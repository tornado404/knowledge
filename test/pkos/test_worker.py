"""Tests for TaskWorker — background task processing."""

import threading
import queue
from unittest.mock import MagicMock, patch
from kgsrc.pkos.worker import TaskWorker


def test_worker_start_stop():
    """Worker starts and stops without error."""
    mock_pipeline = MagicMock()
    worker = TaskWorker(pipeline=mock_pipeline)

    assert worker._thread is None
    assert not worker._running.is_set()

    worker.start()
    assert worker._thread is not None
    assert worker._thread.is_alive()
    assert worker._running.is_set()

    worker.stop()
    worker._thread.join(timeout=2.0)
    assert not worker._thread.is_alive()


def test_worker_submit_processes_task():
    """After submit, worker processes the task via pipeline."""
    mock_pipeline = MagicMock()
    worker = TaskWorker(pipeline=mock_pipeline)
    worker.start()

    try:
        worker.submit("task-1", raw_text="hello", file_path="/tmp/test.md")

        # Wait a bit for processing
        import time
        time.sleep(0.3)

        mock_pipeline.process_task.assert_called_once_with(
            "task-1", raw_text="hello", file_path="/tmp/test.md"
        )
    finally:
        worker.stop()
        worker._thread.join(timeout=2.0)


def test_worker_submit_without_raw_text():
    """submit works with only task_id (raw_text and file_path optional)."""
    mock_pipeline = MagicMock()
    worker = TaskWorker(pipeline=mock_pipeline)
    worker.start()

    try:
        worker.submit("task-2")

        import time
        time.sleep(0.3)

        mock_pipeline.process_task.assert_called_once_with(
            "task-2", raw_text=None, file_path=None
        )
    finally:
        worker.stop()
        worker._thread.join(timeout=2.0)


def test_worker_process_multiple_tasks():
    """Worker processes multiple submitted tasks sequentially."""
    mock_pipeline = MagicMock()
    worker = TaskWorker(pipeline=mock_pipeline)
    worker.start()

    try:
        worker.submit("task-a", raw_text="first")
        worker.submit("task-b", raw_text="second")

        import time
        time.sleep(0.5)

        assert mock_pipeline.process_task.call_count == 2
        mock_pipeline.process_task.assert_any_call("task-a", raw_text="first", file_path=None)
        mock_pipeline.process_task.assert_any_call("task-b", raw_text="second", file_path=None)
    finally:
        worker.stop()
        worker._thread.join(timeout=2.0)


def test_worker_handles_pipeline_exception():
    """Worker continues after pipeline raises an exception."""
    mock_pipeline = MagicMock()
    mock_pipeline.process_task.side_effect = [RuntimeError("processing failed"), None]

    worker = TaskWorker(pipeline=mock_pipeline)
    worker.start()

    try:
        worker.submit("task-fail", raw_text="boom")
        worker.submit("task-ok", raw_text="fine")

        import time
        time.sleep(0.5)

        # Both tasks should have been attempted
        assert mock_pipeline.process_task.call_count == 2
    finally:
        worker.stop()
        worker._thread.join(timeout=2.0)


def test_worker_config_disabled():
    """When worker is disabled (config.worker_enabled=False), start is a no-op."""
    mock_pipeline = MagicMock()
    worker = TaskWorker(pipeline=mock_pipeline, enabled=False)

    worker.start()
    # No thread should be created
    assert worker._thread is None

    # submit should still work but nothing processes
    worker.submit("task-disabled", raw_text="nope")
    import time
    time.sleep(0.2)
    mock_pipeline.process_task.assert_not_called()


def test_worker_daemon_thread():
    """Worker thread is a daemon thread."""
    mock_pipeline = MagicMock()
    worker = TaskWorker(pipeline=mock_pipeline)
    worker.start()

    try:
        assert worker._thread is not None
        assert worker._thread.daemon is True
    finally:
        worker.stop()
        worker._thread.join(timeout=2.0)
