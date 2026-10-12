import json 
import redis
from config_file import REDIS_DB,REDIS_HOST,REDIS_PASSWORD,REDIS_PORT,MAX_MESSAGES,SESSION_TTL,SESSION_KEY_PREFIX
import time

#多用户提问结果
#session_result={}

#本地存储改为redis存储

#连接redis
redis_client=redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    password=REDIS_PASSWORD,
    socket_timeout=0.5,  #单次操作超时设置 秒
    socket_connect_timeout=0.5, #连接超时设置 秒
    #retry_on_timeout=False,  #是否重试，False不重试
    decode_responses=True
)

#redis不可用时，兜底
_fallback={}


#熔断器状态
_circuit={
    'failures':0,   #连续失败次数
    'open_until':0,  #熔断到什么时候
}

#连接失败3次就熔断
FAILURE_THRESHOLD=3
#熔断30秒后重试
CIRCUIT_COOLDOWN=30

def _is_circuit_open():
    '''
    判断熔断器是否开启
    '''
    return time.time()<_circuit['open_until']

def _record_failure():
    '''
    记录一次失败
    '''
    if _is_circuit_open():
        return
    _circuit['failures']+=1
    if _circuit['failures']>=FAILURE_THRESHOLD:
        _circuit['open_until']=time.time()+CIRCUIT_COOLDOWN
        print(f"熔断器开启{CIRCUIT_COOLDOWN}内不再尝试连redis")

def _record_success():
    '''
    记录一次成功，重置熔断器。也就是redis当前连接成功，熔断器重置
    '''
    if _circuit['failures']>0:   #这里是判断当前redis连接状态是不是断开的，断开的则输出打印信息
        print(f"redis恢复，熔断器重置")
    _circuit['failures']=0
    _circuit['open_until']=0

def _key(session_id):
    return f"{SESSION_KEY_PREFIX}{session_id}"

def get_session(session_id):
    if _is_circuit_open():
        return _fallback.get(session_id)
    try:
        data=redis_client.get(_key(session_id))   #尝试连接redis获取session_id存储的消息，如果连接redis失败，则走记录失败，熔断器数据更新
        _record_success()
        if data is None:   #如果redis返回了None，说明该session_id之前未访问过，没有相关消息，是新用户
            return None
        return json.loads(data)
    except Exception as e:
        _record_failure()
        print(f"redis读取失败，{type(e).__name__}")
        return _fallback.get(session_id)

#保存会话
def save_session(session_id,messages):
    #兜底上下文第一条内容是system
    MAX=MAX_MESSAGES
    if len(messages)<=MAX:
        trimmed=messages
    else:
        trimmed=messages[-MAX:]
        for i,m in enumerate(trimmed):
            if m.get('role')=='user':
                trimmed=trimmed[i:]
                break
    if messages and messages[0].get('role')=='system':
        if not trimmed or trimmed[0].get('role')!='system':
            trimmed=[messages[0]]+trimmed

    if _is_circuit_open():
        _fallback[session_id]=trimmed
        return
    try:
        redis_client.setex(name=_key(session_id),time=SESSION_TTL,value=json.dumps(trimmed,ensure_ascii=False))
        _record_success()
    except Exception as e:
        _record_failure()
        print(f"redis 写入失败:{type(e).__name__}")
        _fallback[session_id]=trimmed

def delete_session(session_id):
    if not _is_circuit_open():
        try:
            redis_client.delete(_key(session_id))
        except Exception:
            pass
    _fallback.pop(session_id,None)

def ping():
    try:
        return redis_client.ping()
    except redis.RedisError:
        return False

