# Knowledge Vector RAG

基于 LangChain + Milvus + MiniMax 的 Markdown 文档智能问答系统。

## 目录

- [功能特性](#功能特性)
- [项目结构](#项目结构)
- [安装部署](./docs/installation.md)
- [使用指南](./docs/usage.md)
- [架构说明](./docs/architecture.md)

---

## 功能特性

| 功能 | 说明 |
|------|------|
| **文档加载** | `UnstructuredMarkdownLoader` 递归加载多级目录 |
| **文本分割** | `MarkdownHeaderTextSplitter` + `RecursiveCharacterTextSplitter` |
| **向量存储** | Milvus 2.3 (Docker 部署) |
| **Embedding** | `BAAI/bge-small-zh-v1.5` (512 维中文向量) |
| **RAG 对话** | LangChain Chain 检索 + MiniMax LLM 生成 |

---

## 项目结构

```
E:\code\knowledge\
├── .env.txt                    # API 配置（MiniMax/Claude）
├── docker-compose.yml           # Milvus 服务编排
├── main.py                     # 主程序入口（3 种运行模式）
├── pyproject.toml              # Python 项目配置
├── requirements.txt            # 依赖列表
├── README.md                   # 本文档
├── docs/
│   ├── installation.md         # 安装部署指南
│   ├── usage.md               # 使用指南
│   └── architecture.md         # 架构说明
├── scripts/
│   └── ingest.py               # 文档摄入脚本
├── src/
│   └── knowledge_vector/
│       ├── __init__.py
│       ├── config.py          # 配置加载
│       ├── loader.py          # Markdown 加载器
│       ├── splitter.py         # 文本分割器
│       ├── vectorstore.py      # Milvus 向量库
│       ├── chain.py            # RAG Chain
│       └── chat.py             # FastAPI 对话服务
└── test/
    └── test_search.py         # 搜索测试
```

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动 Milvus

```bash
docker-compose up -d
```

### 3. 摄入文档

```bash
python scripts/ingest.py
```

### 4. 对话测试

```bash
# 交互式对话
python main.py --mode chat

# 仅检索
python main.py --mode retrieve --query "你的问题"

# API 服务
python main.py --mode api --port 8000
```

---

## 三种运行模式

| 模式 | 命令 | 用途 |
|------|------|------|
| `chat` | `python main.py --mode chat` | 交互式 RAG 对话 |
| `retrieve` | `python main.py --mode retrieve --query "..."` | 仅向量检索 |
| `api` | `python main.py --mode api --port 8000` | HTTP API 服务 |

---

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `ANTHROPIC_BASE_URL` | API 端点 | `https://api.minimaxi.com/anthropic` |
| `ANTHROPIC_API_KEY` | API 密钥 | - |
| `ANTHROPIC_MODEL` | LLM 模型 | `MiniMax-M2.7` |
| `MILVUS_HOST` | Milvus 主机 | `localhost` |
| `MILVUS_PORT` | Milvus 端口 | `19530` |
| `MILVUS_COLLECTION` | 集合名称 | `knowledge_base` |
