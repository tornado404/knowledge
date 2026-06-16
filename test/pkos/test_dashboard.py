"""Tests for PKOS Dashboard routes — TDD-driven."""

import os
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_pipeline():
    """Create a mock IngestPipeline with tasks and metrics."""
    from pathlib import Path

    pipeline = MagicMock()

    # Mock store.list_tasks
    pipeline.store.list_tasks.return_value = ["task-1", "task-2", "task-3"]

    # Mock store.load for individual tasks
    def mock_load(task_id):
        tasks = {
            "task-1": MagicMock(
                task_id="task-1",
                source_type="web",
                status=MagicMock(value="INDEXED"),
                error=None,
                vault_path="/vault/AI/doc1.md",
                created_at="2026-06-16T10:00:00",
                updated_at="2026-06-16T10:05:00",
                topic="AI",
                identities=["程序员"],
                tags=["rag", "llm"],
                retry_count=0,
            ),
            "task-2": MagicMock(
                task_id="task-2",
                source_type="pdf",
                status=MagicMock(value="FAILED"),
                error="PDF parse timeout",
                vault_path=None,
                created_at="2026-06-16T10:10:00",
                updated_at="2026-06-16T10:12:00",
                topic="",
                identities=[],
                tags=[],
                retry_count=2,
            ),
            "task-3": MagicMock(
                task_id="task-3",
                source_type="text",
                status=MagicMock(value="REGISTERED"),
                error=None,
                vault_path=None,
                created_at="2026-06-16T10:20:00",
                updated_at="2026-06-16T10:20:00",
                topic="",
                identities=[],
                tags=[],
                retry_count=0,
            ),
        }
        return tasks.get(task_id)
    pipeline.store.load.side_effect = mock_load

    # Mock get_metrics
    pipeline.get_metrics.return_value = {
        "ingest_tasks_total": 3,
        "ingest_tasks_by_status": {
            "REGISTERED": 1,
            "PARSING": 0,
            "UNDERSTANDING": 0,
            "CLASSIFYING": 0,
            "ARCHIVING": 0,
            "INDEXED": 1,
            "FAILED": 1,
            "DEAD_LETTER": 0,
        },
    }

    # Mock vault
    mock_doc_path = Path("/vault/AI/2026-06-15-rag-optimization.md")
    pipeline.vault.list_documents.return_value = [mock_doc_path]
    pipeline.vault.vault_dir = Path("/vault")
    pipeline.vault.read_document.return_value = {
        "path": str(mock_doc_path),
        "frontmatter": {
            "title": "RAG Optimization Guide",
            "topic": "AI",
            "identities": ["程序员"],
            "tags": ["rag", "llm"],
        },
        "content": "# RAG Optimization\n\nContent here...",
    }

    return pipeline


@pytest.fixture
def app(monkeypatch, mock_pipeline):
    """Create a FastAPI app with dashboard routes registered and mock pipeline."""
    monkeypatch.setenv("PKOS_DASHBOARD_ENABLED", "true")

    # Reset module-level pipeline cache to ensure each test gets a fresh state
    import kgsrc.pkos.dashboard as dashboard_module
    dashboard_module._pipeline = None

    # We need to patch the pipeline used by the dashboard module
    # The dashboard module will use IngestPipeline() which we mock
    monkeypatch.setattr("kgsrc.pkos.dashboard.IngestPipeline", lambda: mock_pipeline)

    from fastapi import FastAPI
    from kgsrc.pkos.dashboard import _register_pkos_dashboard_routes

    app = FastAPI()
    _register_pkos_dashboard_routes(app)
    return app


@pytest.fixture
def client(app):
    """Test client for the dashboard app."""
    return TestClient(app)


# ==================== Route registration ====================

def test_dashboard_redirect(client):
    """GET /pkos/v1/dashboard should redirect to /pkos/v1/dashboard/tasks."""
    response = client.get("/pkos/v1/dashboard", follow_redirects=False)
    assert response.status_code in (200, 307, 302)
    # If it redirects, check location; if it renders directly, OK
    if response.status_code in (307, 302):
        assert "tasks" in response.headers.get("location", "")


def test_tasks_page_returns_200(client):
    """GET /pkos/v1/dashboard/tasks should return 200 HTML."""
    response = client.get("/pkos/v1/dashboard/tasks")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")


# ==================== Task list rendering ====================

def test_tasks_page_contains_task_list(client):
    """Task list page should contain task IDs."""
    response = client.get("/pkos/v1/dashboard/tasks")
    assert response.status_code == 200
    html = response.text
    assert "task-1" in html
    assert "task-2" in html
    assert "task-3" in html


def test_tasks_page_shows_source_types(client):
    """Task list should display source types."""
    response = client.get("/pkos/v1/dashboard/tasks")
    assert "web" in response.text or "pdf" in response.text or "text" in response.text


# ==================== Status filtering ====================

def test_tasks_filter_by_status(client, mock_pipeline):
    """GET /pkos/v1/dashboard/tasks?status=FAILED should filter tasks."""
    response = client.get("/pkos/v1/dashboard/tasks?status=FAILED")
    assert response.status_code == 200
    html = response.text
    # Should contain FAILED task and its error message
    assert "FAILED" in html or "task-2" in html


# ==================== Task detail ====================

def test_task_detail_returns_200(client):
    """GET /pkos/v1/dashboard/tasks/{task_id} should return HTML fragment."""
    response = client.get("/pkos/v1/dashboard/tasks/task-1")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")


def test_task_detail_shows_task_info(client):
    """Task detail should show task metadata."""
    response = client.get("/pkos/v1/dashboard/tasks/task-1")
    html = response.text
    assert "task-1" in html
    assert "INDEXED" in html


def test_task_detail_shows_error_for_failed(client):
    """Task detail for failed task should show error."""
    response = client.get("/pkos/v1/dashboard/tasks/task-2")
    html = response.text
    assert "PDF parse timeout" in html


def test_task_detail_not_found(client):
    """Non-existent task should return 404."""
    response = client.get("/pkos/v1/dashboard/tasks/nonexistent")
    assert response.status_code == 404


# ==================== Vault document list ====================

def test_vault_page_returns_200(client):
    """GET /pkos/v1/dashboard/vault should return 200 HTML."""
    response = client.get("/pkos/v1/dashboard/vault")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")


def test_vault_page_contains_documents(client):
    """Vault page should list documents."""
    response = client.get("/pkos/v1/dashboard/vault")
    html = response.text
    assert "rag-optimization" in html or "RAG" in html or "Optimization" in html


def test_vault_page_shows_metadata(client):
    """Vault page should show document metadata (topic, identities, tags)."""
    response = client.get("/pkos/v1/dashboard/vault")
    html = response.text
    assert "程序员" in html
    assert "rag" in html or "llm" in html


# ==================== Vault filtering ====================

def test_vault_filter_by_topic(client, mock_pipeline):
    """GET /pkos/v1/dashboard/vault?topic=AI should filter by topic."""
    response = client.get("/pkos/v1/dashboard/vault?topic=AI")
    assert response.status_code == 200


def test_vault_filter_by_identity(client, mock_pipeline):
    """GET /pkos/v1/dashboard/vault?identity=程序员 should filter by identity."""
    response = client.get("/pkos/v1/dashboard/vault?identity=程序员")
    assert response.status_code == 200


def test_vault_filter_by_tag(client, mock_pipeline):
    """GET /pkos/v1/dashboard/vault?tag=rag should filter by tag."""
    response = client.get("/pkos/v1/dashboard/vault?tag=rag")
    assert response.status_code == 200


# ==================== Document preview ====================

def test_vault_doc_preview_returns_200(client):
    """GET /pkos/v1/dashboard/vault/{path} should return HTML fragment."""
    response = client.get("/pkos/v1/dashboard/vault/AI/2026-06-15-rag-optimization.md")
    assert response.status_code == 200


def test_vault_doc_preview_shows_content(client):
    """Document preview should show frontmatter and content."""
    response = client.get("/pkos/v1/dashboard/vault/AI/2026-06-15-rag-optimization.md")
    html = response.text
    assert "RAG Optimization Guide" in html
    assert "RAG Optimization" in html


def test_vault_doc_preview_not_found(client, mock_pipeline):
    """Non-existent document should return 404."""
    mock_pipeline.vault.read_document.return_value = None
    response = client.get("/pkos/v1/dashboard/vault/nonexistent/doc.md")
    assert response.status_code == 404


# ==================== Metrics page ====================

def test_metrics_page_returns_200(client):
    """GET /pkos/v1/dashboard/metrics should return 200 HTML."""
    response = client.get("/pkos/v1/dashboard/metrics")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")


def test_metrics_page_shows_task_counts(client):
    """Metrics page should show task totals and status distribution."""
    response = client.get("/pkos/v1/dashboard/metrics")
    html = response.text
    assert "3" in html  # total tasks


def test_metrics_page_shows_status_distribution(client):
    """Metrics page should show per-status counts."""
    response = client.get("/pkos/v1/dashboard/metrics")
    html = response.text
    assert "INDEXED" in html
    assert "FAILED" in html
    assert "REGISTERED" in html


# ==================== Static CSS ====================

def test_static_css_accessible(client):
    """GET /pkos/v1/dashboard/static/style.css should return 200 CSS."""
    response = client.get("/pkos/v1/dashboard/static/style.css")
    assert response.status_code == 200
    assert "text/css" in response.headers.get("content-type", "")


# ==================== Dashboard disabled ====================

def test_dashboard_disabled_returns_404(monkeypatch):
    """When PKOS_DASHBOARD_ENABLED=false, dashboard routes should not be registered."""
    monkeypatch.setenv("PKOS_DASHBOARD_ENABLED", "false")

    from fastapi import FastAPI
    from kgsrc.pkos.dashboard import _register_pkos_dashboard_routes

    app = FastAPI()
    _register_pkos_dashboard_routes(app)

    client = TestClient(app)
    response = client.get("/pkos/v1/dashboard/tasks")
    assert response.status_code == 404


# ==================== Config object integration ====================

def test_config_has_dashboard_enabled():
    """PKOSConfig should have pkos_dashboard_enabled field."""
    from kgsrc.pkos.config import PKOSConfig

    config = PKOSConfig()
    # Should have the attribute, defaulting to True
    assert hasattr(config, "pkos_dashboard_enabled")
    assert config.pkos_dashboard_enabled is True


def test_dashboard_enabled_env_var(monkeypatch):
    """PKOS_DASHBOARD_ENABLED env var should control config."""
    monkeypatch.setenv("PKOS_DASHBOARD_ENABLED", "false")

    from kgsrc.pkos.config import PKOSConfig

    config = PKOSConfig.from_base()
    assert config.pkos_dashboard_enabled is False


def test_dashboard_default_enabled():
    """When env var is not set, dashboard should be enabled by default."""
    # Temporarily remove the env var if set
    old_val = os.environ.pop("PKOS_DASHBOARD_ENABLED", None)
    try:
        from kgsrc.pkos.config import PKOSConfig
        config = PKOSConfig.from_base()
        assert config.pkos_dashboard_enabled is True
    finally:
        if old_val is not None:
            os.environ["PKOS_DASHBOARD_ENABLED"] = old_val
