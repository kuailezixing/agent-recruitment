from config_file import api_key,base_url,KB_DIR,cache_file
from func_tools import get_date,get_weather,get_adcode
from prompt import tools,system_content
from knowledge import retrieve,build_knowledge_list,load_documents_from_dir,split_by_numbering,get_hashlib_md5,init_knowledge
from session_store import session_result
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

#连接大模型
client=OpenAI(api_key=api_key,base_url=base_url)

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
        result_content=retrieve(text,knowledge_list)
    elif name=='get_date':
        text=args['text']
        strs=get_date(text)
        result_content=f"{text}的日期是{strs[text]}"
        if result_content is None:
            result_content="【系统标记:NO_RESULT】：知识库没有相关记录"
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
def run_agent(user_input:str,session_id:str,session_result=session_result):
    print(f"收到参数user_input的值：{user_input}")
    if session_id in session_result.keys():
        messages=session_result[session_id]
    else:
        messages=[{'role':'system','content':system_content}]
        session_result[session_id]=messages
    messages.append({'role':'user','content':user_input})
    res=client.chat.completions.create(
        messages=messages,
        model='deepseek-ai/DeepSeek-V3.2',
        tools=tools,
        tool_choice='auto'
    )
    tool_calls=res.choices[0].message.tool_calls
    max_steps=10
    steps=0
    t1=datetime.datetime.today()
    print(t1)
    #print(f'tool_calls的数量：{len(tool_calls)}')
    #使用并行执行
    while tool_calls and steps<max_steps:
        messages.append({'role':'assistant','content':None,'tool_calls':tool_calls})
        tool_results={}

        #execute_one_tool(tool_calls[0],knowledge_list_new=knowledge_list_new)

        with ThreadPoolExecutor(max_workers=len(tool_calls)) as executor:
            future_to_call={executor.submit(execute_one_tool,tc,knowledge_list):tc for tc in tool_calls}
            for future in as_completed(future_to_call):
                tc_id,content=future.result()
                tool_results[tc_id]=content
        for tc in tool_calls:
            messages.append({
                'role':'tool',
                'tool_call_id':tc.id,
                'content':tool_results[tc.id]
            })
        #print(f'大模型调用前{datetime.datetime.today()}')
        res=client.chat.completions.create(
            model='deepseek-ai/DeepSeek-V3.2',
            messages=messages,
            tools=tools,
            tool_choice='auto'
        )
        #print(f'大模型调用后{datetime.datetime.today()}')
        #print(f'当前输入长度：{res.usage.prompt_tokens} token')
        #print(f'当前输出长度：{res.usage.completion_tokens} token')
        #print(f'当前总长度：{res.usage.total_tokens} token')
        tool_calls=res.choices[0].message.tool_calls
        if not tool_calls:
            print(res.choices[0].message.content)
            break
        steps=steps+1
        #t2=datetime.datetime.today()
        #print(t2)
        #print(t2-t1)
    session_result[session_id]=messages
    return res.choices[0].message.content



#一次性输出
@app.post('/chat',response_model=ChatResponse)
async def chat(request:ChatRequest):
    try:
        answer=run_agent(request.message,request.session_id)
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


if __name__=='__main__':
    uvicorn.run(app,host='0.0.0.0',port=8000)