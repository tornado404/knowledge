"""PKOS structured logging — TaskLogger and PipelineLogger.

Provides per-task JSON Lines logging with thread safety.
Log path: {log_dir}/ingest/{date}/{task_id}.jsonl
"""

import json
import os
import shutil
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional


class TaskLogger:
    """Per-task structured logger (thread-safe).

    Writes JSON Lines records to {log_dir}/ingest/{date}/{task_id}.jsonl.
    """

    def __init__(self, task_id: str, log_dir: str = "./pkos_logs"):
        self.task_id = task_id
        self._lock = threading.Lock()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self._log_path = Path(log_dir) / "ingest" / today / f"{task_id}.jsonl"
        self._log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(
        self,
        level: str,
        stage: str,
        message: str,
        duration_ms: float = None,
        error: str = None,
        extra: dict = None,
    ):
        """Write a structured log line (thread-safe)."""
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "logger": "pkos.pipeline",
            "task_id": self.task_id,
            "stage": stage,
            "message": message,
            "duration_ms": duration_ms,
            "error": error,
        }
        if extra:
            record.update(extra)
        with self._lock:
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def debug(self, stage: str, message: str, **kwargs):
        self.log("DEBUG", stage, message, **kwargs)

    def info(self, stage: str, message: str, **kwargs):
        self.log("INFO", stage, message, **kwargs)

    def warn(self, stage: str, message: str, **kwargs):
        self.log("WARN", stage, message, **kwargs)

    def error(self, stage: str, message: str, **kwargs):
        self.log("ERROR", stage, message, **kwargs)


class PipelineLogger:
    """Global Pipeline log aggregator (dispatches by task_id, thread-safe)."""

    def __init__(self, log_dir: str = "./pkos_logs"):
        self.log_dir = log_dir
        self._loggers: dict[str, TaskLogger] = {}
        self._lock = threading.Lock()

    def get_task_logger(self, task_id: str) -> TaskLogger:
        """Get or create a TaskLogger for the given task_id (thread-safe)."""
        if task_id not in self._loggers:
            with self._lock:
                # Double-check after acquiring lock
                if task_id not in self._loggers:
                    self._loggers[task_id] = TaskLogger(task_id, log_dir=self.log_dir)
        return self._loggers[task_id]

    def get_recent_errors(self, limit: int = 20) -> list[dict]:
        """Get the most recent ERROR-level log records across all tasks."""
        errors: list[dict] = []
        log_root = Path(self.log_dir) / "ingest"
        if not log_root.exists():
            return errors
        for day_dir in sorted(log_root.iterdir(), reverse=True):
            if not day_dir.is_dir():
                continue
            for log_file in sorted(day_dir.glob("*.jsonl"), reverse=True):
                try:
                    for line in log_file.read_text().splitlines():
                        record = json.loads(line)
                        if record.get("level") == "ERROR":
                            errors.append(record)
                            if len(errors) >= limit:
                                return errors
                except (json.JSONDecodeError, OSError):
                    continue
        return errors

    def get_stage_durations(self, task_id: str) -> list[dict]:
        """Get stage duration records for a specific task."""
        task_logger = self.get_task_logger(task_id)
        path = task_logger._log_path  # type: ignore[attr-defined]
        if not path.exists():
            return []
        durations: list[dict] = []
        for line in path.read_text().splitlines():
            try:
                record = json.loads(line)
                if record.get("duration_ms") is not None:
                    durations.append({
                        "stage": record["stage"],
                        "duration_ms": record["duration_ms"],
                    })
            except json.JSONDecodeError:
                continue
        return durations

    def cleanup_old_logs(self, max_age_days: int = 30):
        """Remove log directories older than max_age_days."""
        cutoff = datetime.now(timezone.utc).date() - timedelta(days=max_age_days)
        log_root = Path(self.log_dir) / "ingest"
        if not log_root.exists():
            return
        for day_dir in log_root.iterdir():
            if not day_dir.is_dir():
                continue
            try:
                day_date = datetime.strptime(day_dir.name, "%Y-%m-%d").date()
                if day_date < cutoff:
                    shutil.rmtree(day_dir)
            except ValueError:
                continue
