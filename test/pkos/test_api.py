import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


@pytest.fixture
def client(monkeypatch):
    """Create a TestClient with a mock pipeline."""
    mock_pipeline = MagicMock()
    monkeypatch.setattr("kgsrc.pkos.api._pipeline", mock_pipeline)

    from fastapi import FastAPI
    from kgsrc.pkos.api import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app), mock_pipeline


def test_ingest_text(client):
    test_client, mock_pipeline = client
    mock_task = MagicMock()
    mock_task.task_id = "test-123"
    mock_task.status.value = "REGISTERED"
    mock_task.created_at = "2026-06-15T10:00:00"
    mock_pipeline.register.return_value = mock_task

    response = test_client.post("/pkos/v1/ingest", data={
        "source_type": "text",
        "source_url": "https://example.com",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["task_id"] == "test-123"
    assert data["status"] == "REGISTERED"


def test_ingest_text_with_identities(client):
    test_client, mock_pipeline = client
    mock_task = MagicMock()
    mock_task.task_id = "test-456"
    mock_task.status.value = "REGISTERED"
    mock_task.created_at = "2026-06-15T10:00:00"
    mock_pipeline.register.return_value = mock_task

    response = test_client.post("/pkos/v1/ingest", data={
        "source_type": "text",
        "source_url": "https://example.com",
        "identities": "程序员, 产品经理",
    })
    assert response.status_code == 201
    mock_pipeline.register.assert_called_once_with(
        source_type="text",
        source_url="https://example.com",
        identities=["程序员", "产品经理"],
    )


def test_get_task_status(client):
    test_client, mock_pipeline = client
    mock_pipeline.store.load.return_value = MagicMock(
        task_id="test-123",
        status=MagicMock(value="PARSING"),
        error=None,
        vault_path=None,
        created_at="2026-06-15T10:00:00",
        updated_at="2026-06-15T10:00:00",
    )

    response = test_client.get("/pkos/v1/ingest/test-123")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "PARSING"
    assert data["task_id"] == "test-123"


def test_get_task_status_not_found(client):
    test_client, mock_pipeline = client
    mock_pipeline.store.load.return_value = None

    response = test_client.get("/pkos/v1/ingest/nonexistent")
    assert response.status_code == 404


def test_list_vault_documents(client):
    test_client, mock_pipeline = client
    from pathlib import Path

    mock_doc_path = Path("/tmp/vault/AI/2026-06-15-test.md")
    mock_pipeline.vault.list_documents.return_value = [mock_doc_path]
    mock_pipeline.vault.vault_dir = Path("/tmp/vault")
    mock_pipeline.vault.read_document.return_value = {
        "frontmatter": {
            "title": "Test Doc",
            "identities": ["程序员"],
            "tags": ["AI"],
        },
    }

    response = test_client.get("/pkos/v1/vault/documents?topic=AI")
    assert response.status_code == 200
    data = response.json()
    assert len(data["documents"]) == 1
    assert data["documents"][0]["title"] == "Test Doc"


def test_list_vault_documents_filter_identity(client):
    test_client, mock_pipeline = client
    from pathlib import Path

    mock_doc_path = Path("/tmp/vault/AI/2026-06-15-test.md")
    mock_pipeline.vault.list_documents.return_value = [mock_doc_path]
    mock_pipeline.vault.vault_dir = Path("/tmp/vault")
    mock_pipeline.vault.read_document.return_value = {
        "frontmatter": {
            "title": "Test Doc",
            "identities": ["程序员"],
            "tags": ["AI"],
        },
    }

    response = test_client.get("/pkos/v1/vault/documents?topic=AI&identity=产品经理")
    assert response.status_code == 200
    data = response.json()
    assert len(data["documents"]) == 0  # Filtered out


def test_metrics(client):
    test_client, mock_pipeline = client
    mock_pipeline.get_metrics.return_value = {
        "ingest_tasks_total": 5,
        "ingest_tasks_by_status": {"REGISTERED": 2, "INDEXED": 3},
    }

    response = test_client.get("/pkos/v1/metrics")
    assert response.status_code == 200
    data = response.json()
    assert data["ingest_tasks_total"] == 5
    assert data["ingest_tasks_by_status"]["REGISTERED"] == 2


def test_retry_task(client):
    test_client, mock_pipeline = client
    mock_task = MagicMock()
    mock_task.status.value = "FAILED"
    mock_task.retry_count = 2
    mock_task.error = "some error"
    mock_pipeline.store.load.return_value = mock_task

    response = test_client.post("/pkos/v1/ingest/test-123/retry")
    assert response.status_code == 200
    data = response.json()
    assert data["task_id"] == "test-123"
    assert data["status"] == "REGISTERED"
    assert mock_task.retry_count == 0
    assert mock_task.error is None
    mock_pipeline.store.save.assert_called_once_with(mock_task)


def test_retry_task_not_retryable(client):
    test_client, mock_pipeline = client
    mock_task = MagicMock()
    mock_task.status.value = "REGISTERED"
    mock_pipeline.store.load.return_value = mock_task

    response = test_client.post("/pkos/v1/ingest/test-123/retry")
    assert response.status_code == 400


def test_retry_task_not_found(client):
    test_client, mock_pipeline = client
    mock_pipeline.store.load.return_value = None

    response = test_client.post("/pkos/v1/ingest/test-123/retry")
    assert response.status_code == 404
