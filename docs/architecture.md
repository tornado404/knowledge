# 架构说明

## 系统架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                         用户交互层                                │
│  ┌──────────┐  ┌──────────────┐  ┌────────────────────────┐    │
│  │  CLI     │  │  FastAPI     │  │  Python Code           │    │
│  │ main.py  │  │  chat.py     │  │  (import 调用)        │    │
│  └────┬─────┘  └──────┬───────┘  └───────────┬────────────┘    │
└───────┼────────────────┼─────────────────────┼─────────────────┘
        │                │                     │
        ▼                ▼                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                      LangChain 编排层                             │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    RAGChain (chain.py)                   │   │
│  │  ┌────────────┐    ┌─────────────┐    ┌───────────────┐   │   │
│  │  │ 检索检索    │ -> │ Context构建 │ -> │ LLM 生成     │   │   │
│  │  │ Milvus     │    │ Prompt填充  │    │ MiniMax-M2.7 │   │   │
│  │  └────────────┘    └─────────────┘    └───────────────┘   │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│                       向量存储层                                  │
│  ┌──────────────────────┐    ┌─────────────────────────────┐    │
│  │  MilvusVectorStore   │    │  Milvus 2.3 (Docker)        │    │
│  │  (vectorstore.py)    │ -> │  - knowledge_base           │    │
│  │                      │    │  - 2457 chunks              │    │
│  └──────────────────────┘    └─────────────────────────────┘    │
│                                    │                             │
│                                    ▼                             │
│                    ┌─────────────────────────────┐              │
│                    │  bge-small-zh-v1.5        │              │
│                    │  (512 维中文向量)           │              │
│                    └─────────────────────────────┘              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 核心组件

### 1. 文档摄入流程

```
docs/*.md
    │
    ▼
[MarkdownLoader] ──> UnstructuredMarkdownLoader
    │
    ▼
[文本分割器]
    │
    ├── MarkdownHeaderTextSplitter (按 # 标题层级)
    │
    └── RecursiveCharacterTextSplitter (按 chunk_size)
    │
    ▼
2457 chunks
    │
    ▼
[Embedding] ──> BAAI/bge-small-zh-v1.5
    │
    ▼
[Milvus.insert()] ──> knowledge_base collection
```

### 2. RAG 查询流程

```
用户问题
    │
    ▼
[Embedding.query()] ──> bge-small-zh-v1.5
    │
    ▼
[Milvus.search()] ──> Top-k 相关文档
    │
    ▼
[Context 构建] ──> 格式化文档为 Prompt
    │
    ▼
[LLM.invoke()] ──> MiniMax-M2.7
    │
    ▼
AI 回答
```

---

## 模块说明

### `src/knowledge_vector/config.py`

配置管理，从 `.env.txt` 加载环境变量：

```python
@dataclass
class Config:
    anthropic_base_url: str
    anthropic_api_key: str
    anthropic_model: str
    milvus_host: str
    milvus_port: int
    milvus_collection: str
```

### `src/knowledge_vector/loader.py`

Markdown 文档加载器：

```python
class MarkdownLoader:
    def load(self) -> List[Document]:
        """递归加载 docs/ 下所有 .md 文件"""

    def load_single(self, file_path: str) -> List[Document]:
        """加载单个文件"""
```

### `src/knowledge_vector/splitter.py`

文本分割：

```python
def split_documents(documents, chunk_size=1000, chunk_overlap=200):
    """MarkdownHeaderTextSplitter + RecursiveCharacterTextSplitter"""
```

### `src/knowledge_vector/vectorstore.py`

Milvus 封装：

```python
class MilvusVectorStore:
    def create_from_documents(self, documents, drop_old=False)
    def load(self)
    def search(self, query, k=4, filter=None) -> List[Document]
    def similarity_search_with_score(self, query, k=4) -> List[tuple]
```

### `src/knowledge_vector/chain.py`

RAG Chain：

```python
class RAGChain:
    def invoke(self, question, k=4) -> str:
        """检索 + 生成"""

    def retrieve(self, query, k=4) -> List[Document]:
        """仅检索"""
```

---

## 数据模型

### Milvus Collection Schema

```
Collection: knowledge_base
├── pk        (INT64, auto_id, primary key)
├── text      (VARCHAR, max_length=65535)
├── source    (VARCHAR, max_length=65535)
└── vector    (FLOAT_VECTOR, dim=512)
```

### Document Metadata

```python
{
    "source": "posts/cc-code-read/00-导读.md"
}
```

---

## 配置对比

| 组件 | 旧方案 | 新方案 |
|------|--------|--------|
| Embedding | text2vec-base-chinese (768维) | bge-small-zh-v1.5 (512维) |
| Milvus 连接 | milvus-lite (已弃用) | Docker milvusdb/milvus:v2.3.3 |
| LangChain | langchain_community | langchain_milvus |

---

## 扩展点

1. **更换 Embedding 模型**
   - 修改 `vectorstore.py` 中的 `DEFAULT_EMBED_MODEL`
   - 重新摄入文档

2. **添加对话记忆**
   - 在 `chain.py` 中集成 `ConversationBufferMemory`
   - 支持多轮对话

3. **添加 Reranker**
   - 在检索后添加 `CohereRerank` 重新排序
   - 提升相关性

4. **流式输出**
   - LLM 使用 `stream` 模式
   - FastAPI 支持 SSE
