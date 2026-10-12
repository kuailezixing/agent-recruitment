# Agent 系统完整流程图解（从用户提问到返回结果）

> 本文档以你当前的 `main.py` 为主线，逐步骤拆解。每一步包含：**输入 → 处理 → 输出 → 技术解释 → 对应代码 → 行业术语 → 生产环境差异**。

---

## 全景图（先看这个）

```
用户提问
  ↓
【第1步】HTTP 请求到达 FastAPI
  ↓
【第2步】加载会话历史（Redis）
  ↓
【第3步】第一次调用大模型（决策：是否需要工具）
  ↓
【第4步】判断 tool_calls 是否存在
  ├─ 有 → 进入 ReAct 循环（第5-8步）
  └─ 无 → 直接生成回答（跳到第9步）
  ↓
【第5步】并行执行工具（ThreadPoolExecutor）
  ↓
【第6步】工具结果追加到 messages
  ↓
【第7步】第二次调用大模型（基于工具结果）
  ↓
【第8步】循环判断：还有 tool_calls 吗？
  ├─ 有 → 回到第5步
  └─ 无 → 跳出循环
  ↓
【第9步】保存会话到 Redis
  ↓
【第10步】返回 JSON 响应
```

---

## 【第1步】HTTP 请求到达 FastAPI

### 输入
用户在浏览器/终端发起：
```bash
POST http://localhost:8000/chat
Content-Type: application/json

{"message": "上海天气怎么样", "session_id": "user_a"}
```

### 处理
FastAPI 收到请求后：
1. 解析 HTTP 协议（请求行、Header、Body）
2. 校验 JSON 格式
3. 用 Pydantic 把 Body 转成 `ChatRequest` 对象
4. 调用路由函数 `chat(request)`

### 输出
一个 `ChatRequest` 对象：
```python
ChatRequest(message="上海天气怎么样", session_id="user_a")
```

### 技术解释
- **HTTP 是无状态协议**：服务端默认不记得"上一个请求是谁发的"
- **Pydantic 数据校验**：自动检查字段类型，缺字段或类型错误会返回 422 错误
- **Uvicorn 是 ASGI 服务器**：负责 socket 监听、HTTP 解析、把请求转发给 FastAPI

### 对应代码
```python
# main.py
class ChatRequest(BaseModel):
    message: str
    session_id: str = 'default'

@app.post('/chat', response_model=ChatResponse)
async def chat(request: ChatRequest):
    answer = run_agent(request.message, request.session_id)
    return ChatResponse(answer=answer, steps=0)
```

### 行业术语
- **RESTful API**：基于 HTTP 的接口设计风格
- **Pydantic Model**：数据校验和序列化模型
- **ASGI（Asynchronous Server Gateway Interface）**：Python 异步 Web 服务标准

### 生产环境差异
| 维度 | 开发环境 | 生产环境 |
| :--- | :--- | :--- |
| **服务器** | Uvicorn 单进程 | Gunicorn + Uvicorn Worker 多进程 |
| **HTTPS** | 无 | Nginx 反向代理 + SSL |
| **认证** | 无 | JWT / API Key / OAuth |
| **限流** | 无 | Nginx 限流 / Redis 令牌桶 |
| **日志** | print | Structured Logging（JSON 格式） |

### 生产环境常见问题
1. **单进程瓶颈**：Uvicorn 单进程只能用一个 CPU 核，QPS 上不去
2. **无认证**：任何人知道 URL 就能调用，会烧你的 Token
3. **无超时**：客户端一直挂着，占用服务端资源
4. **无幂等性**：用户网络抖动重试，会重复扣费

---

## 【第2步】加载会话历史（Redis）

### 输入
```python
session_id = "user_a"
```

### 处理
`get_session("user_a")` 函数：
1. 检查熔断器是否开启
2. 从 Redis 读取 key `session:user_a`
3. 如果存在，JSON 反序列化成 `messages` 列表
4. 如果不存在，返回 `None`
5. 如果 Redis 报错，走降级路径（返回内存字典）

### 输出

**第一次访问**（新会话）：
```python
None
```

**第二次访问**（已有历史）：
```python
[
  {"role": "system", "content": "你是一个智能查询助手..."},
  {"role": "user", "content": "上海天气怎么样"},
  {"role": "assistant", "content": None, "tool_calls": [...]},
  {"role": "tool", "tool_call_id": "...", "content": "上海对应的adcode是310000"},
  ...
]
```

### 技术解释
- **Redis 是内存数据库**：读写速度微秒级，适合存会话
- **TTL（Time To Live）**：用 `setex` 设置的过期时间，24 小时后自动删除，避免内存爆掉
- **熔断器（Circuit Breaker）**：Redis 连续失败 3 次后，30 秒内不再尝试，直接走降级，防止每个请求都卡 0.5 秒

### 对应代码
```python
# session_store.py
def get_session(session_id):
    if _is_circuit_open():                    # 熔断器检查
        return _fallback.get(session_id)
    try:
        data = redis_client.get(_key(session_id))
        _record_success()
        if data is None:
            return None
        return json.loads(data)               # 反序列化
    except Exception as e:
        _record_failure()                     # 记录失败
        return _fallback.get(session_id)      # 降级
```

### 行业术语
- **Session Store**：会话存储
- **TTL**：过期时间
- **Circuit Breaker**：熔断器（微服务架构的标准组件）
- **Graceful Degradation**：优雅降级
- **Fallback**：降级方案

### 生产环境差异
| 维度 | 开发环境 | 生产环境 |
| :--- | :--- | :--- |
| **Redis** | 单机 Docker | Redis Cluster / 哨兵模式 |
| **持久化** | 无 | AOF + RDB 双保险 |
| **序列化** | JSON | MessagePack / Protobuf（更快更小） |
| **多进程** | 内存字典兜底 | 分布式会话服务 |
| **安全** | 无密码 | 密码 + 内网隔离 |

### 生产环境常见问题
1. **会话丢失**：Redis 没配持久化，重启后数据全丢
2. **内存爆掉**：会话永不过期，用户多了 Redis OOM
3. **序列化不兼容**：不同版本的数据结构变了，反序列化报错
4. **热点 Key**：某个用户的会话特别长，单节点压力大

---

## 【第3步】第一次调用大模型

### 输入
`messages` 列表（system + user + 历史），加上工具定义：
```python
messages = [
    {"role": "system", "content": "你是一个智能查询助手..."},
    {"role": "user", "content": "上海天气怎么样"}
]
tools = [ {...get_weather...}, {...get_adcode...}, {...get_embedding...}, {...get_date...} ]
```

### 处理
1. 把 `messages` 和 `tools` 序列化成 JSON
2. 通过 HTTPS 发给硅基流动的 API
3. 硅基流动的 GPU 上跑 DeepSeek-V3.2
4. 模型内部：**自注意力机制**处理输入，**预测下一个 Token**，生成响应

### 输出
两种可能：

**情况 A：模型决定调用工具**
```python
res.choices[0].message.tool_calls = [
    ChatCompletionMessageFunctionToolCall(
        id='call_abc123',
        function=Function(name='get_adcode', arguments='{"city_name": "上海"}')
    )
]
res.choices[0].message.content = "我来帮您查询上海天气"
```

**情况 B：模型直接回答**
```python
res.choices[0].message.tool_calls = None
res.choices[0].message.content = "上海今天晴，25度"
```

### 技术解释
- **Function Calling**：模型根据用户问题和工具描述，决定是否调用工具。返回的是**调用指令**，不是执行结果
- **前缀缓存**：System Prompt + tools 定义如果不变，平台会缓存，第二次请求会快很多
- **Token 计费**：`prompt_tokens` 是输入消耗，`completion_tokens` 是输出消耗

### 对应代码
```python
# main.py
res = client.chat.completions.create(
    messages=messages,
    model='deepseek-ai/DeepSeek-V3.2',
    tools=tools,
    tool_choice='auto'          # auto = 模型自己决定是否调用工具
)
tool_calls = res.choices[0].message.tool_calls
```

### 行业术语
- **Function Calling**：函数调用
- **Tool Use**：工具使用
- **Tool Router**：工具路由（模型决定调哪个工具）
- **Prefix Caching**：前缀缓存
- **Prompt Tokens / Completion Tokens**：输入/输出 Token

### 生产环境差异
| 维度 | 开发环境 | 生产环境 |
| :--- | :--- | :--- |
| **模型** | DeepSeek-V3.2 | 多模型路由（小模型做简单任务） |
| **平台** | 硅基流动 | 官方 API / 多云容灾 |
| **缓存** | 平台自动 | 自建语义缓存（Semantic Cache） |
| **超时** | 默认 | 显式设置（如 30s） |
| **重试** | 无 | 指数退避重试 |

### 生产环境常见问题
1. **API 限流**：请求量太大，被平台 429
2. **模型幻觉**：模型不调用工具直接编答案
3. **成本失控**：长对话 Token 飙升，一次对话几块钱
4. **供应商故障**：平台挂了，服务全挂
5. **上下文超长**：messages 超过 128K，请求被拒

---

## 【第4步】判断 tool_calls 是否存在

### 输入
`tool_calls`（可能为 None，可能是列表）

### 处理
```python
if tool_calls:      # 有工具调用 → 进入循环
    ...进入第5步
else:               # 无工具调用 → 直接生成回答
    ...跳到第9步
```

### 输出
一个分支决策。

### 技术解释
这是 **ReAct 循环的入口判断**。ReAct = Reasoning + Acting，模型先"思考"要不要行动，如果要行动就返回 `tool_calls`，如果不需要就直接回答。

### 对应代码
```python
# main.py
while tool_calls and steps < max_steps:
    # ...循环体...
```

### 行业术语
- **ReAct Loop**：ReAct 循环
- **Agent Loop**：Agent 主循环
- **Termination Condition**：终止条件（这里是 `tool_calls` 为空）

### 生产环境差异
生产环境会额外判断：
- **步数上限**：`max_steps=10` 防止死循环
- **Token 预算**：单次对话超过 10 万 Token 强制停止
- **时间预算**：超过 60 秒强制停止

---

## 【第5步】并行执行工具

### 输入
```python
tool_calls = [
    {"id": "call_1", "function": {"name": "get_adcode", "arguments": '{"city_name": "上海"}'}},
    {"id": "call_2", "function": {"name": "get_adcode", "arguments": '{"city_name": "北京"}'}}
]
```

### 处理
1. 先追加 `assistant` 消息（包含 tool_calls）
2. 用 `ThreadPoolExecutor` 并发执行每个工具
3. 每个工具内部：解析参数 → 执行 Python 函数 → 返回结果

以 `get_adcode("上海")` 为例：
1. 调用高德地图 API `https://restapi.amap.com/v3/config/district`
2. 传入 `key` 和 `keywords=上海`
3. 拿到 JSON 响应，提取 `adcode`

### 输出
```python
tool_results = {
    "call_1": "上海对应的adcode是310000",
    "call_2": "北京对应的adcode是110000"
}
```

### 技术解释
- **ThreadPoolExecutor**：Python 线程池，适合 IO 密集任务（HTTP 请求）
- **为什么能并发**：`requests.get()` 会释放 GIL，多个线程能真正并行
- **依赖问题**：如果两个工具有依赖关系（一个的输出是另一个的输入），不能并发

### 对应代码
```python
# main.py
tool_calls_dict = [tc.model_dump() for tc in tool_calls]
messages.append({'role':'assistant','content':None,'tool_calls':tool_calls_dict})

with ThreadPoolExecutor(max_workers=len(tool_calls)) as executor:
    future_to_call = {executor.submit(execute_one_tool, tc, knowledge_list): tc for tc in tool_calls}
    for future in as_completed(future_to_call):
        tc_id, content = future.result()
        tool_results[tc_id] = content

# execute_one_tool 内部
def execute_one_tool(tool_call, knowledge_list):
    name = tool_call.function.name
    args = json.loads(tool_call.function.arguments)
    if name == 'get_adcode':
        adcode_dict = get_adcode(args['city_name'])
        result_content = f"{adcode_dict['city_name']}对应的adcode是{adcode_dict['adcode']}"
    # ...
    return tool_call.id, result_content
```

### 行业术语
- **Tool Execution**：工具执行
- **Parallel Tool Calling**：并行工具调用
- **Concurrency**：并发
- **Tool Node**：工具节点（LangGraph 里的概念）

### 生产环境差异
| 维度 | 开发环境 | 生产环境 |
| :--- | :--- | :--- |
| **执行** | 本地线程池 | Celery / 消息队列（异步任务） |
| **失败处理** | 无 | 重试 + 熔断 + 降级 |
| **限流** | 无 | 每个工具独立的限流器 |
| **缓存** | 无 | 工具结果缓存（如天气缓存 5 分钟） |
| **超时** | 无 | 每个工具设置超时（如 5s） |

### 生产环境常见问题
1. **工具挂掉**：高德 API 挂了，整个请求失败
2. **工具慢**：某个工具卡 30 秒，整个请求被拖垮
3. **工具限流**：高德 API 有 QPS 限制，并发太多被拒
4. **参数错误**：模型传的参数格式不对，工具报错
5. **权限问题**：工具需要用户授权，但没传 token

---

## 【第6步】工具结果追加到 messages

### 输入
```python
tool_results = {"call_1": "上海对应的adcode是310000"}
tool_calls = [...]  # 来自第3步
```

### 处理
遍历 `tool_calls`，为每个工具构造一条 `tool` 消息，追加到 `messages`：
```python
for tc in tool_calls:
    messages.append({
        'role': 'tool',
        'tool_call_id': tc.id,
        'content': tool_results[tc.id]
    })
```

### 输出
`messages` 列表新增了 `tool` 消息：
```python
messages = [
    {"role": "system", ...},
    {"role": "user", "content": "上海天气怎么样"},
    {"role": "assistant", "content": None, "tool_calls": [...]},
    {"role": "tool", "tool_call_id": "call_1", "content": "上海对应的adcode是310000"}
]
```

### 技术解释
**消息顺序是强制的**：OpenAI API 规定，`tool` 消息必须跟在对应的 `assistant(tool_calls)` 之后。顺序错了会报 400 错误。

**为什么必须遵守**：API 通过 `tool_call_id` 把"工具调用指令"和"工具执行结果"配对。如果顺序乱了，API 不知道这条 tool 消息对应哪条调用。

### 对应代码
```python
# main.py
for tc in tool_calls:
    messages.append({
        'role': 'tool',
        'tool_call_id': tc.id,
        'content': tool_results[tc.id]
    })
```

### 行业术语
- **Message Role**：消息角色（system/user/assistant/tool）
- **Message History**：消息历史
- **Conversation Context**：对话上下文

### 生产环境差异
生产环境会：
- **裁剪历史**：只保留最近 N 条（你用的是 `messages[-20:]`）
- **压缩历史**：把早期对话总结成一段话（Summary）
- **淘汰历史**：把早期对话向量化，需要时再检索

---

## 【第7步】第二次调用大模型

### 输入
更新后的 `messages`（包含了工具结果）+ `tools` 定义

### 处理
再次调用大模型 API。这次模型能看到工具执行结果，决定：
- 继续调用工具（如果还需要更多信息）
- 生成最终回答（如果信息已足够）

### 输出

**情况 A：继续调用工具**
```python
tool_calls = [
    {"id": "call_3", "function": {"name": "get_weather", "arguments": '{"city_adcode": "310000"}'}}
]
content = "现在我可以查询上海天气了"
```

**情况 B：生成最终回答**
```python
tool_calls = None
content = "上海今天多云，温度29度，东南风，风级≤3级。"
```

### 技术解释
**为什么需要第二次调用**：模型第一次只能"决定调用什么工具"，它**看不到工具的执行结果**。必须把结果喂回去，模型才能基于事实生成回答。

这是 ReAct 循环的**核心机制**：思考 → 行动 → 观察 → 再思考。

### 对应代码
```python
# main.py
res = client.chat.completions.create(
    model='deepseek-ai/DeepSeek-V3.2',
    messages=messages,     # 已包含工具结果
    tools=tools,
    tool_choice='auto'
)
tool_calls = res.choices[0].message.tool_calls
```

### 行业术语
- **Observation**：观察（ReAct 的三要素之一）
- **Tool Result Feedback**：工具结果反馈
- **Multi-Turn Reasoning**：多轮推理

### 生产环境差异
- **流式输出**：第二次调用开始用 streaming，用户体验更好
- **Token 预算**：控制 messages 长度，防止超限

---

## 【第8步】循环判断

### 输入
新的 `tool_calls` + `steps` 计数

### 处理
```python
if not tool_calls:
    # 跳出循环，生成最终答案
    break
steps += 1
# 否则继续下一轮
```

### 输出
- **跳出循环** → 进入第9步
- **继续循环** → 回到第5步

### 技术解释
**循环终止条件**：
1. 模型不再返回 `tool_calls`（任务完成）
2. `steps >= max_steps`（防死循环）
3. 超过 Token 预算（生产环境）
4. 超过时间预算（生产环境）

### 对应代码
```python
# main.py
max_steps = 10
steps = 0
while tool_calls and steps < max_steps:
    # ...
    tool_calls = res.choices[0].message.tool_calls
    if not tool_calls:
        final_answer = res.choices[0].message.content
        messages.append({'role':'assistant','content':final_answer})
        break
    steps += 1
```

### 行业术语
- **Loop Termination**：循环终止
- **Max Steps / Max Iterations**：最大步数
- **Circuit Breaker**：熔断（和 Redis 那个不同，这里指防止死循环）

### 生产环境常见问题
1. **死循环**：模型反复调用同一个工具
2. **无限增长**：每轮都追加消息，messages 越来越长
3. **成本爆炸**：10 轮调用下来，Token 消耗几万

---

## 【第9步】保存会话到 Redis

### 输入
完整的 `messages` 列表（包含所有历史）

### 处理
1. 裁剪：只保留最近 20 条（`messages[-MAX_MESSAGES:]`）
2. 序列化成 JSON 字符串
3. 写入 Redis，设置 24 小时 TTL

### 输出
Redis 里新增/更新了一个 key：
```
key: session:user_a
value: "[{\"role\":\"system\",...},...]"
TTL: 86400 秒
```

### 技术解释
- **为什么裁剪**：messages 会无限增长，不裁剪会爆 Token
- **为什么用 TTL**：防止僵尸会话占用内存
- **为什么存 Redis**：跨重启保留、跨进程共享、自动过期

### 对应代码
```python
# session_store.py
def save_session(session_id, messages):
    trimmed = messages[-MAX_MESSAGES:]      # 裁剪
    if _is_circuit_open():
        _fallback[session_id] = trimmed
        return
    try:
        redis_client.setex(
            name=_key(session_id),
            time=SESSION_TTL,                 # 24小时
            value=json.dumps(trimmed, ensure_ascii=False)
        )
        _record_success()
    except Exception as e:
        _record_failure()
        _fallback[session_id] = trimmed
```

### 行业术语
- **Session Persistence**：会话持久化
- **State Management**：状态管理
- **TTL**：过期时间
- **Eviction Policy**：淘汰策略

### 生产环境差异
| 维度 | 开发环境 | 生产环境 |
| :--- | :--- | :--- |
| **存储** | 单机 Redis | Redis Cluster |
| **裁剪** | 固定 20 条 | 动态裁剪（按 Token 数） |
| **压缩** | 无 | 历史摘要 + 向量化 |
| **加密** | 无 | 敏感字段加密 |

---

## 【第10步】返回 JSON 响应

### 输入
`final_answer` 字符串（最终回答）

### 处理
FastAPI 把它包装成 `ChatResponse` 对象，序列化成 JSON，通过 HTTP 返回。

### 输出
```json
{
    "answer": "上海今天多云，温度29度，东南风，风级≤3级。",
    "steps": 0
}
```

### 技术解释
- **Pydantic 序列化**：`ChatResponse` 对象自动转成 JSON
- **HTTP 状态码**：成功返回 200，出错返回 500/422/404

### 对应代码
```python
# main.py
class ChatResponse(BaseModel):
    answer: str
    steps: int

@app.post('/chat', response_model=ChatResponse)
async def chat(request: ChatRequest):
    answer = run_agent(request.message, request.session_id)
    return ChatResponse(answer=answer, steps=0)
```

### 行业术语
- **Response Model**：响应模型
- **Serialization**：序列化
- **API Response**：接口响应

### 生产环境差异
- **流式响应（SSE）**：逐 Token 返回，用户体验好
- **响应压缩**：gzip 压缩，减少带宽
- **缓存响应**：相同问题直接返回缓存
- **错误码标准化**：4001/5001 等业务错误码

---

## 完整流程图（带输入输出）

```
┌──────────────────────────────────────────────────────────────────┐
│                        用户提问                                  │
│  POST /chat {"message": "上海天气怎么样", "session_id": "user_a"} │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ 【第1步】FastAPI 接收请求                                        │
│  输入：HTTP 请求                                                 │
│  输出：ChatRequest 对象                                          │
│  技术：HTTP 解析 + Pydantic 校验                                 │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ 【第2步】加载会话历史                                            │
│  输入：session_id = "user_a"                                     │
│  输出：messages 列表 或 None                                     │
│  技术：Redis 读取 + 熔断器 + 降级                                 │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ 【第3步】第一次调用大模型                                        │
│  输入：messages + tools                                          │
│  输出：tool_calls（get_adcode("上海")）                          │
│  技术：Function Calling + 自注意力 + 前缀缓存                    │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ 【第4步】判断 tool_calls                                         │
│  有 → 进入循环 / 无 → 直接回答                                   │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ 【第5步】并行执行工具                                            │
│  输入：tool_calls 列表                                           │
│  输出：tool_results 字典                                         │
│  技术：ThreadPoolExecutor + HTTP 请求                            │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ 【第6步】追加 tool 消息                                          │
│  输入：tool_results                                              │
│  输出：更新后的 messages                                         │
│  技术：消息顺序规范（assistant → tool）                          │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ 【第7步】第二次调用大模型                                        │
│  输入：更新后的 messages + tools                                 │
│  输出：新的 tool_calls 或最终回答                                │
│  技术：多轮推理                                                  │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ 【第8步】循环判断                                                │
│  还有 tool_calls → 回到第5步                                     │
│  没有 → 跳出循环                                                 │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ 【第9步】保存会话                                                │
│  输入：完整 messages                                             │
│  输出：Redis 写入成功                                            │
│  技术：裁剪 + 序列化 + TTL                                       │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ 【第10步】返回响应                                               │
│  输入：final_answer                                              │
│  输出：{"answer": "...", "steps": 0}                            │
│  技术：Pydantic 序列化                                           │
└──────────────────────────────────────────────────────────────────┘
                              ↓
                         用户看到回答
```

---

## 关键技术总结

| 步骤 | 核心技术 | 行业术语 | 生产环境挑战 |
| :--- | :--- | :--- | :--- |
| 第1步 | FastAPI + Pydantic | RESTful API | 限流、认证、多进程 |
| 第2步 | Redis + 熔断器 | Session Store | 集群、持久化、加密 |
| 第3步 | Function Calling | Tool Router | 幻觉、成本、限流 |
| 第4步 | ReAct 入口 | Termination Condition | 死循环防护 |
| 第5步 | ThreadPoolExecutor | Parallel Tool Calling | 工具熔断、超时 |
| 第6步 | 消息规范 | Message History | 上下文裁剪 |
| 第7步 | 多轮推理 | Observation | Token 预算 |
| 第8步 | 循环控制 | Max Iterations | 成本控制 |
| 第9步 | Redis 持久化 | State Management | 分布式存储 |
| 第10步 | 响应序列化 | API Response | 流式输出 |

---

## 你的代码在生产环境还缺什么？

| 缺失 | 影响 | 补充方案 |
| :--- | :--- | :--- |
| **多进程部署** | 单进程 QPS 低 | Gunicorn + Uvicorn Worker |
| **认证机制** | 谁都能调用 | JWT / API Key |
| **限流** | 恶意刷接口 | Redis 令牌桶 |
| **日志** | 出问题无法排查 | Structured Logging |
| **监控** | 不知道系统状态 | Prometheus + Grafana |
| **追踪** | 不知道哪一步慢 | LangSmith / OpenTelemetry |
| **成本控制** | Token 烧钱 | 预算熔断 |
| **工具熔断** | 工具挂了整个服务挂 | 每个工具独立的熔断器 |
| **流式输出** | 用户体验差 | SSE / WebSocket |
| **多模型路由** | 大材小用 | 小模型做简单任务 |

---

## 一句话总结

> **你的 Agent 走完了一个完整的 ReAct 循环：用户提问 → 加载历史 → 模型决策 → 执行工具 → 反馈结果 → 再决策 → 生成回答 → 保存历史 → 返回结果。**
> **每一步都有对应的行业术语、技术原理、生产环境差异。**
> **你已经手写了一个"生产级内核"——只是缺"生产级外壳"（多进程、监控、限流、认证）。**

---
