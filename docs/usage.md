# 使用指南

## 运行模式

本项目提供三种运行模式，通过 `main.py` 的 `--mode` 参数选择。

### 模式 1: 交互式对话 (chat) - 支持多轮

RAG 多轮对话模式，结合检索、生成和对话历史：

```bash
python main.py --mode chat
```

**多轮对话特性**：
- 自动保存对话历史
- 支持指代词理解（如"它"、"上面说的"等）
- 输入 `clear` 可清空历史
- 默认保存最近 10 轮对话

示例：
```
Knowledge RAG Chat - Multi-turn (type 'quit' to exit, 'clear' to clear history)
--------------------------------------------------

You: claude code的架构是怎么样的

Assistant: # Claude Code 架构概览
...

[Turn 1]

You: 它的Tools系统呢

Assistant: Claude Code 的 Tools 系统...
[Turn 2]

You: quit
```

### 模式 2: 仅检索 (retrieve)

仅返回向量相似搜索结果，不经过 LLM 生成：

```bash
python main.py --mode retrieve --query "你的问题" --k 4
```

示例输出：
```
Found 4 documents:

1. [posts\cc-code-read\_index.md]
   title: Claude Code 源码导读...

2. [posts\cc-code-read\00-导读.md]
   title: "Claude Code 源码导读(一)---概论"...
```

### 模式 3: API 服务 (api)

启动 FastAPI HTTP 服务：

```bash
python main.py --mode api --port 8000 --host 0.0.0.0
```

#### API 端点

**POST /chat** - 多轮对话

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Claude Code的架构是什么", "session_id": "test1"}'
```

响应：
```json
{
  "answer": "Claude Code 的架构...",
  "sources": [...],
  "session_id": "test1",
  "turn_count": 1
}
```

**第二轮对话**（使用相同 session_id）：
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "它的Tools系统呢", "session_id": "test1"}'
```

**GET /health** - 健康检查

```bash
curl http://localhost:8000/health
```

**GET /sessions/{session_id}/history** - 获取对话历史

```bash
curl http://localhost:8000/sessions/test1/history
```

响应：
```json
{
  "session_id": "test1",
  "turn_count": 2,
  "messages": [
    {"role": "user", "content": "Claude Code的架构是什么"},
    {"role": "assistant", "content": "Claude Code 的架构..."},
    {"role": "user", "content": "它的Tools系统呢"},
    {"role": "assistant", "content": "Tools 系统..."}
  ]
}
```

**DELETE /sessions/{session_id}** - 删除会话

```bash
curl -X DELETE http://localhost:8000/sessions/test1
```

**GET /sessions** - 列出所有会话

---

## 代码调用

### 多轮 RAG 对话

```python
from knowledge_vector.chain import create_rag_chain
from knowledge_vector.memory import ConversationMemory

# 创建 RAG chain（启用历史）
rag = create_rag_chain(use_history=True)

# 创建记忆
memory = ConversationMemory(max_turns=10)

# 第一轮
memory.add_user("Claude Code的架构是什么")
history = memory.get_history_for_rag()
answer = rag.invoke("Claude Code的架构是什么", k=4, history=history)
memory.add_assistant(answer)

# 第二轮（带历史）
memory.add_user("它的Tools系统呢")
history = memory.get_history_for_rag()
answer = rag.invoke("它的Tools系统呢", k=4, history=history)
memory.add_assistant(answer)
```

### 单轮 RAG 对话

```python
from knowledge_vector.chain import create_rag_chain

rag = create_rag_chain(use_history=False)
answer = rag.invoke("你的问题", k=4)
```

### 仅检索

```python
from knowledge_vector import MilvusVectorStore

vs = MilvusVectorStore()
vs.load()

docs = vs.search("你的问题", k=4)
for doc in docs:
    print(doc.page_content)
```

### 仅生成（无 RAG）

```python
from langchain_anthropic import ChatAnthropic
from langchain_core.output_parsers import StrOutputParser

llm = ChatAnthropic(model="MiniMax-M2.7")
parser = StrOutputParser()

answer = (llm | parser).invoke("你的问题")
```

---

## 管理向量库

### 查看集合

```python
from pymilvus import MilvusClient

client = MilvusClient(uri='http://localhost:19530')
print(client.list_collections())
```

### 查看数据量

```python
stats = client.get_collection_stats('knowledge_base')
print(f"Row count: {stats['row_count']}")
```

### 删除集合

```python
client.drop_collection('knowledge_base')
```

### 重新摄入

```bash
# 删除旧集合后重新摄入
python scripts/ingest.py --drop-old
```
