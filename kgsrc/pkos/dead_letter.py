"""Dead Letter Queue for failed ingest tasks."""

import json
import shutil
from pathlib import Path
from typing import Optional

from .models import IngestTask


class DeadLetterQueue:
    """Archive failed tasks for manual inspection and retry."""

    def __init__(self, dlq_dir: str = "./pkos_dead_letter"):
        self.dlq_dir = Path(dlq_dir)
        self.dlq_dir.mkdir(parents=True, exist_ok=True)

    def archive(self, task: IngestTask, original_path: Optional[str] = None) -> bool:
        """Archive a failed task.

        Args:
            task: The failed task.
            original_path: Path to the original file (if any).

        Returns:
            True if archived successfully.
        """
        try:
            archive_dir = self.dlq_dir / task.task_id
            archive_dir.mkdir(parents=True, exist_ok=True)

            # Save task metadata
            with open(archive_dir / "task.json", "w", encoding="utf-8") as f:
                json.dump(task.to_dict(), f, ensure_ascii=False, indent=2)

            # Copy original file if exists
            if original_path and Path(original_path).exists():
                shutil.copy2(original_path, archive_dir / "original")

            return True
        except Exception as e:
            print(f"[DeadLetterQueue] archive failed: {e}")
            return False

    def list_archived(self) -> list:
        """List all archived tasks."""
        tasks = []
        for subdir in self.dlq_dir.iterdir():
            if subdir.is_dir():
                task_file = subdir / "task.json"
                if task_file.exists():
                    try:
                        with open(task_file, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        tasks.append(data)
                    except Exception:
                        pass
        return tasks

    def get_archive(self, task_id: str) -> Optional[Path]:
        """Get the archive directory for a task."""
        archive_dir = self.dlq_dir / task_id
        if archive_dir.exists():
            return archive_dir
        return None

    def delete(self, task_id: str) -> bool:
        """Delete an archived task."""
        try:
            archive_dir = self.dlq_dir / task_id
            if archive_dir.exists():
                shutil.rmtree(archive_dir)
            return True
        except Exception as e:
            print(f"[DeadLetterQueue] delete failed: {e}")
            return False
