# AI Agent 应用落地实战学习计划（脱产版）


## 一、整体思路

按照“**用户提问题 → Agent内部处理 → 输出答案**”这条完整链路，我把整个学习过程拆解为**8个阶段、30天脱产计划**。核心理念是：**每天跑通一个可运行的案例**，案例的哪一段对应哪个技术环节，一目了然。

**学习原则**：理论学习与代码实践比例 **3:7**——先看10分钟原理，然后立刻动手写代码。绝不只看文档不动手。

**推荐技术栈**：Python 3.10+、LangChain / LangGraph、DeepSeek / Qwen 等国产模型（注册即送额度）。


## 二、一个完整Agent应用的完整流程

在开始之前，先理解一个Agent从用户提问到输出答案的完整链路：

```
用户提问 → 输入理解与Prompt组装 → 模型推理（规划）→ 工具调用判断 
    → 执行工具 → 观察结果 → 反思/再规划 → 生成最终答案 → 输出给用户
```

这个循环在Agent领域叫做 **ReAct（Reasoning + Acting）循环**——思考→行动→观察→再思考，直到任务完成。

整个学习计划就是围绕这个流程，从零开始逐块搭建。


## 三、30天脱产学习计划

### 📌 阶段零：环境准备与认知（第1天）

**目标**：跑通第一个Agent，理解整体流程

| 时间段 | 内容 | 案例/材料 |
|--------|------|-----------|
| 上午 | 搭建Python环境、配置API密钥 | [ai-agent-handbook 第0章](https://github.com/Xwh630/ai-agent-handbook) — 10分钟跑通第一个Agent |
| 下午 | 运行一个最小ReAct Agent（不到50行代码） | [learn-claude-code](https://developer.aliyun.com/article/1662362) — 50行Python实现ReAct范式 |

**对应完整流程的哪一段**：整条链路的最小闭环——用户输入 → 模型思考 → 输出答案。

**今日产出**：一个能回答简单问题并调用1个工具（如天气查询）的Agent。


### 📌 阶段一：LLM基础与Prompt工程（第2-4天）

**目标**：理解大模型如何理解用户输入、如何通过Prompt控制输出

| 天数 | 内容 | 案例/材料 |
|------|------|-----------|
| 第2天 | API调用、基础问答、结构化输出 | [ai-agent-startup 阶段1](https://github.com/EldonZhao/ai-agent-startup) — 用API做问答、数据结构化 |
| 第3天 | Chain-of-Thought（CoT）思维链 | 手写Prompt让模型展示推理步骤 |
| 第4天 | 复杂Prompt设计（角色设定、格式约束） | 做一个“数据结构化提取器”——输入一段文字，输出JSON |

**对应完整流程的哪一段**：`用户提问 → 结构化Prompt组装 → 模型推理`

**今日产出**：一个能按要求输出结构化数据的问答工具。


### 📌 阶段二：工具调用 / Function Calling（第5-7天）

**目标**：让Agent能调用外部工具（这是Agent区别于普通Chatbot的核心）

| 天数 | 内容 | 案例/材料 |
|------|------|-----------|
| 第5天 | Function Calling原理 + 定义第一个工具 | [AI Agent开发完全指南](https://ofox.ai) — Function Calling原理与工具定义 |
| 第6天 | 多工具注册与调用（天气+汇率+计算器） | [ai-agent-startup 阶段2](https://github.com/EldonZhao/ai-agent-startup) — 聚合多工具的Agent小项目 |
| 第7天 | 工具调用错误处理与重试 | [从零构建AI Agent：基于LangGraph](https://developer.aliyun.com/article/1691144) — 失败重试机制 |

**对应完整流程的哪一段**：`模型推理 → 工具调用判断 → 执行工具 → 观察结果`

**今日产出**：一个能调用3种以上工具的Agent（如“帮我查一下北京天气然后换算成美元”）。


### 📌 阶段三：ReAct循环与多步推理（第8-11天）

**目标**：理解Agent的核心循环——思考→行动→观察→再思考

| 天数 | 内容 | 案例/材料 |
|------|------|-----------|
| 第8天 | 手写ReAct循环（不依赖框架） | [awesome-agent-tutorial 第2章](https://github.com/cdavid817/awesome-agent-tutorial) — 不到40行代码的最小ReAct Loop |
| 第9天 | 理解Agent Loop的终止条件与预算控制 | [awesome-agent-tutorial 第3章](https://github.com/cdavid817/awesome-agent-tutorial) — Agentic Loop解剖 |
| 第10天 | 任务分解与多步规划 | [ai-agent-startup 阶段3](https://github.com/EldonZhao/ai-agent-startup) — 自动收集资料/多步骤办公助手 |
| 第11天 | 完整的多步推理Agent | [从零构建ReAct智能体](https://cloud.tencent.com/developer/article/2571495) — 完整实现 |

**对应完整流程的哪一段**：`模型推理 → 工具调用 → 观察 → 反思/再规划 → ...（循环直到完成）`

**今日产出**：一个能自主完成多步骤任务的Agent（如“帮我搜集某公司近3年的融资信息并整理成报告”）。


### 📌 阶段四：记忆与RAG知识库（第12-16天）

**目标**：让Agent拥有“记忆力”和“知识库”

| 天数 | 内容 | 案例/材料 |
|------|------|-----------|
| 第12天 | 短期记忆（对话历史管理） | [从零构建具备规划与记忆能力的自主智能体](https://cloud.tencent.com/developer/article/2576354) |
| 第13天 | Embedding + 向量数据库入门 | 用ChromaDB做文本向量存储与检索 |
| 第14天 | RAG完整流程（检索→增强→生成） | [从零搭建企业级RAG知识库](https://cloud.tencent.com/developer/article/2603191) — LangChain+Qwen+Chroma |
| 第15天 | Agentic RAG（Agent自主决定是否检索、如何检索） | [Agentic RAG with LangGraph](https://developer.aliyun.com/article/1664903) — 自动修正检索错误 |
| 第16天 | 长期记忆系统（Mem0等） | [ai-agent-startup 阶段4](https://github.com/EldonZhao/ai-agent-startup) — 个人笔记/知识问答Agent |

**对应完整流程的哪一段**：`用户提问 → 检索记忆/知识库 → 增强Prompt → 模型推理`（记忆贯穿整个流程）

**今日产出**：一个能“记住”历史对话、能检索私有文档知识库的Agent。


### 📌 阶段五：多Agent协同（第17-20天）

**目标**：让多个Agent分工协作，完成复杂任务

| 天数 | 内容 | 案例/材料 |
|------|------|-----------|
| 第17天 | 多Agent模式概述（Manager-Worker、专家小组） | [ai-agent-startup 阶段5](https://github.com/EldonZhao/ai-agent-startup) |
| 第18天 | Supervisor模式 + 消息队列 | [AgentGuide](https://github.com/zgd716/AgentGuide) — 3个专业Agent协同工作 |
| 第19天 | LangGraph多Agent编排 | [langchain-langgraph-tutorial](https://github.com/ShadowQuill/langchain-langgraph-tutorial) — 9个Phase、26个可运行示例 |
| 第20天 | 完整多Agent项目 | 模拟“需求分析师→预算规划师→行程执行者”协作流 |

**对应完整流程的哪一段**：复杂任务被拆解后，`多个Agent各自执行子任务 → 汇总结果 → 输出`

**今日产出**：一个由3个以上Agent协作完成任务的系统。


### 📌 阶段六：主流框架实战（第21-25天）

**目标**：用成熟框架快速构建生产级应用

| 天数 | 内容 | 案例/材料 |
|------|------|-----------|
| 第21天 | LangChain核心组件（LCEL、Chain） | [LangChain + DeepSeek实战拆解](https://bbs.huaweicloud.com/blogs/453278) |
| 第22天 | LangGraph状态图与条件边 | [LangGraph快速入门实战](https://cloud.tencent.com/developer/article/2613668) |
| 第23天 | LangGraph + 多工具 + 记忆（完整项目） | [从零构建AI Agent：基于LangGraph](https://developer.aliyun.com/article/1691144) — 开箱即用 |
| 第24天 | Dify低代码平台 | [ai-agent-handbook 第7章](https://github.com/Xwh630/ai-agent-handbook) — Dify可视化拖拽 |
| 第25天 | 框架对比与选型 | 用同一场景分别用LangChain、LangGraph、Dify实现，对比优劣 |

**对应完整流程的哪一段**：完整流程的框架化实现——所有环节都用框架的标准组件完成。

**今日产出**：用至少2种框架实现同一个Agent应用。


### 📌 阶段七：工程化、评估与部署（第26-30天）

**目标**：让Agent从“能跑”变成“生产可用”

| 天数 | 内容 | 案例/材料 |
|------|------|-----------|
| 第26天 | API服务化（FastAPI封装Agent） | [ai-agent-startup 阶段7](https://github.com/EldonZhao/ai-agent-startup) — API服务化、日志 |
| 第27天 | Agent评估（测试用例、LLM-as-Judge） | [agent-study 第6章](https://github.com/Callous-0923/agent-study) — 评估维度与单元测试 |
| 第28天 | 可观测性（LangSmith追踪） | [LangSmith](https://docs.langchain.com) — 追踪Agent每一步执行 |
| 第29天 | 安全与成本控制 | 预算熔断、权限控制、成本监控 |
| 第30天 | **毕业项目**：端到端完整Agent产品 | 从用户输入到最终输出，覆盖全部环节 |

**对应完整流程的哪一段**：完整流程 + 运维保障（监控、评估、安全、成本）

**今日产出**：一个可部署、可监控、可评估的完整Agent产品。


## 四、推荐的核心学习资源

### 首选资源（有完整代码、可直接运行）

| 资源 | 特点 | 适合阶段 |
|------|------|----------|
| [ai-agent-startup](https://github.com/EldonZhao/ai-agent-startup) | 8阶段系统路线，每阶段有代码示例 | 全部 |
| [awesome-agent-tutorial](https://github.com/cdavid817/awesome-agent-tutorial) | 27章，从150行ReAct到生产级系统 | 第1-30天 |
| [ai-agent-handbook](https://github.com/Xwh630/ai-agent-handbook) | 10+框架、23+章、零门槛 | 第0-25天 |
| [ai-agents-from-zero](https://github.com/didilili/ai-agents-from-zero) | 完整学习路径+实战项目+面试题库 | 全部 |
| [awesome-ai-agent-learning](https://github.com/2182977liu-bit/awesome-ai-agent-learning) | 不依赖框架从零构建，保姆级中文 | 第1-11天 |

### 按技术点查阅的实战文章

- **Function Calling原理**：[AI Agent开发完全指南](https://ofox.ai)
- **LangGraph实战**：[从零构建AI Agent](https://developer.aliyun.com/article/1691144)
- **RAG系统**：[从零搭建企业级RAG知识库](https://cloud.tencent.com/developer/article/2603191)
- **Agent评估**：[agent-study 第6章](https://github.com/Callous-0923/agent-study)


## 五、每日学习节奏（脱产版）

| 时间段 | 内容 | 说明 |
|--------|------|------|
| 09:00-09:30 | 回顾昨天 + 规划今天 | 5分钟跑通昨天代码，25分钟看今日目标 |
| 09:30-10:30 | 理论学习 | 阅读对应章节文档，理解原理（不超过1小时） |
| 10:30-12:00 | **动手写代码（第一轮）** | 照着案例敲一遍，确保跑通 |
| 14:00-16:00 | **动手写代码（第二轮）** | 脱离案例，自己重写一遍（这才是真正的学习） |
| 16:00-17:30 | 扩展/改造 | 给案例加一个新功能或换一个场景 |
| 17:30-18:00 | 复盘 + 记笔记 | 记录今天学到了完整流程的哪一段 |

**核心原则**：每天至少跑通**1个完整案例**，每周完成**1个小项目**。


## 六、里程碑检查点

| 时间 | 里程碑 | 检验方式 |
|------|--------|----------|
| 第7天 | 能调用多工具的Agent | 输入“北京天气+人民币汇率”，一次输出两个结果 |
| 第11天 | 能多步推理的Agent | 输入复杂任务，观察是否自主拆解并分步执行 |
| 第16天 | 带记忆和知识库的Agent | 问“我之前问过什么？”+“根据这份文档回答...” |
| 第20天 | 多Agent协作系统 | 3个Agent协同完成一个完整任务 |
| 第25天 | 用框架快速构建 | 2小时内用LangGraph搭出一个新Agent |
| 第30天 | 完整产品 | 部署上线，真实用户可用 |


> **最后提醒**：这个计划的核心不是“看完”，而是“跑通”。每一行代码都要亲手敲过，每一个案例都要自己运行过。说得很对——“**先理解原理，再学框架；先动手写，再学理论**”。如果某一天的内容太吃力，就放慢速度，多跑几遍案例，不要赶进度。祝你顺利落地你的第一个Agent应用！