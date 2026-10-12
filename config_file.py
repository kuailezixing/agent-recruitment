import os

#大模型的api_key
siliconflow_api_key=os.environ.get('SILICONFLOW_API_KEY')
siliconflow_base_url='https://api.siliconflow.cn/v1'
deepseek_api_key=os.environ.get('DEEPSEEK_API_KEY')
deepseek_base_url='https://api.deepseek.com'

#高德地图api_key
amap_key=os.environ.get('AMAP_KEY')

#知识库文档存放本地目录
KB_DIR='./knowledge_base'
#文档分块大小
CHUNK_SIZE=300
#文档分块冗余大小
CHUNK_OVERLAP=50

#文档向量化的文件
cache_file='hashlib_md5_file.json'

#新增redis配置
REDIS_HOST=os.environ.get('REDIS_HOST','localhost')
REDIS_PORT=int(os.environ.get('REDIS_PORT',32768))
REDIS_DB=int(os.environ.get('REDIS_DB',0))
REDIS_PASSWORD=os.environ.get('REDIS_PASSWORD',None)
#会话过期时间
SESSION_TTL=60 * 60 * 24
#会话保留的最大消息条数（防止上下文无限膨胀）
MAX_MESSAGES=20
#会话key的命名
SESSION_KEY_PREFIX='session:'

SCORE_THRESHOLD=0.3
