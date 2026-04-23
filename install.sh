#!/bin/bash
# ============================================================
# Knowledge RAG System - 一键安装部署脚本 (for Ubuntu)
# ============================================================
# 功能: 安装 Docker/Docker Compose, 配置环境变量, 拉取镜像
# ============================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 检查是否为 root 用户
if [[ $EUID -ne 0 ]]; then
   log_warn "建议使用 sudo 运行此脚本，或确保当前用户有 Docker 操作权限"
fi

# ============================================================
# 1. 安装 Docker (如果未安装)
# ============================================================
log_info "检查 Docker 安装状态..."

if command -v docker &> /dev/null; then
    log_info "Docker 已安装: $(docker --version)"
else
    log_info "安装 Docker..."
    apt-get update
    apt-get install -y ca-certificates curl gnupg lsb-release

    # 添加 Docker GPG key
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg

    # 添加 Docker 仓库
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

    log_info "Docker 安装完成"
fi

# 启动 Docker 服务
systemctl enable docker --now 2>/dev/null || true

# ============================================================
# 2. 创建项目目录和配置文件
# ============================================================
log_info "创建项目目录结构..."

PROJECT_DIR="${HOME}/knowledge-rag"
mkdir -p "${PROJECT_DIR}/docs"

# 复制必要文件
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp -r "${SCRIPT_DIR}/kgsrc" "${PROJECT_DIR}/" 2>/dev/null || true
cp -r "${SCRIPT_DIR}/dependencies" "${PROJECT_DIR}/" 2>/dev/null || true

# 创建 .env.txt 配置文件模板
cat > "${PROJECT_DIR}/.env.txt" << 'EOF'
# ===============================================
# MiniMax LLM 配置
# ===============================================
ANTHROPIC_BASE_URL=https://api.minimaxi.com/anthropic
ANTHROPIC_API_KEY=your_api_key_here
ANTHROPIC_MODEL=MiniMax-M2.7
MINIMAX_EMBED_MODEL=embeddings@MiniMax/MiniMax-Embedding-M2

# ===============================================
# Milvus 向量数据库配置
# ===============================================
MILVUS_HOST=localhost
MILVUS_PORT=19530
MILVUS_COLLECTION=knowledge_base

# ===============================================
# LangSmith (可选，用于链路追踪)
# ===============================================
LANGSMITH_API_KEY=your_langsmith_key_here
EOF

log_warn "配置文件已创建: ${PROJECT_DIR}/.env.txt"
log_warn "请编辑 .env.txt 填入你的 MiniMax API Key"

# ============================================================
# 3. 复制 docker-compose.yml
# ============================================================
cp "${SCRIPT_DIR}/docker-compose.yml" "${PROJECT_DIR}/" 2>/dev/null || true

# ============================================================
# 4. 安装 Python 依赖 (用于本地运行 main.py)
# ============================================================
if command -v python3 &> /dev/null; then
    log_info "安装 Python 依赖..."
    cd "${PROJECT_DIR}"
    pip3 install -r dependencies/requirements.txt -q
    log_info "Python 依赖安装完成"
fi

# ============================================================
# 5. 拉取 Docker 镜像
# ============================================================
log_info "拉取 Docker 镜像 (Milvus, Redis, PostgreSQL)..."

cd "${PROJECT_DIR}"
docker compose pull langgraph-redis langgraph-postgres

log_info "镜像拉取完成"

# ============================================================
# 6. 完成提示
# ============================================================
echo ""
echo "=============================================="
echo -e "${GREEN}安装完成！${NC}"
echo "=============================================="
echo ""
echo "下一步操作:"
echo "  1. 编辑配置文件: nano ${PROJECT_DIR}/.env.txt"
echo "  2. 放入 Markdown 文档到: ${PROJECT_DIR}/docs/"
echo "  3. 运行启动脚本: bash ${PROJECT_DIR}/setup.sh"
echo ""
echo "或直接启动服务: cd ${PROJECT_DIR} && docker compose up -d"
echo "=============================================="