#!/bin/bash
# ============================================================
# Knowledge RAG System - 一键启动脚本 (for Ubuntu)
# ============================================================
# 功能: 启动 Milvus + Redis + PostgreSQL + LangGraph API
#       并自动摄入 docs/ 目录下的 Markdown 文档到向量库
# ============================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${PROJECT_DIR}"

# ============================================================
# 1. 检查配置文件
# ============================================================
if [ ! -f "${PROJECT_DIR}/.env.txt" ]; then
    log_error ".env.txt 配置文件不存在"
    log_info "请先运行 install.sh 进行安装"
    exit 1
fi

# 检查 API Key 是否已配置
source "${PROJECT_DIR}/.env.txt"
if [ "${ANTHROPIC_API_KEY}" = "your_api_key_here" ] || [ -z "${ANTHROPIC_API_KEY}" ]; then
    log_error "API Key 未配置!"
    log_info "请编辑 ${PROJECT_DIR}/.env.txt 填入你的 MiniMax API Key"
    exit 1
fi

# ============================================================
# 2. 启动基础服务 (Milvus, Redis, PostgreSQL)
# ============================================================
log_info "启动基础服务 (Milvus, Redis, PostgreSQL)..."

docker compose up -d

# 等待 Milvus 启动
log_info "等待 Milvus 服务就绪..."
sleep 10

# 检查 Milvus 是否就绪
for i in {1..30}; do
    if docker exec milvus-standalone milvusctl health > /dev/null 2>&1 || nc -z localhost 19530 2>/dev/null; then
        log_info "Milvus 服务已就绪"
        break
    fi
    if [ $i -eq 30 ]; then
        log_warn "Milvus 启动可能需要更长时间，请稍候..."
    fi
    sleep 2
done

# ============================================================
# 3. 摄入文档到向量库
# ============================================================
if [ -d "${PROJECT_DIR}/docs" ] && [ "$(ls -A ${PROJECT_DIR}/docs 2>/dev/null)" ]; then
    log_info "摄入 Markdown 文档到向量库..."

    # 检查 ingest.py 是否存在
    if [ -f "${PROJECT_DIR}/scripts/ingest.py" ]; then
        export $(grep -v '^#' "${PROJECT_DIR}/.env.txt" | xargs)
        python3 "${PROJECT_DIR}/scripts/ingest.py" \
            --docs-dir "${PROJECT_DIR}/docs" \
            --chunk-size 1000 \
            --chunk-overlap 200 \
            --drop-old
        log_info "文档摄入完成"
    else
        log_warn "未找到 ingest.py，跳过文档摄入"
        log_info "如需摄入文档，请手动运行: python scripts/ingest.py --docs-dir docs"
    fi
else
    log_warn "docs/ 目录为空或不存在，跳过文档摄入"
fi

# ============================================================
# 4. 构建并启动 LangGraph API
# ============================================================
log_info "构建 LangGraph API 镜像..."

docker compose build langgraph-api

log_info "启动 LangGraph API 服务..."
docker compose up -d langgraph-api

# 等待 API 服务启动
log_info "等待 API 服务就绪..."
sleep 5

# ============================================================
# 5. 完成提示
# ============================================================
echo ""
echo "=============================================="
echo -e "${GREEN}启动完成！${NC}"
echo "=============================================="
echo ""
echo "服务地址:"
echo "  - LangGraph API: http://localhost:8123"
echo "  - Milvus Console: http://localhost:9091"
echo "  - MinIO Console: http://localhost:9001"
echo ""
echo "API 端点:"
echo "  - POST /agent/chat  - 对话接口"
echo "  - GET  /health      - 健康检查"
echo "  - GET  /sessions    - 会话管理"
echo ""
echo "常用命令:"
echo "  - 查看日志: docker compose logs -f langgraph-api"
echo "  - 停止服务: docker compose down"
echo "  - 重新摄入文档: python scripts/ingest.py --docs-dir docs --drop-old"
echo "=============================================="