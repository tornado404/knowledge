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

    # Milvus
    milvus_collection: str = "knowledge_base"
    milvus_host: str = "localhost"
    milvus_port: int = 19530

    @classmethod
    def from_env(cls) -> "Config":
        """Create Config from environment variables."""
        return cls(
            anthropic_base_url=os.getenv("ANTHROPIC_BASE_URL", ""),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            anthropic_model=os.getenv("ANTHROPIC_MODEL", ""),
            minimax_embed_model=os.getenv("MINIMAX_EMBED_MODEL", "embeddings@MiniMax/MiniMax-Embedding-M2"),
            minimax_embed_api_key=os.getenv("MINIMAX_EMBED_API_KEY", os.getenv("ANTHROPIC_API_KEY", "")),
            milvus_collection=os.getenv("MILVUS_COLLECTION", "knowledge_base"),
            milvus_host=os.getenv("MILVUS_HOST", "localhost"),
            milvus_port=int(os.getenv("MILVUS_PORT", "19530")),
        )


# Global config instance
config = Config.from_env()
