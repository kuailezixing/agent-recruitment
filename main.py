from config_file import deepseek_api_key,deepseek_base_url,KB_DIR,cache_file
from func_tools import get_date,get_weather,get_adcode
from prompt import tools,system_content
from knowledge import retrieve,build_knowledge_list,load_documents_from_dir,split_by_numbering,get_hashlib_md5,init_knowledge
from session_store import get_session,save_session,delete_session
from openai import OpenAI
import json
import asyncio
import uvicorn
import datetime
from fastapi import FastAPI,HTTPException
from pydantic import BaseModel
from concurrent.futures import ThreadPoolExecutor,as_completed
from fastapi.responses import StreamingResponse
import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi import Response
import time

#连接大模型
client=OpenAI(api_key=deepseek_api_key,base_url=deepseek_base_url)

knowledge_list=init_knowledge(KB_DIR,cache_file)


#根据返回tool_call分流执行对应函数
def execute_one_tool(tool_call,knowledge_list):
    name=tool_call.function.name
    args=json.loads(tool_call.function.arguments)
    result_content=''

    if name=='get_adcode':
        city_name=args['city_name']
        adcode_dict=get_adcode(city_name)
        result_content=f"{adcode_dict['city_name']}对应的adcode是{adcode_dict['adcode']}"
    elif name=='get_weather':
        city_adcode=args['city_adcode']
        city_weather_dict=get_weather(city_adcode)
        result_content=f"{city_weather_dict['city_name']}今天{city_weather_dict['weather']},温度{city_weather_dict['temperature']},风向{city_weather_dict['winddirection']},风级{city_weather_dict['windpower']}。"
    elif name=='get_embedding':
        text=args['text']
        result_content=retrieve(text,knowledge_list,top_k=10)
        if result_content is None:
            result_content="【系统标记:NO_RESULT】：知识库没有相关记录"
    elif name=='get_date':
        text=args['text']
        strs=get_date(text)
        result_content=f"{text}的日期是{strs[text]}"
    return tool_call.id,result_content



#fastapi封装成web服务
app=FastAPI(title='我的裸调agent')
#创建http请求类
class ChatRequest(BaseModel):
    message:str
    session_id:str='default'
#创建http响应类
class ChatResponse(BaseModel):
    answer:str 
    steps:int


#模型运行主函数
def run_agent(user_input:str,session_id:str):
    t0=time.time()
    print("\n" + "=" * 60)
    print(f"【1. 收到用户输入】{user_input}")
    print(f"【1.1 会话ID】{session_id}")
    #查询会话，没有则新建，有则返回会话历史消息
    messages=get_session(session_id)
    if messages is None:
        messages=[{'role':'system','content':system_content}]
        print(f"【2. 新建会话】messages 长度 = {len(messages)}")
    else:
        print(f"【2. 恢复会话】messages 长度 = {len(messages)}")
    messages.append({'role':'user','content':user_input})
    t1=time.time()
    print(f"【Redis 读取】{t1-t0:.2f}s")
    print(f"【3. 追加用户消息后】messages 长度 = {len(messages)}")
    print(f"\n【4. 发送给模型的内容】")
    for i, msg in enumerate(messages):
        content = msg.get('content', '')
        if content and len(str(content)) > 100:
            content = str(content)[:100] + "..."
        print(f"   [{i}] role={msg['role']}, content={content}")
    print(f"   可用工具：{[t['function']['name'] for t in tools]}")
    #将消息传给大模型
    res=client.chat.completions.create(
        messages=messages,
        #model='deepseek-ai/DeepSeek-V3.2',
        model='deepseek-flash',
        tools=tools,
        tool_choice='auto'
    )
    #拿到大模型返回的tool_calls信息
    tool_calls=res.choices[0].message.tool_calls
    t2 = time.time()
    print(f"【第1次大模型】{t2-t1:.2f}s，tool_calls={len(tool_calls) if tool_calls else 0}")
    print(f"\n【5. 模型返回】")
    if tool_calls:
        print(f"   决定调用 {len(tool_calls)} 个工具：")
        for tc in tool_calls:
            print(f"   → {tc.function.name}({tc.function.arguments})")
    else:
        print(f"   直接回答：{res.choices[0].message.content[:100]}")
    
    max_steps=10
    steps=0
    #t1=datetime.datetime.today()
    #print(t1)
    #print(f'tool_calls的数量：{len(tool_calls)}')
    #使用并行执行
    t_llm=t2
    content_str=res.choices[0].message.content
    while tool_calls and steps<max_steps:
        step_start = time.time()
        print(f"\n【6. 进入 ReAct 循环第 {steps} 轮】")
        #因为tool_calls列表元素有ChatCompletionMessagesFunctionToolCall对象，所以要转成json格式
        tool_calls_dict=[tc.model_dump() for tc in tool_calls]
        messages.append({'role':'assistant','content':None,'tool_calls':tool_calls_dict})
        print(f"   追加 assistant 消息（含 tool_calls）")
        tool_results={}
        #execute_one_tool(tool_calls[0],knowledge_list)
        #如果tool_calls里含有多个工具调用信息，则会并行执行
        with ThreadPoolExecutor(max_workers=len(tool_calls)) as executor:
            future_to_call={executor.submit(execute_one_tool,tc,knowledge_list):tc for tc in tool_calls}
            for future in as_completed(future_to_call):
                tc_id,content=future.result()
                tool_results[tc_id]=content
        for tc in tool_calls:
            print(f"   工具 {tc.function.name} 返回：{tool_results[tc.id][:100]}")
            messages.append({
                'role':'tool',
                'tool_call_id':tc.id,
                'content':tool_results[tc.id]
            })
        t_tool = time.time()
        print(f"  【第{steps+1}轮-工具执行】{t_tool-step_start:.2f}s")
        print(f"   追加 tool 结果后，messages 长度 = {len(messages)}")
        #print(f'大模型调用前{datetime.datetime.today()}')
        #把工具调用结果返回给大模型
        res=client.chat.completions.create(
            #model='deepseek-ai/DeepSeek-V3.2',
            model='deepseek-flash',
            messages=messages,
            tools=tools,
            tool_choice='auto'
        )
        t_llm = time.time()
        print(f"  【第{steps+1}轮-大模型】{t_llm-t_tool:.2f}s")
        #print(f'大模型调用后{datetime.datetime.today()}')
        #print(f'当前输入长度：{res.usage.prompt_tokens} token')
        #print(f'当前输出长度：{res.usage.completion_tokens} token')
        #print(f'当前总长度：{res.usage.total_tokens} token')
        #重新拿到大模型返回的tool_calls
        tool_calls=res.choices[0].message.tool_calls
        #判断是否继续调用工具
        if not tool_calls:
            print(f"\n【7. 模型判断任务完成】")
            print(f"   最终回答：{res.choices[0].message.content}")
            final_answer=res.choices[0].message.content
            messages.append({'role':'assistant','content':final_answer})
            print(final_answer)
            break
        else:
            print(f"   模型决定继续调用：{[tc.function.name for tc in tool_calls]}")
        steps=steps+1
        #t2=datetime.datetime.today()
        #print(t2)
        #print(t2-t1)
    if messages[-1].get('role')!='assistant':
        messages.append({'role':'assistant','content':content_str})
    save_session(session_id=session_id,messages=messages)
    t_end = time.time()
    print(f"【Redis 保存】{t_end-t_llm:.2f}s")
    print(f"【总耗时】{t_end-t0:.2f}s")
    print("=" * 60 + "\n")
    return res.choices[0].message.content



#一次性输出
@app.post('/chat',response_model=ChatResponse)
async def chat(request:ChatRequest):
    try:
        t1=datetime.datetime.today()
        answer=run_agent(request.message,request.session_id)
        t2=datetime.datetime.today()
        print(t2-t1)
        return ChatResponse(answer=answer,steps=0)
    except Exception as e:
        raise HTTPException(status_code=500,detail=str(e))

#伪流式输出：先一次性拿到结果，然后把结果拆分成多段，使结果看起来像流式(源于API平台的缘故)
#async 定义异步协程
#yield 生成器，把值发送出去并暂停函数等外面调用方处理完在继续往下
#await 异步暂停
async def fake_stream(text:str):
    #for i in range(0,len(text),5):
    text_list=text.split('，')
    for txt in text_list:
        yield f"data:{txt}\n\n"
        await asyncio.sleep(0.05)
@app.post('/chat/stream')
async def chat_stream(request:ChatRequest):
    answer=run_agent(request.message,request.session_id)
    return StreamingResponse(fake_stream(answer),media_type='text/event-stream')

#添加清空会话的路由，用户切换话题时，调用此路由，防止上下文干扰
@app.post('/session/clear')
async def clear_session(request:ChatRequest):
    delete_session(request.session_id)
    return {'status':'ok','message':f"会话{request.session_id}已清空"}

@app.get('/favicon.png')
async def favicon():
    return Response(status_code=204)


@app.get('/')
async def index():
    return FileResponse('static/index.html')

app.mount('/static',StaticFiles(directory='static'),name='static')
if __name__=='__main__':
    uvicorn.run(app,host='0.0.0.0',port=8000)
    