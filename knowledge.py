import datetime
import os
import re
import requests
from config_file import siliconflow_api_key,SCORE_THRESHOLD
import numpy as np
import hashlib
import json
from rank_bm25 import BM25Okapi
import jieba
import jieba.posseg as pseg


_bm25_index=None
_bm25_corpus=None
_bm25_hash=None

#对字符串分词
def _tokenize(text):
    '''
    中文分词，用jieba切词，转小写
    '''
    return [w.lower() for w in jieba.cut(text) if w.strip()]

#建立bm25索引
def build_bm25_index(knowledge_list):
    '''
    对知识库建立BM25索引，将知识库中的每条记录通过jieba切词，然后通BM25Okapi对切词后的语料库建立索引
    '''
    global _bm25_index,_bm25_corpus,_bm25_hash
    current_hash=hashlib.md5('|||'.join(item['text'] for item in knowledge_list).encode()).hexdigest()
    if _bm25_index is not None and _bm25_hash==current_hash:
        return _bm25_index
    _bm25_corpus=[_tokenize(item['text']) for item in knowledge_list]
    _bm25_index=BM25Okapi(_bm25_corpus)
    _bm25_hash=current_hash
    print(f"BM25索引构建完成，共{len(_bm25_corpus)}条")
    return _bm25_index

#在知识库中根据bm25检索查询，返回得分最高的前10个
def bm25_search(query,knowledge_list,top_n=None):
    '''
    先建立知识库的BM25索引，然后对query切词，计算切词后的语料库在知识库中根据BM25检索的得分，返回前10
    '''
    index=build_bm25_index(knowledge_list=knowledge_list)
    tokens=_tokenize(query)
    scores=index.get_scores(tokens)
    scored=list(zip(scores,knowledge_list))
    scored.sort(key=lambda x:x[0],reverse=True)
    if top_n is None:
        return scored
    return scored[:top_n]

def _doc_key(item):
    return f"{item['source']}#{item.get('chunk_id',item.get('num',''))}"


def rrf_fusion(vector_result,bm25_result,k=60):
    rrf_scores={}
    for rank,(_,item) in enumerate(vector_result):
        #key=item['text']
        key=_doc_key(item)
        rrf_scores[key]=rrf_scores.get(key,0)+1.0/(k+rank+1)

    for rank,(_,item) in enumerate(bm25_result):
        #key=item['text']
        key=_doc_key(item)
        rrf_scores[key]=rrf_scores.get(key,0)+1.0/(k+rank+1)

    key_to_item={_doc_key(item):item for (_,item) in vector_result+bm25_result}
    sorted_keys=sorted(rrf_scores.keys(),key=lambda x:rrf_scores[x],reverse=True)
    return [(rrf_scores[key],key_to_item[key]) for key in sorted_keys]



#1、检查目录是否存在，不存在返回空列表；2、检查是否txt或md文件；3、获取文档内容并与文件名一起存入列表返回
def load_documents_from_dir(dir_path):
    '''
    读取本地目录的txt和md文档
    '''
    docs=[]
    if not os.path.exists(dir_path):
        print(f"知识库目录不存在：{dir_path}")
        return docs
    for filename in os.listdir(dir_path):
        if not filename.endswith(('.txt','.md')):
            continue
        filepath=os.path.join(dir_path,filename)
        with open(filepath,'r',encoding='utf-8') as f:
            content=f.read().strip()
            if content:
                docs.append((filename,content))
    print(f"共读取{len(docs)}个文档")
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
    pattern=r'(?=^\s*[-–—]?\s*\d+\s*[、\.\)]\s*)'
    parts=re.split(pattern=pattern,string=text,flags=re.MULTILINE)
    results=[]
    for part in parts:
        part=part.strip()
        if not part:
            continue
        match=re.match(r'^\s*[-–—]?\s*(\d+)\s*[、\.\)]',part)
        if match:
            results.append({'text':part,'num':match.group(1)})
    return results


def split_by_heading(text,max_chunk_size=800):
    '''
    根据Markdown标题分块
    每个标题+下面的内容为一个块
    '''
    pattern=r'(?=^#{1,3}\s+)'
    parts=re.split(pattern=pattern,string=text,flags=re.MULTILINE)
    results=[]
    pending_title=[]
    for part in parts:
        part=part.strip()
        if not part:
            continue
        match=re.match(r'^(#{1,3})\s+(.+)',part)
        if not match:
            continue
        lines=[l for l in part.split('\n') if l.strip()]
        is_pure_title=len(lines)<=1 and len(part)<50
        if is_pure_title:
            pending_title.append(part)
            continue
        if pending_title:
            part='\n\n'.join(pending_title)+'\n\n'+part
            pending_title=[]
        if len(part)>max_chunk_size:
            sub_parts=split_by_paragraph(part,min_length=200)
            for sub in sub_parts:
                results.append({'text':sub['text']})
        else:
            results.append({'text':part})
    if pending_title:
        results.append({'text':'\n\n'.join(pending_title)})
    return results



def split_by_paragraph(text,min_length=50):
    '''
    兜底策略，按空行切分段落
    min_length:太短的段落合并到下一段，知道达到最小长度
    '''
    parts=re.split(r'\n\s*\n',text)
    results=[]
    buffer=""
    for part in parts:
        part=part.strip()
        if not part:
            continue
        buffer+='\n\n'+part if buffer else part
        if len(buffer)>=min_length:
            results.append({'text':buffer})
            buffer=""
    if buffer:
        results.append({'text':buffer})
    return results


def smart_split(text):
    '''
    智能分块：根据文档格式自动选择策略
    返回(chunks,strategy_name)
    '''
    #优先级1，Markdown标题
    heading_count=len(re.findall(r'^#{1,3}\s+',text,flags=re.MULTILINE))
    if heading_count>3:
        return split_by_heading(text),'heading'
    #优先级2，按编号,排除日期干扰
    numbering_pattern=r'^\s*[-–—]?\s*\d+\s*[、\)]\s*'
    numbered_lines=[l for l in text.split('\n') if re.match(numbering_pattern,l)]
    if len(numbered_lines)>=5 and len(numbered_lines)/max(len(text.split('\n')),1)>0.3:
        return split_by_numbering(text),'numbering'
    #优先级3，兜底按段落
    return split_by_paragraph(text),'paragraph'





#文档向量化
def get_embedding(text):
    '''
    将text字符串转成向量
    '''
    headers={'Authorization': f"Bearer {siliconflow_api_key}"} 
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
def build_knowledge_list(docs):
    '''
    传入列表文档docs,构建相应的向量库
    '''
    result=[]
    for idx,data in enumerate(docs):
        print(f"正在构建第{idx+1}/{len(docs)}条：{data['text'][:20]}...")
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
def rerank_documents(query,documents,top_n):
    '''
    将大模型检索的结果进行重排序
    '''
    url='https://api.siliconflow.cn/v1/rerank'
    headers= {'Authorization': f"Bearer {siliconflow_api_key}"}
    params={'model':'BAAI/bge-reranker-v2-m3','query':query,'documents':documents,'top_n':top_n,'return_documents':True}
    res=requests.post(url=url,headers=headers,json=params)
    return res.json()['results']

#构建知识库通用过滤器
def extract_metadata(text,source):
    #提取文档关键信息作为元数据
    meta={}
    m=re.match(r'^\s*[-–—]?\s*(\d+)\s*[、\)]',text)
    if m:
        meta['num']=m.group(1)
    m=re.search(r'(\d{4})年(\d{2})月(\d{2})日',text)
    if m:
        meta['date']=f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    else:
        m=re.search(r'(\d{4})-(\d{2})-(\d{2})',text)
        if m:
            meta['date']=f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    if re.search(r'第\s*\d+\s*(个|条|点|项)',text):
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
    m=re.search(r'(\d{1,2})月(\d{1,2})[日号]?',query)
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
        filters['type']='question'
    elif 'key' in query or '密钥' in query or 'Key' in query:
        filters['type']='key'
    elif  '条目' in query:
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



def extract_content_word(query):
    """
    用 jieba POS 标注提取实词（关键词）
    只保留：英文词（eng）+ 名词（n 开头）+ 动名词（vn）
    过滤：虚词（u）、介词（p）、副词（d）、连词（c）等
    """
    keywords=[]
    for word,flag in pseg.cut(query):
        word_lower=word.lower()
        if flag=='eng' or flag.startswith('n') or flag=='vn':
            if len(word_lower)>=2:
                keywords.append(word_lower)
    for match in re.findall(r'[a-zA-Z][a-zA-Z0-9+#\.]*',query):
        w=match.lower()
        if len(w)>=2 and w not in keywords:
            keywords.append(w)
    return keywords


def check_keywords_in_corpus(query,knowledge_list):
    """
    检查 query 里的实词是否在知识库里出现过
    返回 (是否通过, 未命中的关键词)
    """
    keywords=extract_content_word(query)
    if not keywords:
        return True,[]
    corpus_text=' '.join(item['text'].lower() for item in knowledge_list)
    matched=[kw for kw in keywords if kw in corpus_text]
    missed=[kw for kw in keywords if kw not in corpus_text]
    if not matched:
        return False,missed
    return True,missed




#通用agent流程架构
#3、agent整体流程
def retrieve(query,knowledge_list,top_k=5,score_threshold=SCORE_THRESHOLD):
    '''
    通用检索：约束提取，元数据过滤，向量检索，精排
    '''
    #提取约束
    filters=extract_filter(query)
    print(f"提取的约束：{filters}")

    #关键词存在性检查
    passed,missed=check_keywords_in_corpus(query,knowledge_list)
    if not passed:
        print(f"关键词全部未在知识库里出现：{missed} 返回None")
        return None

    #元数据过滤：应用约束
    candidates=apply_filters(knowledge_list,filters)
    #硬性约束条件，没有匹配上则返回未找到
    hard_filter={'date','num','source','type'}
    if not candidates and any(k in filters for k in hard_filter):
        return None
    
    if not candidates:
        candidates=knowledge_list
    if not candidates:
        return None
    if len(candidates)==1:
        return format_result(candidates[0])
    #向量检索
    vec=get_embedding(query)
    vector_scored=[(cosine_similarity(vec,c['vec']),c) for c in candidates]
    vector_scored.sort(key=lambda x:x[0],reverse=True)
    #判断检索结果与查询相关性，低于阈值，则判断为不相关
    if vector_scored[0][0]<score_threshold:
        return None
    #向量检索前10条记录
    vector_top=vector_scored
    #新增bm25检索逻辑
    #bm25
    #元数据过滤后的记录内容
    candidate_keys={_doc_key(c) for c in candidates}
    #元数据过滤后提取内容和全量知识库匹配，得出前20条记录
    bm25_all=bm25_search(query=query,knowledge_list=knowledge_list)
    bm25_top=[(s,item) for s,item in bm25_all if _doc_key(item) in candidate_keys]
    #rrf融合
    fused=rrf_fusion(vector_top,bm25_top)
    print(f"向量 {len(vector_top)}+BM25 {len(bm25_top)} 融合 {len(fused)}")

    seen_source=set()
    deduped=[]
    for item in fused:
        src=item[1]['source']
        if src not in seen_source:
            seen_source.add(src)
            deduped.append(item)
    print(f"去重后：{len(deduped)}个候选人")
    #精排：重排序rerank
    #if len(scored)>3:
    #下面把scored改成fused
    #限制精排条数30条
    if not deduped:
        return None
    fused=deduped[:30]
    if len(fused)>3:
        top_text=[item['text'] for _,item in fused[:30]]
        reranked=rerank_documents(query=query,documents=top_text,top_n=top_k)
        text_to_key={item['text']:_doc_key(item) for _,item in fused}
        key_to_item={_doc_key(item):item for _,item in fused}
        final=[]
        for r in reranked:
            key=text_to_key.get(r['document']['text'])
            if key and key in key_to_item:
                final.append(key_to_item[key])
    else:
        final=[item for _,item in fused[:top_k]]
    #组装返回
    return "\n\n".join(format_result(c) for c in final)

def init_knowledge(KB_DIR,cache_file):
    #记录分块后的文档
    raw_docs=[]
    #给知识库添加内容：分块的内容，所属文件名，分块的索引
    for filename,content in load_documents_from_dir(dir_path=KB_DIR):
        #chunks=split_by_numbering(content)
        chunks,stategy=smart_split(content)
        for idx,chunk in enumerate(chunks):
            raw_docs.append({'text':chunk['text'],'source':filename,'chunk_id':idx})
        print(f"{filename}被切分成{len(chunks)}块(策略:{stategy})")
    print(f"知识库中共有{len(raw_docs)}个块")

    current_cache_hash=get_hashlib_md5(raw_docs)

    #如果本地已存在缓存文件，则根据hash值判断是否一致，不一致则更新。如果不存在缓存文件，则新建
    if os.path.exists(cache_file):
        try:
            with open(cache_file,'r',encoding='utf-8') as f:
                cache_data=json.load(f)
                if cache_data.get('hash')==current_cache_hash:
                    print('缓存向量库与当前向量库一致')
                    knowledge_list=cache_data['data']
                else:
                    print('缓存向量与当前向量库不一致')
                    knowledge_list=build_knowledge_list(raw_docs)
                    with open(cache_file,'w',encoding='utf-8') as f:
                        json.dump({'hash':current_cache_hash,'data':knowledge_list},f,ensure_ascii=False,indent=2)
                    print('新向量库已持久化到缓存文件')
        except:
            knowledge_list=build_knowledge_list(raw_docs)
            os.remove(cache_file)
            with open(cache_file,'w',encoding='utf-8') as f:
                json.dump({'hash':current_cache_hash,'data':knowledge_list},f,ensure_ascii=False,indent=2)
    else:
        print('首次启动，构建向量库')
        knowledge_list=build_knowledge_list(raw_docs)
        with open(cache_file,'w',encoding='utf-8') as f:
            json.dump({'hash':current_cache_hash,'data':knowledge_list},f,ensure_ascii=False,indent=2)
    return knowledge_list

