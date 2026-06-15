"""Ingest task persistence — JSON file store with expiration cleanup."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import IngestTask, TaskStatus


class IngestTaskStore:
    """JSON-backed store for IngestTask objects.

    Reuses the SessionPersistence pattern: one JSON file per task,
    atomic write via temp file + rename, expiration cleanup.
    """

    def __init__(self, storage_dir: str = "./pkos_tasks", max_age_days: int = 30):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.max_age_days = max_age_days

    def _task_path(self, task_id: str) -> Path:
        safe_id = "".join(c for c in task_id if c.isalnum() or c in "-_.")
        return self.storage_dir / f"{safe_id}.json"

    def save(self, task: IngestTask) -> bool:
        try:
            task.updated_at = datetime.now().isoformat()
            path = self._task_path(task.task_id)
            temp = path.with_suffix(".tmp")
            with open(temp, "w", encoding="utf-8") as f:
                json.dump(task.to_dict(), f, ensure_ascii=False, indent=2)
            temp.replace(path)
            return True
        except Exception as e:
            print(f"[IngestTaskStore] save failed: {e}")
            return False

    def load(self, task_id: str) -> Optional[IngestTask]:
        try:
            path = self._task_path(task_id)
            if not path.exists():
                return None
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return IngestTask.from_dict(data)
        except Exception as e:
            print(f"[IngestTaskStore] load failed: {e}")
            return None

    def list_tasks(self) -> list:
        try:
            return [p.stem for p in self.storage_dir.glob("*.json")]
        except Exception as e:
            print(f"[IngestTaskStore] list failed: {e}")
            return []

    def delete(self, task_id: str) -> bool:
        try:
            path = self._task_path(task_id)
            if path.exists():
                path.unlink()
            return True
        except Exception as e:
            print(f"[IngestTaskStore] delete failed: {e}")
            return False

    def cleanup_expired(self) -> int:
        deleted = 0
        try:
            for path in self.storage_dir.glob("*.json"):
                mtime = datetime.fromtimestamp(path.stat().st_mtime)
                age_days = (datetime.now() - mtime).days
                if age_days > self.max_age_days:
                    path.unlink()
                    deleted += 1
        except Exception as e:
            print(f"[IngestTaskStore] cleanup failed: {e}")
        return deleted
