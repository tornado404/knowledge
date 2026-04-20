# 使用指南

## 运行模式

本项目提供三种运行模式，通过 `main.py` 的 `--mode` 参数选择。

### 模式 1: 交互式对话 (chat)

RAG 对话模式，结合检索和生成：

```bash
python main.py --mode chat
```

示例：
```
Knowledge RAG Chat (type 'quit' to exit)
----------------------------------------

You: claude code的架构是怎么样的

Assistant: # Claude Code 架构概览

根据参考资料，Claude Code 的架构非常模块化...

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

**POST /chat** - 对话

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "claude code的Tools如何编写", "k": 4}'
```

响应：
```json
{
  "answer": "Claude Code 的 Tools 编写方式...",
  "sources": [
    {"source": "posts/cc-code-read/02_工具系统.md", "content": "..."},
    ...
  ],
  "session_id": "session_123456"
}
```

**GET /health** - 健康检查

```bash
curl http://localhost:8000/health
```

**GET /sessions/{session_id}/messages** - 获取对话历史

**DELETE /sessions/{session_id}** - 删除会话

---

## 代码调用

### 检索 + 生成（RAG Chain）

```python
from knowledge_vector.chain import create_rag_chain

rag = create_rag_chain()
answer = rag.invoke("你的问题", k=4)
print(answer)
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
