"""Configuration loader from .env.txt."""

import os
from pathlib import Path
from dataclasses import dataclass
from dotenv import load_dotenv

# Load .env.txt from project root
ENV_PATH = Path(__file__).parent.parent.parent / ".env.txt"
load_dotenv(ENV_PATH)


@dataclass
class Config:
    """Application configuration from environment variables."""

    # Anthropic / MiniMax API
    anthropic_base_url: str = ""
    anthropic_api_key: str = ""
    anthropic_model: str = ""

    # MiniMax Embedding
    minimax_embed_model: str = "embeddings@MiniMax/MiniMax-Embedding-M2"
    minimax_embed_api_key: str = ""
    minimax_group_id: str = ""

    # Milvus
    milvus_collection: str = "knowledge_base"
    milvus_host: str = "localhost"
    milvus_port: int = 19530

    # Tavily Web Search
    tavily_api_key: str = ""

    # LangSmith Tracing
    langsmith_api_key: str = ""
    langsmith_tracing: bool = False
    langsmith_project: str = "knowledge-rag"

    # Multi-Agent Configuration
    multi_agent_enabled: bool = False
    e2b_api_key: str = ""
    sandbox_pool_size: int = 5
    sandbox_timeout: int = 300
    max_subtasks: int = 10
    task_timeout: int = 120

    # Compression Configuration
    use_llm_summarizer: bool = False  # 是否使用 LLM 生成语义摘要

    # Session Persistence Configuration
    session_persistence: bool = True  # 是否启用会话持久化
    session_storage_dir: str = "./sessions"  # 会话存储目录
    session_max_age_days: int = 30  # 会话最大保留天数

    # PKOS Configuration
    pkos_vault_dir: str = "./kgsrc/pkos/vault"
    pkos_inbox_dir: str = "./pkos_inbox"
    pkos_task_dir: str = "./pkos_tasks"
    pkos_dlq_dir: str = "./pkos_dead_letter"

    @classmethod
    def from_env(cls) -> "Config":
        """Create Config from environment variables."""
        return cls(
            anthropic_base_url=os.getenv("ANTHROPIC_BASE_URL", ""),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            anthropic_model=os.getenv("ANTHROPIC_MODEL", ""),
            minimax_embed_model=os.getenv("MINIMAX_EMBED_MODEL", "embeddings@MiniMax/MiniMax-Embedding-M2"),
            minimax_embed_api_key=os.getenv("MINIMAX_EMBED_API_KEY", os.getenv("ANTHROPIC_API_KEY", "")),
            minimax_group_id=os.getenv("MINIMAX_GROUP_ID", ""),
            milvus_collection=os.getenv("MILVUS_COLLECTION", "knowledge_base"),
            milvus_host=os.getenv("MILVUS_HOST", "localhost"),
            milvus_port=int(os.getenv("MILVUS_PORT", "19530")),
            tavily_api_key=os.getenv("TAVILY_API_KEY", ""),
            langsmith_api_key=os.getenv("LANGSMITH_API_KEY", ""),
            langsmith_tracing=os.getenv("LANGSMITH_TRACING", "false").lower() == "true",
            langsmith_project=os.getenv("LANGSMITH_PROJECT", "knowledge-rag"),
            multi_agent_enabled=os.getenv("MULTI_AGENT_ENABLED", "false").lower() == "true",
            e2b_api_key=os.getenv("E2B_API_KEY", ""),
            sandbox_pool_size=int(os.getenv("SANDBOX_POOL_SIZE", "5")),
            sandbox_timeout=int(os.getenv("SANDBOX_TIMEOUT", "300")),
            max_subtasks=int(os.getenv("MAX_SUBTASKS", "10")),
            task_timeout=int(os.getenv("TASK_TIMEOUT", "120")),
            use_llm_summarizer=os.getenv("USE_LLM_SUMMARIZER", "false").lower() == "true",
            session_persistence=os.getenv("SESSION_PERSISTENCE", "true").lower() == "true",
            session_storage_dir=os.getenv("SESSION_STORAGE_DIR", "./sessions"),
            session_max_age_days=int(os.getenv("SESSION_MAX_AGE_DAYS", "30")),
            pkos_vault_dir=os.getenv("PKOS_VAULT_DIR", "./kgsrc/pkos/vault"),
            pkos_inbox_dir=os.getenv("PKOS_INBOX_DIR", "./pkos_inbox"),
            pkos_task_dir=os.getenv("PKOS_TASK_DIR", "./pkos_tasks"),
            pkos_dlq_dir=os.getenv("PKOS_DLQ_DIR", "./pkos_dead_letter"),
        )


# Global config instance
config = Config.from_env()
