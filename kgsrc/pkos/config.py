"""PKOS configuration — extends main config with PKOS-specific settings."""

import os
from dataclasses import dataclass

from knowledge_vector.config import config as _base_config


@dataclass
class PKOSConfig:
    """PKOS-specific configuration."""

    vault_dir: str = "./kgsrc/pkos/vault"
    inbox_dir: str = "./pkos_inbox"
    task_dir: str = "./pkos_tasks"
    dlq_dir: str = "./pkos_dead_letter"
    image_storage_dir: str = "./pkos_images"
    indexed_file: str = "./pkos_indexed.json"
    max_file_size_mb: int = 50
    allowed_image_types: tuple = ("png", "jpg", "jpeg", "webp", "gif")
    # Worker configuration
    worker_enabled: bool = True
    worker_poll_interval: float = 1.0
    # Inherit LLM config from base
    anthropic_model: str = ""
    anthropic_api_key: str = ""
    anthropic_base_url: str = ""
    milvus_collection: str = ""
    milvus_host: str = ""
    milvus_port: int = 19530

    @classmethod
    def from_base(cls):
        return cls(
            vault_dir=os.getenv("PKOS_VAULT_DIR", "./kgsrc/pkos/vault"),
            inbox_dir=os.getenv("PKOS_INBOX_DIR", "./pkos_inbox"),
            task_dir=os.getenv("PKOS_TASK_DIR", "./pkos_tasks"),
            dlq_dir=os.getenv("PKOS_DLQ_DIR", "./pkos_dead_letter"),
            image_storage_dir=os.getenv("PKOS_IMAGE_DIR", "./pkos_images"),
            indexed_file=os.getenv("PKOS_INDEXED_FILE", "./pkos_indexed.json"),
            max_file_size_mb=int(os.getenv("PKOS_MAX_FILE_SIZE_MB", "50")),
            worker_enabled=os.getenv("PKOS_WORKER_ENABLED", "true").lower() == "true",
            worker_poll_interval=float(os.getenv("PKOS_WORKER_POLL_INTERVAL", "1.0")),
            anthropic_model=_base_config.anthropic_model,
            anthropic_api_key=_base_config.anthropic_api_key,
            anthropic_base_url=_base_config.anthropic_base_url,
            milvus_collection=_base_config.milvus_collection,
            milvus_host=_base_config.milvus_host,
            milvus_port=_base_config.milvus_port,
        )


pkos_config = PKOSConfig.from_base()
