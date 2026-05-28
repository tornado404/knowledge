# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

基于 LangChain + Milvus + MiniMax 的 Markdown 文档智能问答系统，支持 RAG (Retrieval Augmented Generation) 对话功能。

## 常用命令

```bash
# 安装依赖
pip install -r requirements.txt

# 启动 Milvus 向量数据库
docker-compose up -d

# 摄入文档到向量库
python scripts/ingest.py --docs-dir docs --chunk-size 1000 --chunk-overlap 200 --drop-old

# 运行主程序（3 种模式）
python main.py --mode chat          # 交互式对话
python main.py --mode retrieve --query "你的问题"  # 仅检索
python main.py --mode api --port 8000  # HTTP API 服务

# 测试检索
python test/test_search.py
```

## 代码架构

**源码目录**: `kgsrc/knowledge_vector/`（注意：README.md 中误写为 `src/`）

```
loader.py      # Markdown 文件加载（UnstructuredMarkdownLoader）
     ↓
splitter.py    # 两阶段分割：按 Markdown 标题 → 按字符数递归分割
     ↓
vectorstore.py # Milvus 向量存储封装（create_from_documents / search）
     ↓
chain.py / agent.py  # RAG Chain / LangGraph Agent
     ↓
memory.py / chat.py  # 对话历史管理 / FastAPI 服务
     ↓
main.py        # 主入口（mode: chat | retrieve | api）
```

**核心模块**:
- `config.py` — 从 `.env.txt` 加载配置
- `loader.py` — 递归加载 Markdown 文件
- `splitter.py` — MarkdownHeaderTextSplitter + RecursiveCharacterTextSplitter 两阶段分割
- `vectorstore.py` — Milvus 封装，BAAI/bge-small-zh-v1.5 embedding
- `chain.py` — 单轮/多轮 RAG Chain
- `agent.py` — LangGraph RAG Agent
- `memory.py` — ConversationMemory 多轮对话历史
- `chat.py` — FastAPI 服务（`/chat`, `/health`, `/sessions` 端点）

**配置**: `.env.txt`（非 `.env`），包含 MiniMax API 和 Milvus 连接参数。

**LangGraph**: `langgraph.json` 定义了 `agent` 图，入口为 `kgsrc/knowledge_vector/agent.py:graph`。
