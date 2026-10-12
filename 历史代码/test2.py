
#######################################v0.6：v0.5基础上，优化知识库切分策略，改为结构感知切分，当前切分规则是按照编号
import os
from openai import OpenAI
import requests
import json
import numpy as np
import datetime
import re
import hashlib
from concurrent.futures import ThreadPoolExecutor,as_completed
import time 
from fastapi import FastAPI,HTTPException
import uvicorn
from pydantic import BaseModel
import asyncio
from fastapi.responses import StreamingResponse

#全局变量
#大模型的api_key
api_key=os.environ.get('OPENAI_API_KEY')
#连接大模型
client=OpenAI(api_key=api_key,base_url='https://api.siliconflow.cn/v1')

#知识库文档存放本地目录
KB_DIR='./knowledge_base'
#文档分块大小
CHUNK_SIZE=300
#文档分块冗余大小
CHUNK_OVERLAP=50

#多用户提问结果
session_result={}

#文档向量化的文件
cache_file='hashlib_md5_file.json'

#文档分块后的结果
raw_docs=[]

#自定义工具函数
#获取城市天气
def get_weather(city_adcode):
    '''
    city_adcode:城市的区域编码。
    播报城市的天气情况
    '''
    print('get_weather被调用了')
    key='857dba005b01a693ec2c5c0aebc44bf9'
    url='https://restapi.amap.com/v3/weather/weatherInfo'
    params={'key':key,'city':city_adcode}
    res=requests.get(url=url,params=params)
    lives=res.json()['lives'][0]
    city_name=lives['city']
    weather=lives['weather']
    temperature=lives['temperature']
    winddirection=lives['winddirection']
    windpower=lives['windpower']
    city_weather_dict={'city_name':city_name,'weather':weather,'temperature':temperature,'winddirection':winddirection,'windpower':windpower}
    return city_weather_dict

#获取城市对应的编码
def get_adcode(city_name):
    '''
    根据参数city_name城市名称,获取city_name对应的adcode区域编码
    '''
    print('get_adcode工具被调用了')
    api_url='https://restapi.amap.com/v3/config/district'
    params={'key':'857dba005b01a693ec2c5c0aebc44bf9','keywords':city_name}
    res=requests.get(url=api_url,params=params)
    adcode_dict={'adcode':res.json()['districts'][0]['adcode'],'city_name':city_name}
    return adcode_dict

#口语日期格式化
def get_date(text):
    '''
    将口语化的日期描述转成年月日格式，
    例如9月1号转成当年的9月1号，即2026年09月01号
    '''
    date_str=None
    if '今天' in text:
        date_str=(datetime.datetime.today()).strftime("%Y年%m月%d日")
        date_str=text.replace('今天',date_str)
    if '昨天' in text:
        date_str=(datetime.datetime.today()+datetime.timedelta(days=-1)).strftime("%Y年%m月%d日")
        date_str=text.replace('昨天',date_str)
    if '前天' in text:
        date_str=(datetime.datetime.today()+datetime.timedelta(days=-2)).strftime("%Y年%m月%d日")
        date_str=text.replace('前天',date_str)
    if '大前天' in text:
        date_str=(datetime.datetime.today()+datetime.timedelta(days=-3)).strftime("%Y年%m月%d日")
        date_str=text.replace('大前天',date_str)
    match = re.search(r'(\d{1,2})月(\d{1,2})日?', text)
    if match:
        month, day = match.groups()
        # 假设是今年，如果已经过了则视为明年（可简化）
        date_str = f"{datetime.datetime.today().year}年{int(month):02d}月{int(day):02d}日"
        #date_str = text.replace(match.group(0), target)
    return {text:date_str}

#1、检查目录是否存在，不存在返回空列表；2、检查是否txt或md文件；3、获取文档内容并与文件名一起存入列表返回
def load_documents_from_dir(dir_path):
    '''
    读取本地目录的txt和md文档
    '''
    docs=[]
    if not os.path.exists(dir_path):
        print(f'知识库目录不存在：{dir_path}')
        return docs
    for filename in os.listdir(dir_path):
        if not filename.endswith(('.txt','.md')):
            continue
        filepath=os.path.join(dir_path,filename)
        with open(filepath,'r',encoding='utf-8') as f:
            content=f.read().strip()
            if content:
                docs.append((filename,content))
    print(f'共读取{len(docs)}个文档')
    return docs

#对文档分块，按照默认300字符串分割，50字符串冗余
def split_into_chunks(text,chunk_size,chunk_overlap):
    '''
    将文档按照指定大小分块,返回切分好的文档块列表
    '''
    chunks=[]
    start=0
    while start<len(text):
        end=start+chunk_size
        chunk=text[start:end]
        chunks.append(chunk.strip())
        start=end-chunk_overlap
        if start>=len(text):
            break
    return [c for c in chunks if c]


def split_by_numbering(text):
    '''
    根据数字，编号切分文档，返回切分好的文档块列表
    '''
    pattern=r'(?=^\s*[-——]?\s*\d+\s*[、\.\)]\s*)'
    parts=re.split(pattern=pattern,string=text,flags=re.MULTILINE)
    results=[]
    for part in parts:
        part=part.strip()
        if not part:
            continue
        match=re.match(r'^\s*[-——]?\s*(\d+)\s*[、\.\)]',part)
        if match:
            results.append({'text':part,'num':match.group(1)})
    return results


#文档向量化
def get_embedding(text):
    '''
    将text字符串转成向量
    '''
    headers={'Authorization': f'Bearer {api_key}'} 
    url='https://api.siliconflow.cn/v1/embeddings'
    params={'model':'Qwen/Qwen3-Embedding-4B','input':text}
    res=requests.post(url=url,headers=headers,json=params)
    return res.json()['data'][0]['embedding']

#余弦相似度
def cosine_similarity(vec1,vec2):
    '''
    计算向量参数vec1和vec2之间的余弦相似度
    '''
    vec_1=np.array(vec1)
    vec_2=np.array(vec2)
    dot=np.dot(vec_1,vec_2)
    norm_1=np.linalg.norm(vec_1)
    norm_2=np.linalg.norm(vec_2)
    if norm_1==0 or norm_2==0:
        return 0
    else:
        return dot/(norm_1*norm_2)

#文档验证码
def get_hashlib_md5(docs):
    '''
    将docs文档列表拼接成一个字符串，然后生成其对应的唯一32位16进制的字符串
    '''
    #f1='|||'.join(docs)
    f1='|||'.join([d['text'] for d in docs])
    return hashlib.md5(f1.encode(encoding='utf-8')).hexdigest()

#知识库添加向量库
def build_knowlege_list(docs):
    '''
    传入列表文档docs,构建相应的向量库
    '''
    result=[]
    for idx,data in enumerate(docs):
        print(f'正在构建第{idx+1}/{len(docs)}条：{data['text'][:20]}...')
        text=data['text']
        meta=extract_metadata(text,data.get('source',''))
        vec=get_embedding(text)
        result.append({
            'text':text,
            'vec':vec,
            'source':data.get('source',''),
            'chunk_id':data.get('chunk_id'),
            'num':meta.get('num'),
            'date':meta.get('date'),
            'type':meta.get('type'),
            'title':meta.get('title')
            })
    return result

#检索的结果重排序
def rerank_documents(query,api_key,documents,top_n):
    '''
    将大模型检索的结果进行重排序
    '''
    url='https://api.siliconflow.cn/v1/rerank'
    headers= {'Authorization': f'Bearer {api_key}'}
    params={'model':'BAAI/bge-reranker-v2-m3','query':query,'documents':documents,'top_n':top_n,'return_documents':True}
    res=requests.post(url=url,headers=headers,json=params)
    return res.json()['results']

#构建知识库通用过滤器
def extract_metadata(text,source):
    #提取文档关键信息作为元数据
    meta={}
    m=re.match(r'^\s*[-——]?\s*(\d+)\s*[、\.\)]',text)
    if m:
        meta['num']=m.group(1)
    m=re.search(r'(\d{4})年(\d{2})月(\d{2})日',text)
    if m:
        meta['date']=f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    else:
        m=re.search(r'(\d{4})-(\d{2})-(\d{2})',text)
        if m:
            meta['date']=f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    if re.search(r'第\s*\d+\s*(个|条|点|项)',text) or text.startswith('- '):
        meta['type']='question'
    elif 'key' in text or '密钥' in text:
        meta['type']='key'
    else:
        meta['type']='note'
    if source:
        meta['title']=source.rsplit('.',1)[0]
    return meta

#解析日期
def parse_date_from_query(query):
    '''
    从query中解析日期，返回YYYY-MM-DD格式，无则返回None
    '''
    today=datetime.datetime.today()
    if '今天' in query:
        return today.strftime('%Y-%m-%d')
    if '昨天' in query:
        return (today-datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    if '前天' in query:
        return (today-datetime.timedelta(days=2)).strftime('%Y-%m-%d')
    m=re.search(r'(\d{1,2})月(\d{1,2})[日,号]?',query)
    if m:
        return f"{today.year}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    return None


#通用agent流程架构
#1、从用户查询中提取约束条件
def extract_filter(query):
    '''
    从query中提取结构化约束，返回字典
    '''
    filters={}
    date_str=parse_date_from_query(query)
    if date_str:
        filters['date']=date_str
    m=re.search(r'第\s*(\d+)\s*(?:个|条|点|项|问|问题)?',query)
    if m:
        filters['num']=m.group(1)
    if 'key' in query or '密钥' in query or 'Key' in query:
        filters['type']='key'
    elif '问题' in query or '条目' in query:
        filters['type']='question'
    m=re.search(r'[\'"《]([^\'"》]+\.(?:md|txt|pdf))[\'"》]',query)
    if m:
        filters['source']=m.group(1)
    return filters

#通用agent流程架构
#2、应用约束条件到知识库文档
def apply_filters(docs,filters):
    '''
    按filters里每个键值对过滤docs
    '''
    if not filters:
        return docs
    result=docs
    for key,value in filters.items():
        result=[d for d in result if d.get(key)==value]
    return result

#格式化返回
def format_result(item):
    '''
    统一格式化返回
    '''
    src=f"【来源：{item['source']}"
    if item.get('num'):
        src+=f"第{item['num']}条"
    src+="】"
    return f"{src}{item['text']}"

#通用agent流程架构
#3、agent整体流程
def retrieve(query,knowlege_list,top_k=3):
    '''
    通用检索：约束提取，元数据过滤，向量检索，精排
    '''
    #提取约束
    filters=extract_filter(query)
    print(f"提取的约束：{filters}")
    #元数据过滤
    candidates=apply_filters(knowlege_list,filters)
    if not candidates:
        candidates=knowlege_list
    if not candidates:
        return '未找到相关记录'
    if len(candidates)==1:
        return format_result(candidates[0])
    #向量检索
    vec=get_embedding(query)
    scored=[(cosine_similarity(vec,c['vec']),c) for c in candidates]
    scored.sort(key=lambda x:x[0],reverse=True)
    #精排：重排序
    if len(scored)>3:
        top_text=[c['text'] for _,c in scored[:10]]
        reranked=rerank_documents(query=query,api_key=api_key,documents=top_text,top_n=top_k)
        final=[]
        for r in reranked:
            for _,c in scored:
                if c['text']==r['document']['text']:
                    final.append(c)
                    break
    else:
        final=[c for _,c in scored[:top_k]]
    #组装返回
    return "\n\n".join(format_result(c) for c in final)


#根据返回tool_call分流执行对应函数
def execute_one_tool(tool_call,knowlege_list):
    name=tool_call.function.name
    args=json.loads(tool_call.function.arguments)
    result_content=''

    if name=='get_adcode':
        city_name=args['city_name']
        adcode_dict=get_adcode(city_name)
        result_content=f'{adcode_dict['city_name']}对应的adcode是{adcode_dict['adcode']}'
    elif name=='get_weather':
        city_adcode=args['city_adcode']
        city_weather_dict=get_weather(city_adcode)
        result_content=f'{city_weather_dict['city_name']}今天{city_weather_dict['weather']},温度{city_weather_dict['temperature']},风向{city_weather_dict['winddirection']},风级{city_weather_dict['windpower']}。'
    elif name=='get_embedding':
        text=args['text']
        result_content=retrieve(text,knowlege_list)
    elif name=='get_date':
        text=args['text']
        strs=get_date(text)
        result_content=f'{text}的日期是{strs[text]}'
        #knowlege_list_new=[]
        #for item in knowlege_list:
        #    if strs[text] in item['text']:
        #        knowlege_list_new.append(item)
    return tool_call.id,result_content


#自定义工具集
tools=[
    {
        'type':'function',
        'function':{
            'name':'get_weather',
            'description':'播报城市的天气情况,当用户查询多个城市时，可以为每个城市分别调用此工具,且可以一次返回多个调用',
            'parameters':{
                'type':'object',
                'properties':{
                    'city_adcode':{
                        'type':'string',
                        'description':'城市区域编码'
                    }
                },
                'required':['city_adcode'],
                'additionalProperties':False,
            },
            'strict':True
        }
    },
    {
        'type':'function',
        'function':{
            'name':'get_adcode',
            'description':'根据参数city_name城市名称,获取city_name对应的adcode区域编码,当用户查询多个城市时，可以为每个城市分别调用此工具,且可以一次返回多个调用',
            'parameters':{
                'type':'object',
                'properties':{
                    'city_name':{
                        'type':'string',
                        'description':'城市名称'
                    }
                },
                'required':['city_name'],
                'additionalProperties':False,
            },
            'strict':True
        }
    },
    {
        'type':'function',
        'function':{
            'name':'get_embedding',
            'description':'从本地知识库检索信息。当用户需要查询自己的学习记录，私人信息，历史笔记，API密钥，配置参数，个人文档等无法从公共尝试获取时，需要从本地知识库检索相关信息时，必须调用此工具。',
            'parameters':{
                'type':'object',
                'properties':{
                    'text':{
                        'type':'string',
                        'description':'文本/文档'
                    }
                },
                'required':['text'],
                'additionalProperties':False,
            },
            'strict':True
        }
    },
#    {
#        'type':'function',
#        'function':{
#            'name':'cosine_similarity',
#            'description':'计算向量参数vec1和vec2之间的余弦相似度',
#            'parameters':{
#                'type':'object',
#                'properties':{
#                    'vec1':{
#                        'type':'dict',
#                        'description':'数值向量'
#                    },
#                    'vec2':{
#                        'type':'dict',
#                        'description':'数值向量'
#                    },
#                },
#                'required':['vec1','vec2'],
#                'additionalProperties':False,
#            },
#            'strict':True
#        }
#    },
    {
            'type':'function',
            'function':{
                'name':'get_date',
                'description':'将口语化的时间描述转成YYYY年mm月dd日格式，例如今天，昨天，或者是9月1号',
                'parameters':{
                    'type':'object',
                    'properties':{
                        'text':{
                            'type':'str',
                            'description':'用户问题'
                        },
                    },
                    'required':['text'],
                    'additionalProperties':False,
                },
                'strict':True
            }
        },
]



#给知识库添加内容：分块的内容，所属文件名，分块的索引
for filename,content in load_documents_from_dir(dir_path=KB_DIR):
    chunks=split_by_numbering(content)
    for idx,chunk in enumerate(chunks):
        raw_docs.append({'text':chunk['text'],'source':filename,'chunk_id':idx,'num':chunk['num']})
    print(f'{filename}被切分成{len(chunks)}块')
print(f'知识库中共有{len(raw_docs)}个块')

current_cache_hash=get_hashlib_md5(raw_docs)

#如果本地已存在缓存文件，则根据hash值判断是否一致，不一致则更新。如果不存在缓存文件，则新建
if os.path.exists(cache_file):
    try:
        with open(cache_file,'r',encoding='utf-8') as f:
            cache_data=json.load(f)
            if cache_data.get('hash')==current_cache_hash:
                print('缓存向量库与当前向量库一致')
                knowlege_list=cache_data['data']
            else:
                print('缓存向量与当前向量库不一致')
                knowlege_list=build_knowlege_list(raw_docs)
                with open(cache_file,'w',encoding='utf-8') as f:
                    json.dump({'hash':current_cache_hash,'data':knowlege_list},f,ensure_ascii=False,indent=2)
                print('新向量库已持久化到缓存文件')
    except:
        knowlege_list=build_knowlege_list(raw_docs)
        os.remove(cache_file)
        with open(cache_file,'w',encoding='utf-8') as f:
            json.dump({'hash':current_cache_hash,'data':knowlege_list},f,ensure_ascii=False,indent=2)
else:
    print('首次启动，构建向量库')
    knowlege_list=build_knowlege_list(raw_docs)
    with open(cache_file,'w',encoding='utf-8') as f:
        json.dump({'hash':current_cache_hash,'data':knowlege_list},f,ensure_ascii=False,indent=2)

knowlege_list_new=knowlege_list



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
    print(f'收到参数user_input的值：{user_input}')
    if session_id in session_result.keys():
        messages=session_result[session_id]
    else:
        messages=[{'role':'system','content':'你是一个智能查询助手，同时你也是一个超级大脑，对于常识问题，直接回答就行。对于用户提问涉及到“我的”、密钥、key、个人笔记等私人信息类时，必须在知识库中先行检索。如果有时间的口语化描述，请按照工具返回的格式'}]
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

        #execute_one_tool(tool_calls[0],knowlege_list_new=knowlege_list_new)

        with ThreadPoolExecutor(max_workers=len(tool_calls)) as executor:
            future_to_call={executor.submit(execute_one_tool,tc,knowlege_list_new):tc for tc in tool_calls}
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
        yield f'data:{txt}\n\n'
        await asyncio.sleep(0.05)
@app.post('/chat/stream')
async def chat_stream(request:ChatRequest):
    answer=run_agent(request.message,request.session_id)
    return StreamingResponse(fake_stream(answer),media_type='text/event-stream')


if __name__=='__main__':
    uvicorn.run(app,host='0.0.0.0',port=8000)
