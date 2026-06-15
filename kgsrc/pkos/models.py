"""PKOS Ingest Pipeline data models."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List


class TaskStatus(Enum):
    """Ingest pipeline task status."""

    REGISTERED = "REGISTERED"
    PARSING = "PARSING"
    UNDERSTANDING = "UNDERSTANDING"
    CLASSIFYING = "CLASSIFYING"
    ARCHIVING = "ARCHIVING"
    INDEXED = "INDEXED"
    FAILED = "FAILED"
    DEAD_LETTER = "DEAD_LETTER"


@dataclass
class ParsedContent:
    """Result of parsing a raw file."""

    raw_text: str = ""
    title: Optional[str] = None
    summary: Optional[str] = None
    entities: List[str] = field(default_factory=list)
    extracted_images: List[dict] = field(default_factory=list)
    source_url: Optional[str] = None


@dataclass
class IngestTask:
    """A single ingest task with state machine tracking."""

    task_id: str
    source_type: str  # "text" | "markdown" | "pdf" | "image" | "web"
    status: TaskStatus = TaskStatus.REGISTERED
    source_url: Optional[str] = None
    identities: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    topic: Optional[str] = None
    retry_count: int = 0
    error: Optional[str] = None
    vault_path: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "source_type": self.source_type,
            "source_url": self.source_url,
            "identities": self.identities,
            "tags": self.tags,
            "topic": self.topic,
            "retry_count": self.retry_count,
            "error": self.error,
            "vault_path": self.vault_path,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "IngestTask":
        return cls(
            task_id=data["task_id"],
            source_type=data["source_type"],
            status=TaskStatus(data["status"]),
            source_url=data.get("source_url"),
            identities=data.get("identities", []),
            tags=data.get("tags", []),
            topic=data.get("topic"),
            retry_count=data.get("retry_count", 0),
            error=data.get("error"),
            vault_path=data.get("vault_path"),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
        )
