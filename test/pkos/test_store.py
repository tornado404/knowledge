import pytest
from datetime import datetime
from kgsrc.pkos.models import IngestTask, TaskStatus, ParsedContent


def test_task_status_values():
    assert TaskStatus.REGISTERED.value == "REGISTERED"
    assert TaskStatus.PARSING.value == "PARSING"
    assert TaskStatus.UNDERSTANDING.value == "UNDERSTANDING"
    assert TaskStatus.CLASSIFYING.value == "CLASSIFYING"
    assert TaskStatus.ARCHIVING.value == "ARCHIVING"
    assert TaskStatus.INDEXED.value == "INDEXED"
    assert TaskStatus.FAILED.value == "FAILED"
    assert TaskStatus.DEAD_LETTER.value == "DEAD_LETTER"


def test_ingest_task_defaults():
    task = IngestTask(task_id="test-001", source_type="text")
    assert task.task_id == "test-001"
    assert task.status == TaskStatus.REGISTERED
    assert task.source_type == "text"
    assert task.retry_count == 0
    assert task.error is None
    assert task.vault_path is None


def test_ingest_task_to_dict():
    task = IngestTask(
        task_id="test-002",
        source_type="pdf",
        status=TaskStatus.PARSING,
        retry_count=1,
        error="test error",
    )
    d = task.to_dict()
    assert d["task_id"] == "test-002"
    assert d["status"] == "PARSING"
    assert d["retry_count"] == 1
    assert d["error"] == "test error"


def test_ingest_task_from_dict():
    data = {
        "task_id": "test-003",
        "status": "UNDERSTANDING",
        "source_type": "web",
        "source_url": "https://example.com",
        "retry_count": 2,
        "error": None,
        "vault_path": None,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    task = IngestTask.from_dict(data)
    assert task.task_id == "test-003"
    assert task.status == TaskStatus.UNDERSTANDING
    assert task.retry_count == 2


def test_parsed_content():
    pc = ParsedContent(raw_text="hello world", title="Hello")
    assert pc.raw_text == "hello world"
    assert pc.title == "Hello"
    assert pc.entities == []


import tempfile
import shutil
from pathlib import Path
from kgsrc.pkos.store import IngestTaskStore


def test_store_save_and_load():
    tmpdir = tempfile.mkdtemp()
    try:
        store = IngestTaskStore(storage_dir=tmpdir)
        task = IngestTask(task_id="store-001", source_type="text")
        assert store.save(task) is True

        loaded = store.load("store-001")
        assert loaded is not None
        assert loaded.task_id == "store-001"
        assert loaded.status == TaskStatus.REGISTERED
    finally:
        shutil.rmtree(tmpdir)


def test_store_load_missing():
    tmpdir = tempfile.mkdtemp()
    try:
        store = IngestTaskStore(storage_dir=tmpdir)
        assert store.load("missing") is None
    finally:
        shutil.rmtree(tmpdir)


def test_store_list():
    tmpdir = tempfile.mkdtemp()
    try:
        store = IngestTaskStore(storage_dir=tmpdir)
        store.save(IngestTask(task_id="a", source_type="text"))
        store.save(IngestTask(task_id="b", source_type="pdf"))
        ids = store.list_tasks()
        assert sorted(ids) == ["a", "b"]
    finally:
        shutil.rmtree(tmpdir)


def test_store_update():
    tmpdir = tempfile.mkdtemp()
    try:
        store = IngestTaskStore(storage_dir=tmpdir)
        task = IngestTask(task_id="update-001", source_type="text")
        store.save(task)

        task.status = TaskStatus.PARSING
        task.retry_count = 1
        store.save(task)

        loaded = store.load("update-001")
        assert loaded.status == TaskStatus.PARSING
        assert loaded.retry_count == 1
    finally:
        shutil.rmtree(tmpdir)


def test_store_cleanup_expired():
    tmpdir = tempfile.mkdtemp()
    try:
        store = IngestTaskStore(storage_dir=tmpdir, max_age_days=0)
        store.save(IngestTask(task_id="old", source_type="text"))
        deleted = store.cleanup_expired()
        assert deleted >= 0
    finally:
        shutil.rmtree(tmpdir)
