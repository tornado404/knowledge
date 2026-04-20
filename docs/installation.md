# 安装部署

## 环境要求

- Python 3.10+
- Docker & Docker Compose
- 4GB+ RAM

## 1. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

主要依赖：
- `langchain`, `langchain_community`, `langchain_text_splitters`
- `langchain-anthropic` (LLM 调用)
- `langchain-huggingface` (Embedding)
- `pymilvus>=2.6.0` (向量数据库客户端)
- `fastapi`, `uvicorn` (API 服务)
- `sentence-transformers` (Embedding 模型)

## 2. 启动 Milvus 服务

### 使用 Docker Compose（推荐）

```bash
docker-compose up -d
```

验证服务状态：
```bash
docker ps
# 应该看到: milvus-standalone, milvus-etcd, milvus-minio
```

### 配置说明

`docker-compose.yml` 包含三个服务：

| 服务 | 端口 | 说明 |
|------|------|------|
| `milvus-standalone` | 19530, 9091 | 主服务 |
| `milvus-etcd` | 2379 | 元数据存储 |
| `milvus-minio` | 9000, 9001 | 对象存储 |

## 3. 配置 API 密钥

编辑 `.env.txt`：

```txt
ANTHROPIC_BASE_URL=https://api.minimaxi.com/anthropic
ANTHROPIC_API_KEY=your_api_key_here
ANTHROPIC_MODEL=MiniMax-M2.7
```

## 4. 摄入文档

```bash
python scripts/ingest.py
```

参数选项：
- `--docs-dir`: Markdown 目录（默认: `docs`）
- `--collection`: 集合名称（默认: `knowledge_base`）
- `--chunk-size`: 块大小（默认: 1000）
- `--chunk-overlap`: 块重叠（默认: 200）
- `--drop-old`: 删除旧集合后重新摄入

## 5. 验证安装

```bash
python main.py --mode retrieve --query "test"
```

预期：返回相关文档列表。

## 故障排除

### Milvus 连接失败

```bash
# 检查容器状态
docker ps -a

# 查看日志
docker logs milvus-standalone
```

### Python 模块导入失败

```bash
# 确保在项目根目录
cd E:\code\knowledge

# 使用正确的 Python 路径
python main.py --mode retrieve --query "test"
```
