"""Tests for PKOS structured logging system."""

import json
import os
import tempfile
import shutil
import time
import threading
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock

import pytest

from kgsrc.pkos.logger import TaskLogger, PipelineLogger
from kgsrc.pkos.models import TaskStatus, IngestTask
from kgsrc.pkos.pipeline import IngestPipeline


# =============================================================================
# TaskLogger Tests
# =============================================================================


class TestTaskLogger:
    """TaskLogger: per-task JSON Lines file writer."""

    def test_writes_jsonl_file(self):
        """TaskLogger writes a JSON Lines file at the expected path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = TaskLogger("test-task-1", log_dir=tmpdir)
            logger.info(stage="TEST", message="hello")

            # Verify file exists
            today = time.strftime("%Y-%m-%d")
            log_path = Path(tmpdir) / "ingest" / today / "test-task-1.jsonl"
            assert log_path.exists(), f"Log file not found: {log_path}"

            # Verify content is valid JSON
            lines = log_path.read_text().strip().splitlines()
            assert len(lines) == 1
            record = json.loads(lines[0])
            assert record["message"] == "hello"

    def test_contains_all_required_fields(self):
        """Each log record has all mandatory fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = TaskLogger("test-task-req", log_dir=tmpdir)
            logger.info(stage="TEST", message="req fields check")

            today = time.strftime("%Y-%m-%d")
            log_path = Path(tmpdir) / "ingest" / today / "test-task-req.jsonl"
            record = json.loads(log_path.read_text().strip())

            assert "timestamp" in record, "Missing timestamp"
            assert "level" in record, "Missing level"
            assert "task_id" in record, "Missing task_id"
            assert "stage" in record, "Missing stage"
            assert "message" in record, "Missing message"
            assert "logger" in record, "Missing logger"
            assert record["task_id"] == "test-task-req"
            assert record["stage"] == "TEST"
            assert record["level"] == "INFO"
            assert record["logger"] == "pkos.pipeline"

    def test_multiple_levels(self):
        """debug/info/warn/error all write correct level field."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = TaskLogger("test-task-levels", log_dir=tmpdir)
            logger.debug(stage="DBG", message="debug msg")
            logger.info(stage="INF", message="info msg")
            logger.warn(stage="WRN", message="warn msg")
            logger.error(stage="ERR", message="error msg")

            today = time.strftime("%Y-%m-%d")
            log_path = Path(tmpdir) / "ingest" / today / "test-task-levels.jsonl"
            lines = log_path.read_text().strip().splitlines()
            assert len(lines) == 4

            records = [json.loads(line) for line in lines]
            levels = [r["level"] for r in records]
            assert levels == ["DEBUG", "INFO", "WARN", "ERROR"]

    def test_extra_fields(self):
        """Extra keyword arguments are included in the log record."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = TaskLogger("test-task-extra", log_dir=tmpdir)
            logger.info(stage="TEST", message="with extra", duration_ms=123.4, error=None,
                        extra={"source_type": "test"})

            today = time.strftime("%Y-%m-%d")
            log_path = Path(tmpdir) / "ingest" / today / "test-task-extra.jsonl"
            record = json.loads(log_path.read_text().strip())

            assert record["duration_ms"] == 123.4
            assert record["error"] is None
            assert record.get("source_type") == "test"

    def test_append_mode(self):
        """Multiple calls append to the same file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = TaskLogger("test-task-append", log_dir=tmpdir)
            logger.info(stage="A", message="first")
            logger.info(stage="B", message="second")
            logger.info(stage="C", message="third")

            today = time.strftime("%Y-%m-%d")
            log_path = Path(tmpdir) / "ingest" / today / "test-task-append.jsonl"
            lines = log_path.read_text().strip().splitlines()
            assert len(lines) == 3

    def test_concurrent_writes_no_race(self):
        """Concurrent writes from multiple threads do not corrupt the file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = TaskLogger("test-task-concurrent", log_dir=tmpdir)
            n = 50
            barrier = threading.Barrier(n)

            def writer(i):
                barrier.wait()  # synchronize start
                logger.info(stage="CONCURRENT", message=f"line {i}")

            threads = [threading.Thread(target=writer, args=(i,)) for i in range(n)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            today = time.strftime("%Y-%m-%d")
            log_path = Path(tmpdir) / "ingest" / today / "test-task-concurrent.jsonl"
            lines = log_path.read_text().strip().splitlines()
            assert len(lines) == n, f"Expected {n} lines, got {len(lines)}"

            # All lines must be valid JSON
            for line in lines:
                record = json.loads(line)
                assert record["level"] == "INFO"
                assert record["task_id"] == "test-task-concurrent"


# =============================================================================
# PipelineLogger Tests
# =============================================================================


class TestPipelineLogger:
    """PipelineLogger: global aggregator dispatching by task_id."""

    def test_get_task_logger_creates_new(self):
        """get_task_logger returns a TaskLogger for the given task_id."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pl = PipelineLogger(log_dir=tmpdir)
            tl = pl.get_task_logger("task-1")
            assert isinstance(tl, TaskLogger)
            assert tl.task_id == "task-1"

    def test_get_task_logger_reuses_existing(self):
        """get_task_logger returns the same logger for the same task_id."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pl = PipelineLogger(log_dir=tmpdir)
            tl1 = pl.get_task_logger("task-same")
            tl2 = pl.get_task_logger("task-same")
            assert tl1 is tl2

    def test_dispatch_by_task_id(self):
        """Loggers for different task_ids write to different files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pl = PipelineLogger(log_dir=tmpdir)
            pl.get_task_logger("task-alpha").info(stage="TEST", message="alpha")
            pl.get_task_logger("task-beta").info(stage="TEST", message="beta")

            today = time.strftime("%Y-%m-%d")
            alpha_path = Path(tmpdir) / "ingest" / today / "task-alpha.jsonl"
            beta_path = Path(tmpdir) / "ingest" / today / "task-beta.jsonl"
            assert alpha_path.exists()
            assert beta_path.exists()

            alpha_record = json.loads(alpha_path.read_text().strip())
            beta_record = json.loads(beta_path.read_text().strip())
            assert alpha_record["task_id"] == "task-alpha"
            assert beta_record["task_id"] == "task-beta"

    def test_get_recent_errors(self):
        """get_recent_errors returns ERROR-level records across all tasks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pl = PipelineLogger(log_dir=tmpdir)
            pl.get_task_logger("task-err1").info(stage="OK", message="fine")
            pl.get_task_logger("task-err1").error(stage="FAIL", message="error one")
            pl.get_task_logger("task-err2").error(stage="FAIL", message="error two")
            pl.get_task_logger("task-err2").warn(stage="OK", message="warning only")

            errors = pl.get_recent_errors(limit=10)
            assert len(errors) == 2
            messages = {e["message"] for e in errors}
            assert "error one" in messages
            assert "error two" in messages

    def test_get_recent_errors_limit(self):
        """get_recent_errors respects the limit parameter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pl = PipelineLogger(log_dir=tmpdir)
            for i in range(5):
                pl.get_task_logger(f"task-{i}").error(stage="FAIL", message=f"err {i}")

            errors = pl.get_recent_errors(limit=3)
            assert len(errors) == 3

    def test_get_stage_durations(self):
        """get_stage_durations returns records with duration_ms."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pl = PipelineLogger(log_dir=tmpdir)
            tl = pl.get_task_logger("task-dur")
            tl.info(stage="PARSING", message="done", duration_ms=150.0)
            tl.info(stage="CLASSIFYING", message="done", duration_ms=250.0)
            tl.info(stage="ARCHIVING", message="done")  # no duration

            durations = pl.get_stage_durations("task-dur")
            assert len(durations) == 2
            assert durations[0] == {"stage": "PARSING", "duration_ms": 150.0}
            assert durations[1] == {"stage": "CLASSIFYING", "duration_ms": 250.0}

    def test_cleanup_old_logs(self):
        """cleanup_old_logs removes log directories older than max_age_days."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pl = PipelineLogger(log_dir=tmpdir)

            # Create a "recent" log directory (today)
            today = time.strftime("%Y-%m-%d")
            recent_dir = Path(tmpdir) / "ingest" / today
            recent_dir.mkdir(parents=True)
            (recent_dir / "task-recent.jsonl").write_text('{"level":"INFO"}\n')

            # Create an "old" log directory (100 days ago)
            from datetime import datetime, timedelta, timezone
            old_date = (datetime.now(timezone.utc) - timedelta(days=100)).strftime("%Y-%m-%d")
            old_dir = Path(tmpdir) / "ingest" / old_date
            old_dir.mkdir(parents=True)
            (old_dir / "task-old.jsonl").write_text('{"level":"ERROR"}\n')

            # Cleanup with max_age_days=30
            pl.cleanup_old_logs(max_age_days=30)

            assert recent_dir.exists(), "Recent log dir should remain"
            assert not old_dir.exists(), "Old log dir should be removed"

    def test_cleanup_old_logs_no_effect(self):
        """cleanup_old_logs keeps all logs within max_age_days."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pl = PipelineLogger(log_dir=tmpdir)
            today = time.strftime("%Y-%m-%d")
            log_dir = Path(tmpdir) / "ingest" / today
            log_dir.mkdir(parents=True)
            (log_dir / "task.jsonl").write_text('{"level":"INFO"}\n')

            pl.cleanup_old_logs(max_age_days=30)
            assert log_dir.exists()

    def test_get_recent_errors_empty(self):
        """get_recent_errors returns empty list when no errors exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pl = PipelineLogger(log_dir=tmpdir)
            pl.get_task_logger("task-clean").info(stage="OK", message="all good")
            errors = pl.get_recent_errors(limit=10)
            assert errors == []


# =============================================================================
# Pipeline Integration Tests
# =============================================================================


class TestPipelineIntegration:
    """Integration: Pipeline._transition() writes structured logs."""

    def test_transition_writes_log(self):
        """_transition() creates a log file with stage info."""
        tmpdir = tempfile.mkdtemp()
        try:
            pipeline = IngestPipeline(
                task_dir=f"{tmpdir}/tasks",
                vault_dir=f"{tmpdir}/vault",
                dlq_dir=f"{tmpdir}/dlq",
            )
            # Inject PipelineLogger
            plogger = PipelineLogger(log_dir=f"{tmpdir}/logs")
            pipeline.logger = plogger

            task = pipeline.register(source_type="text", source_url="https://example.com")
            pipeline._transition(task, TaskStatus.PARSING)

            today = time.strftime("%Y-%m-%d")
            log_path = Path(tmpdir) / "logs" / "ingest" / today / f"{task.task_id}.jsonl"
            assert log_path.exists(), f"Log file not found: {log_path}"

            record = json.loads(log_path.read_text().strip())
            assert record["stage"] == "PARSING"
            assert record["level"] == "INFO"
            assert record["task_id"] == task.task_id
        finally:
            shutil.rmtree(tmpdir)

    def test_transition_with_error(self):
        """_transition() includes error message when provided."""
        tmpdir = tempfile.mkdtemp()
        try:
            pipeline = IngestPipeline(
                task_dir=f"{tmpdir}/tasks",
                vault_dir=f"{tmpdir}/vault",
                dlq_dir=f"{tmpdir}/dlq",
            )
            plogger = PipelineLogger(log_dir=f"{tmpdir}/logs")
            pipeline.logger = plogger

            task = pipeline.register(source_type="text")
            pipeline._transition(task, TaskStatus.FAILED, error="Something went wrong")

            today = time.strftime("%Y-%m-%d")
            log_path = Path(tmpdir) / "logs" / "ingest" / today / f"{task.task_id}.jsonl"
            record = json.loads(log_path.read_text().strip())
            assert record["stage"] == "FAILED"
            assert record["error"] == "Something went wrong"
        finally:
            shutil.rmtree(tmpdir)

    def test_process_task_logs_stages(self):
        """Full process_task creates logs with multiple stages."""
        tmpdir = tempfile.mkdtemp()
        try:
            pipeline = IngestPipeline(
                task_dir=f"{tmpdir}/tasks",
                vault_dir=f"{tmpdir}/vault",
                dlq_dir=f"{tmpdir}/dlq",
            )
            plogger = PipelineLogger(log_dir=f"{tmpdir}/logs")
            pipeline.logger = plogger

            task = pipeline.register(source_type="text", source_url="https://example.com")
            task_id = task.task_id

            mock_result = MagicMock()
            mock_result.title = "Test Title"
            mock_result.summary = "Test Summary"
            mock_result.topic = "测试"
            mock_result.identities = ["程序员"]
            mock_result.tags = ["test"]

            with patch.object(pipeline.classifier, "classify_content", return_value=mock_result):
                with patch.object(pipeline.indexer, "index_document", return_value=True):
                    result = pipeline.process_task(task_id, raw_text="Hello world content here")

            assert result is True

            today = time.strftime("%Y-%m-%d")
            log_path = Path(tmpdir) / "logs" / "ingest" / today / f"{task_id}.jsonl"
            assert log_path.exists()

            lines = log_path.read_text().strip().splitlines()
            stages = [json.loads(line)["stage"] for line in lines]

            # Should include at least PARSING, UNDERSTANDING, CLASSIFYING, ARCHIVING, INDEXED
            assert "PARSING" in stages
            assert "UNDERSTANDING" in stages
            assert "CLASSIFYING" in stages
            assert "ARCHIVING" in stages
            assert "INDEXED" in stages
        finally:
            shutil.rmtree(tmpdir)

    def test_process_task_with_duration_ms(self):
        """process_task logs include duration_ms for each stage."""
        tmpdir = tempfile.mkdtemp()
        try:
            pipeline = IngestPipeline(
                task_dir=f"{tmpdir}/tasks",
                vault_dir=f"{tmpdir}/vault",
                dlq_dir=f"{tmpdir}/dlq",
            )
            plogger = PipelineLogger(log_dir=f"{tmpdir}/logs")
            pipeline.logger = plogger

            task = pipeline.register(source_type="text", source_url="https://example.com")
            task_id = task.task_id

            mock_result = MagicMock()
            mock_result.title = "Test Title"
            mock_result.summary = "Test Summary"
            mock_result.topic = "测试"
            mock_result.identities = ["程序员"]
            mock_result.tags = ["test"]

            with patch.object(pipeline.classifier, "classify_content", return_value=mock_result):
                with patch.object(pipeline.indexer, "index_document", return_value=True):
                    result = pipeline.process_task(task_id, raw_text="Hello world")

            assert result is True

            today = time.strftime("%Y-%m-%d")
            log_path = Path(tmpdir) / "logs" / "ingest" / today / f"{task_id}.jsonl"
            records = [json.loads(line) for line in log_path.read_text().strip().splitlines()]

            # At least some records should have duration_ms
            durations = [r for r in records if r.get("duration_ms") is not None]
            assert len(durations) > 0, "No log records with duration_ms found"
            for d in durations:
                assert isinstance(d["duration_ms"], (int, float))
                assert d["duration_ms"] >= 0
        finally:
            shutil.rmtree(tmpdir)


# =============================================================================
# Concurrency Tests
# =============================================================================


class TestConcurrency:
    """Concurrent access to PipelineLogger is thread-safe."""

    def test_concurrent_get_task_logger(self):
        """Concurrent get_task_logger calls do not race on _loggers dict."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pl = PipelineLogger(log_dir=tmpdir)
            n = 30
            barrier = threading.Barrier(n)
            results = {}

            def get_logger(i):
                barrier.wait()
                tl = pl.get_task_logger("shared-task")
                results[i] = tl

            threads = [threading.Thread(target=get_logger, args=(i,)) for i in range(n)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            # All threads got the same logger instance
            first = results[0]
            for i in range(1, n):
                assert results[i] is first, f"Thread {i} got different logger instance"

    def test_concurrent_logging_multiple_tasks(self):
        """Concurrent logging across different task_ids is safe."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pl = PipelineLogger(log_dir=tmpdir)
            n_tasks = 10
            lines_per_task = 20
            barrier = threading.Barrier(n_tasks * lines_per_task)

            def writer(task_id, line_no):
                barrier.wait()
                tl = pl.get_task_logger(task_id)
                tl.info(stage="CONCURRENT", message=f"line {line_no} from {task_id}")

            threads = []
            for i in range(n_tasks):
                for j in range(lines_per_task):
                    t = threading.Thread(target=writer, args=(f"task-{i}", j))
                    threads.append(t)

            for t in threads:
                t.start()
            for t in threads:
                t.join()

            today = time.strftime("%Y-%m-%d")
            for i in range(n_tasks):
                log_path = Path(tmpdir) / "ingest" / today / f"task-{i}.jsonl"
                assert log_path.exists()
                lines = log_path.read_text().strip().splitlines()
                assert len(lines) == lines_per_task, f"task-{i}: expected {lines_per_task} lines, got {len(lines)}"


# =============================================================================
# Config Defaults Tests
# =============================================================================


class TestConfigDefaults:
    """Configuration default values."""

    def test_default_log_dir(self):
        """Default log_dir is ./pkos_logs."""
        tl = TaskLogger("test-default")
        assert "pkos_logs" in str(tl._log_path)

    def test_pipeline_logger_default_log_dir(self):
        """PipelineLogger default log_dir is ./pkos_logs."""
        pl = PipelineLogger()
        assert pl.log_dir == "./pkos_logs"
