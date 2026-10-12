# 招聘简历筛选 Agent

> 基于 RAG + ReAct 的生产级 AI Agent，帮助 HR 快速筛选候选人。

## 🎯 业务场景

HR 每天收到大量简历，人工筛选效率低，容易漏掉合适候选人。本 Agent 支持：

- 按技能筛选：「有没有会 Python 的候选人？」
- 按经验年限筛选：「筛选 3 年以上经验的」
- 复合条件：「5 年以上 Python + Docker」
- 候选人对比：「张三和李四谁更适合后端？」
- **幻觉抑制**：知识库没有的技能，明确说"未找到"，不编造

## ✨ 核心能力

| 能力 | 实现 |
| :--- | :--- |
| **手写 ReAct 循环** | 不依赖 LangChain，`while tool_calls` 自主循环 |
| **混合检索** | 向量 + BM25 + RRF + Reranker，**Hit@3 = 100%，MRR = 1.000** |
| **元数据预过滤** | 硬约束（日期/序号）优先过滤 |
| **智能分块** | 按文档结构路由（编号/标题/段落）+ 纯标题块合并 |
| **通用关键词过滤** | 用 jieba POS 标注提取实词，**零硬编码** |
| **幻觉抑制** | Prompt 约束 + NO_RESULT 标记 + 代码层过滤 |
| **多用户隔离** | session_id + Redis，24h TTL |
| **熔断降级** | Redis 挂了自动切内存字典 |
| **Docker 部署** | docker-compose 一键启动 |
| **外网穿透** | ngrok 固定域名 |

## 🛠 技术栈

| 组件 | 服务商 / 库 | 用途 |
| :--- | :--- | :--- |
| 对话模型 | DeepSeek 官方 API（`deepseek-flash`，V4.1） | ReAct 循环 |
| Embedding | Qwen3-Embedding-4B（硅基流动） | 向量检索 |
| Reranker | bge-reranker-v2-m3（硅基流动） | 精排 |
| 关键词检索 | rank-bm25 + jieba | BM25 检索 |
| Web 框架 | FastAPI + uvicorn | HTTP 服务 |
| 会话存储 | Redis（Docker 容器） | 多用户隔离 |
| 部署 | Docker + docker-compose | 容器化 |

## 🚀 快速开始

### 1. 配置环境变量

在项目根目录创建 `.env`：

```env
DEEPSEEK_API_KEY=sk-你的deepseek密钥
SILICONFLOW_API_KEY=你的硅基流动密钥
AMAP_KEY=你的高德地图密钥
```

### 2. 启动服务

```bash
docker-compose up --build -d
```

### 3. 访问

浏览器打开 `http://localhost:8000`

## 📊 效果演示

**测试 1：按技能筛选**
> 用户：有没有会 Python 的候选人？
> 
> Agent：找到 6 位会 Python 的候选人：
> 1. 钱七（精通）  2. 吴十（熟练）  3. 王五（精通）
> 4. 张三（精通）  5. 周九（熟练）  6. 孙八（熟练）

**测试 2：幻觉抑制**
> 用户：有没有会 Rust 的候选人？
> 
> Agent：简历库中未找到明确提到 Rust 技能的候选人。

**测试 3：复合条件**
> 用户：找 5 年以上 Python 经验、熟悉 Docker 的候选人
> 
> Agent：找到 4 位：王五（7年）、张三（5年）、孙八（6年）、吴十（8年）

**测试 4：候选人对比**
> 用户：张三和李四哪个更适合后端岗位？
> 
> Agent：**张三更适合**。依据：1) 5年 vs 3年；2) 高级 vs 中级；3) Python + Go 双栈 vs Java 单栈；4) 熟悉 K8s。

## 📈 评估结果

```bash
python test_rag.py
```

```
Hit@3: 8/8 = 100.0%
MRR:   1.000
```

- **Hit@3**：前 3 名命中率
- **MRR**：平均倒数排名（1.000 = 每次都排第 1）

## 💡 技术亮点

### 1. 手写 ReAct 循环

```python
while tool_calls and steps < max_steps:
    messages.append({'role':'assistant','content':None,'tool_calls':tool_calls_dict})
    with ThreadPoolExecutor() as executor:
        ...
    messages.append({'role':'tool','tool_call_id':tc.id,'content':result})
    res = client.chat.completions.create(messages=messages, tools=tools)
    tool_calls = res.choices[0].message.tool_calls
```

### 2. 混合检索

向量检索（语义）+ BM25（关键词）→ RRF 融合 → Reranker 精排。

### 3. 通用关键词过滤（无硬编码）

用 jieba POS 标注提取实词（英文词 + 名词），检查是否在知识库出现。**不需要任何技能词典**。

### 4. 幻觉抑制三层防御

| 层级 | 手段 |
| :--- | :--- |
| Prompt 层 | "禁止推测"、"未找到就说未找到" |
| 系统标记层 | `retrieve` 返回 None → `【系统标记:NO_RESULT】` |
| 代码层 | POS 关键词过滤 |

### 5. 熔断降级

Redis 连续失败 3 次 → 熔断 30 秒 → 走内存字典。

## 📁 项目结构

```
first_agent/
├── main.py              # FastAPI + run_agent
├── prompt.py            # System Prompt + tools
├── knowledge.py         # RAG 检索
├── session_store.py     # Redis + 熔断器
├── func_tools.py        # 工具函数
├── config_file.py       # 配置
├── knowledge_base/      # 简历库
├── static/              # 前端
├── test_rag.py          # 评估脚本
├── Dockerfile
└── docker-compose.yml
```

## 📝 License

MIT