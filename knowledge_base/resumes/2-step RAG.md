## 文档索引

获取完整文档索引：https://docs.langchain.com/llms.txt  
使用此文件可发现所有可用页面，便于后续深入探索。

---

# 检索（Retrieval）

大型语言模型（LLM）功能强大，但存在两个关键限制：

* **上下文有限**：无法一次性处理整个语料库。
* **知识静态**：训练数据冻结于某个时间点。

检索通过**在查询时获取相关外部知识**来解决这些问题。这是**检索增强生成（RAG）** 的基础，即用上下文特定信息来增强 LLM 的回答。

---

## 构建知识库

**知识库**是用于检索的文档或结构化数据的存储库。

如需自定义知识库，可使用 LangChain 的文档加载器和向量存储，基于自有数据构建。

<Note>
  如果您已有知识库（例如 SQL 数据库、文档数据库、CRM 或内部文档系统），则**无需**重新构建。您可以：

  * 在 **Agentic RAG** 中将其作为 **工具** 连接到 Agent。
  * 查询它并将检索到的内容作为上下文提供给 LLM（参见 [2-Step RAG](#2-step-rag)）。
</Note>

更多信息，请参阅以下教程，了解如何构建可搜索的知识库和最小 RAG 工作流：

### 教程：语义搜索
  学习如何使用 LangChain 的文档加载器、嵌入和向量存储，从自有数据构建可搜索的知识库。
  在本教程中，你将基于 PDF 构建一个搜索引擎，能够检索与查询相关的段落。你还将在此引擎之上实现一个最小 RAG 工作流，了解如何将外部知识融入 LLM 推理。
  了解更多(https://docs.langchain.com/oss/python/langchain/knowledge-base):即semantic_search-demo

### 从检索到 RAG

检索允许 LLM 在运行时访问相关上下文。但大多数实际应用更进一步：**将检索与生成集成**，以产生有依据的、上下文感知的回答。

这正是**检索增强生成（RAG）** 的核心思想。检索管道成为更广泛系统的基础，该系统将搜索与生成相结合。

### 检索管道

典型的检索工作流如下所示：

```mermaid actions={true} theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
%%{init: {'flowchart': {'nodeSpacing': 12, 'rankSpacing': 18, 'padding': 4}, 'themeVariables': {'fontSize': '12px'}}}%%
flowchart TB
  subgraph ingest[" "]
    direction LR
    S(["数据源<br>（Google Drive、Slack、Notion 等）"]) --> L[文档加载器]
    L --> A([文档])
  end
  A --> B[分块]
  B --> C[生成嵌入]
  C --> D[(向量存储)]
  Q([用户查询]) --> E[查询嵌入]
  E --> D
  D --> F[检索器]
  F --> G[LLM 使用检索信息]
  G --> H([回答])

  classDef trigger fill:#F6FFDB,stroke:#6E8900,stroke-width:2px,color:#2E3900
  classDef process fill:#E5F4FF,stroke:#006DDD,stroke-width:2px,color:#030710
  classDef output fill:#EBD0F0,stroke:#885270,stroke-width:2px,color:#441E33
  classDef neutral fill:#F2FAFF,stroke:#40668D,stroke-width:2px,color:#2F4B68

  class S,Q trigger
  class L,B,C,E,F,G process
  class D output
  class A,H neutral
```

每个组件都是模块化的：你可以自由替换加载器、分割器、嵌入模型或向量存储，而无需重写应用程序逻辑。

### 构建模块

#### 文档加载器
    从外部源（Google Drive、Slack、Notion 等）提取数据，返回标准化的 [`Document`](https://reference.langchain.com/python/langchain-core/documents/base/Document) 对象。
    了解更多（https://docs.langchain.com/oss/python/integrations/document_loaders）

#### 文本分割器
    将大型文档拆分为较小的块，以便单独检索并适应模型的上下文窗口。
    了解更多（https://docs.langchain.com/oss/python/integrations/splitters）

#### 嵌入模型
    嵌入模型将文本转换为数值向量，使语义相近的文本在向量空间中彼此靠近。
    了解更多（https://docs.langchain.com/oss/python/integrations/embeddings）

#### 向量存储
    专门用于存储和搜索嵌入向量的数据库。
    了解更多（https://docs.langchain.com/oss/python/integrations/retrievers/）

#### 检索器
    检索器是一个接口，根据非结构化查询返回文档。
    了解更多（https://docs.langchain.com/oss/python/integrations/retrievers/）

---

## RAG 架构

RAG 可根据系统需求以多种方式实现。我们在下文中概述每种类型。

| 架构           | 描述                                                                  | 控制度   | 灵活性   | 延迟     | 示例用例                             |
| -------------- | --------------------------------------------------------------------- | -------- | -------- | -------- | ------------------------------------ |
| **2-Step RAG** | 检索始终在生成之前执行。简单且可预测。                                | ✅ 高     | ❌ 低     | ⚡ 快速   | FAQ、文档机器人                      |
| **Agentic RAG**| LLM 驱动的 Agent 在推理过程中决定*何时*以及*如何*检索。              | ❌ 低     | ✅ 高     | ⏳ 可变   | 可访问多种工具的研究助手             |
| **混合型**     | 结合两种方法的特点，并加入验证步骤。                                  | ⚖️ 中等  | ⚖️ 中等  | ⏳ 可变   | 带质量验证的领域特定问答             |

<Info>
  **延迟**：**2-Step RAG** 的延迟通常更**可预测**，因为 LLM 调用的最大次数是已知且有上限的。这种可预测性假设 LLM 推理时间是主导因素。然而，实际延迟还可能受检索步骤的性能影响，例如 API 响应时间、网络延迟或数据库查询，具体取决于所使用的工具和基础设施。
</Info>

### 2-Step RAG

在 **2-Step RAG** 中，检索步骤始终在生成步骤之前执行。这种架构简单且可预测，适用于许多应用场景，其中检索相关文档是生成答案的明确前提。

```mermaid actions={true} theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
%%{init: {'flowchart': {'nodeSpacing': 12, 'rankSpacing': 18, 'padding': 4}, 'themeVariables': {'fontSize': '12px'}}}%%
graph TB
    A[用户问题] --> B["检索相关文档"]
    B --> C["生成答案"]
    C --> D[向用户返回答案]

    %% 样式
    classDef startend fill:#F6FFDB,stroke:#6E8900,stroke-width:2px,color:#2E3900
    classDef process fill:#E5F4FF,stroke:#006DDD,stroke-width:1.5px,color:#030710

    class A,D startend
    class B,C process
```

<br />

#### 教程：语义搜索
    使用文档加载器、嵌入和向量存储构建可搜索的知识库，然后在其上运行一个最小的“检索-生成”RAG 工作流。了解更多（https://docs.langchain.com/oss/python/langchain/knowledge-base）


#### 教程：评估 RAG 应用
    构建一个简单的“检索-生成”RAG 应用，并使用 LangSmith 评估答案正确性、相关性、依据性和检索质量。了解更多（https://docs.langchain.com/oss/python/langchain/knowledge-base）


### Agentic RAG

**Agentic 检索增强生成（RAG）** 结合了 RAG 的优势与基于 Agent 的推理能力。Agent（由 LLM 驱动）不是先检索再回答，而是逐步推理，并在交互过程中决定**何时**以及**如何**检索信息。

<Tip>
  Agent 启用 RAG 行为的唯一要求是能够访问一个或多个可以获取外部知识的**工具**，例如文档加载器、Web API 或数据库查询。
</Tip>

```mermaid actions={true} theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
%%{init: {'flowchart': {'nodeSpacing': 12, 'rankSpacing': 18, 'padding': 4}, 'themeVariables': {'fontSize': '12px'}}}%%
graph TB
    A[用户输入 / 问题] --> B["Agent（LLM）"]
    B --> C{需要外部信息？}
    C -- 是 --> D["使用工具搜索"]
    D --> H{信息足够回答？}
    H -- 否 --> B
    H -- 是 --> I[生成最终答案]
    C -- 否 --> I
    I --> J[返回给用户]

    %% 深色模式友好样式
    classDef startend fill:#F6FFDB,stroke:#6E8900,stroke-width:2px,color:#2E3900
    classDef decision fill:#FDF3FF,stroke:#7E65AE,stroke-width:2px,color:#504B5F
    classDef process fill:#E5F4FF,stroke:#006DDD,stroke-width:1.5px,color:#030710

    class A,J startend
    class B,D,I process
    class C,H decision
```

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
import requests
from langchain.tools import tool
from langchain.chat_models import init_chat_model
from langchain.agents import create_agent


@tool
def fetch_url(url: str) -> str:
    """从 URL 获取文本内容"""
    response = requests.get(url, timeout=10.0)
    response.raise_for_status()
    return response.text

system_prompt = """\
当需要从网页获取信息时，使用 fetch_url；引用相关片段。
"""

agent = create_agent(
    model="claude-sonnet-4-6",
    tools=[fetch_url], # 检索工具 [!code highlight]
    system_prompt=system_prompt,
)
```

扩展示例：针对 LangGraph 的 llms.txt 的 Agentic RAG

  本示例实现了一个 **Agentic RAG 系统**，用于帮助用户查询 LangGraph 文档。Agent 首先加载 [llms.txt](https://llmstxt.org/)（其中列出了可用的文档 URL），然后根据用户的问题动态使用 `fetch_documentation` 工具检索并处理相关内容。

  ```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
  import requests
  from langchain.agents import create_agent
  from langchain.messages import HumanMessage
  from langchain.tools import tool
  from markdownify import markdownify


  ALLOWED_DOMAINS = ["https://langchain-ai.github.io/"]
  LLMS_TXT = 'https://langchain-ai.github.io/langgraph/llms.txt'


  @tool
  def fetch_documentation(url: str) -> str:  # [!code highlight]
      """从 URL 获取并转换文档内容"""
      if not any(url.startswith(domain) for domain in ALLOWED_DOMAINS):
          return (
              "错误：URL 不允许。"
              f"必须以以下之一开头：{', '.join(ALLOWED_DOMAINS)}"
          )
      response = requests.get(url, timeout=10.0)
      response.raise_for_status()
      return markdownify(response.text)


  # 我们将预先获取 llms.txt 的内容，无需发起 LLM 请求。
  llms_txt_content = requests.get(LLMS_TXT).text

  # Agent 的系统提示
  system_prompt = f"""
  你是一名资深的 Python 开发者和技术助手。
  你的主要职责是帮助用户解答有关 LangGraph 及相关工具的问题。

  操作说明：

  1. 如果用户提出你不确定的问题，或可能涉及 API 用法、行为或配置的问题，你必须使用 `fetch_documentation` 工具查阅相关文档。
  2. 引用文档时，请清晰总结并包含内容的相关上下文。
  3. 不得使用允许域之外的任何 URL。
  4. 如果文档获取失败，请告知用户，然后根据你最佳的专业理解继续回答。

  你可以从以下经批准的来源获取官方文档：

  {llms_txt_content}

  在回答用户关于 LangGraph 的问题之前，你**必须**查阅文档以获取最新的文档信息。

  你的回答应当清晰、简洁且技术准确。
  """

  tools = [fetch_documentation]

  model = init_chat_model("claude-sonnet-4-6", max_tokens=32_000)

  agent = create_agent(
      model=model,
      tools=tools,  # [!code highlight]
      system_prompt=system_prompt,  # [!code highlight]
      name="Agentic RAG",
  )

  response = agent.invoke({
      'messages': [
          HumanMessage(content=(
              "编写一个使用预置 create_react_agent 的 langgraph agent 的简短示例。"
              "该 agent 应能够查询股票价格信息。"
          ))
      ]
  })

  print(response['messages'][-1].content)
  ```
</Expandable>

教程：使用 Deep Agents 实现 RAG

  构建一个文档问答 Agent，在查询时检索相关块，将其卸载到文件系统，并将分析委托给子 Agent。了解更多（https://docs.langchain.com/oss/python/deepagents/rag）


### 混合型 RAG

混合型 RAG 结合了 2-Step RAG 和 Agentic RAG 的特点。它引入了中间步骤，如查询预处理、检索验证和生成后检查。这些系统比固定管道提供更多灵活性，同时保持一定的执行可控性。

典型组件包括：

* **查询增强**：修改输入问题以提高检索质量。这可以包括重写模糊查询、生成多个变体或用附加上下文扩展查询。
* **检索验证**：评估检索到的文档是否相关且充分。如果不够，系统可能会优化查询并重新检索。
* **答案验证**：检查生成的答案是否准确、完整，并与源内容一致。如有必要，系统可以重新生成或修订答案。

该架构通常支持这些步骤之间的多次迭代：

```mermaid actions={true} theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
%%{init: {'flowchart': {'nodeSpacing': 12, 'rankSpacing': 18, 'padding': 4}, 'themeVariables': {'fontSize': '12px'}}}%%
graph TB
    A[用户问题] --> B[查询增强]
    B --> C[检索文档]
    C --> D{信息是否充足？}
    D -- 否 --> E[优化查询]
    E --> C
    D -- 是 --> F[生成答案]
    F --> G{答案质量合格？}
    G -- 否 --> H{尝试不同方法？}
    H -- 是 --> E
    H -- 否 --> I[返回最佳答案]
    G -- 是 --> I
    I --> J[返回给用户]

    classDef startend fill:#F6FFDB,stroke:#6E8900,stroke-width:2px,color:#2E3900
    classDef decision fill:#FDF3FF,stroke:#7E65AE,stroke-width:2px,color:#504B5F
    classDef process fill:#E5F4FF,stroke:#006DDD,stroke-width:1.5px,color:#030710

    class A,J startend
    class B,C,E,F,I process
    class D,G,H decision
```

此架构适用于：

* 查询模糊或信息不足的应用
* 需要验证或质量控制步骤的系统
* 涉及多源或迭代优化的复杂工作流

教程：带自校正的 Agentic RAG

  一个 **混合型 RAG** 示例，结合了 Agentic 推理与检索和自校正机制。了解更多（https://docs.langchain.com/oss/python/langgraph/agentic-rag）
