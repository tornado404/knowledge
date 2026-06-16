"""PKOS Dashboard — FastAPI routes for task status board and Vault browsing.

All routes are mounted under /pkos/v1/dashboard and use Jinja2 templates
with htmx for partial page updates. No frontend framework required.

Usage:
    from kgsrc.pkos.dashboard import _register_pkos_dashboard_routes
    _register_pkos_dashboard_routes(app)
"""

import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import PKOSConfig
from .pipeline import IngestPipeline

# ── Router ──────────────────────────────────────────────────────────────

dashboard_router = APIRouter(prefix="/pkos/v1/dashboard", tags=["pkos-dashboard"])

# Templates (lazy init)
_templates: Optional[Jinja2Templates] = None


def _get_templates() -> Jinja2Templates:
    global _templates
    if _templates is None:
        template_dir = os.path.join(os.path.dirname(__file__), "templates")
        _templates = Jinja2Templates(directory=template_dir)
    return _templates


def _render(template_name: str, context: dict) -> str:
    """Synchronously render a Jinja2 template to a string.

    Avoids the FastAPI TemplateResponse async machinery for pre-rendering
    child templates to be embedded in the base layout.
    """
    templates = _get_templates()
    template = templates.get_template(template_name)
    return template.render(**context)


# Pipeline (lazy init, one per process)
_pipeline: Optional[IngestPipeline] = None


def _get_pipeline() -> IngestPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = IngestPipeline()
    return _pipeline


# ── Route helpers ───────────────────────────────────────────────────────

def _load_all_tasks() -> list:
    """Load all tasks from the pipeline store into a list of dicts."""
    pipeline = _get_pipeline()
    task_ids = pipeline.store.list_tasks()
    tasks = []
    for tid in task_ids:
        task = pipeline.store.load(tid)
        if task:
            tasks.append({
                "task_id": task.task_id,
                "source_type": task.source_type,
                "status": task.status.value if hasattr(task.status, "value") else task.status,
                "error": task.error,
                "vault_path": task.vault_path,
                "created_at": task.created_at,
                "updated_at": task.updated_at,
                "topic": task.topic or "",
                "identities": task.identities or [],
                "tags": task.tags or [],
                "retry_count": task.retry_count,
            })
    # Sort newest first
    tasks.sort(key=lambda t: t.get("created_at", ""), reverse=True)
    return tasks


def _get_task_detail(task_id: str) -> Optional[dict]:
    """Load a single task by ID."""
    pipeline = _get_pipeline()
    task = pipeline.store.load(task_id)
    if not task:
        return None
    return {
        "task_id": task.task_id,
        "source_type": task.source_type,
        "status": task.status.value if hasattr(task.status, "value") else task.status,
        "error": task.error,
        "vault_path": task.vault_path,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "topic": task.topic or "",
        "identities": task.identities or [],
        "tags": task.tags or [],
        "retry_count": task.retry_count,
    }


def _render_page(
    request: Request,
    template_name: str,
    context: dict,
    active_tab: str,
) -> HTMLResponse:
    """Render a full page with base layout or just the content (htmx).

    When HX-Request header is present, returns only the content template.
    Otherwise, pre-renders the content and wraps it in base.html.
    """
    templates = _get_templates()
    is_htmx = request.headers.get("HX-Request") == "true"

    if is_htmx:
        return templates.TemplateResponse(
            name=template_name,
            context={"request": request, **context},
            request=request,
        )

    # Pre-render content template to string (avoids Jinja2 include cache issues)
    content_html = _render(template_name, {"request": request, **context})
    return templates.TemplateResponse(
        name="base.html",
        context={
            "request": request,
            "content_html": content_html,
            "active_tab": active_tab,
        },
        request=request,
    )


# ── Routes ──────────────────────────────────────────────────────────────


@dashboard_router.get("", include_in_schema=False)
async def dashboard_root():
    """Redirect to /pkos/v1/dashboard/tasks."""
    return RedirectResponse(url="/pkos/v1/dashboard/tasks")


@dashboard_router.get("/tasks", response_class=HTMLResponse)
async def dashboard_tasks(
    request: Request,
    status: Optional[str] = Query(None, description="Filter by task status"),
):
    """Task list page with optional status filter."""
    tasks = _load_all_tasks()

    if status:
        filtered = [t for t in tasks if t["status"] == status.upper()]
    else:
        filtered = tasks

    return _render_page(
        request,
        "tasks.html",
        {"tasks": filtered, "current_status": status or ""},
        active_tab="tasks",
    )


@dashboard_router.get("/tasks/{task_id}", response_class=HTMLResponse)
async def dashboard_task_detail(request: Request, task_id: str):
    """Single task detail (HTML fragment)."""
    task = _get_task_detail(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    templates = _get_templates()
    return templates.TemplateResponse(
        name="task_detail.html",
        context={"request": request, "task": task},
        request=request,
    )


@dashboard_router.get("/vault", response_class=HTMLResponse)
async def dashboard_vault(
    request: Request,
    topic: Optional[str] = Query(None),
    identity: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
):
    """Vault document list page with optional filters."""
    pipeline = _get_pipeline()
    docs = pipeline.vault.list_documents(topic=topic)

    results = []
    for doc_path in docs:
        try:
            data = pipeline.vault.read_document(str(doc_path))
            fm = data.get("frontmatter", {})
            doc_identities = fm.get("identities", [])
            doc_tags = fm.get("tags", [])

            if identity and identity not in doc_identities:
                continue
            if tag and tag not in doc_tags:
                continue

            results.append({
                "path": str(doc_path.relative_to(pipeline.vault.vault_dir)),
                "title": fm.get("title", doc_path.stem),
                "topic": fm.get("topic", ""),
                "identities": doc_identities,
                "tags": doc_tags,
            })
        except Exception:
            continue

    # Get available topics for filter dropdown
    topics = pipeline.vault.list_topics()

    return _render_page(
        request,
        "vault.html",
        {
            "documents": results,
            "topics": topics,
            "current_topic": topic or "",
            "current_identity": identity or "",
            "current_tag": tag or "",
        },
        active_tab="vault",
    )


@dashboard_router.get("/vault/{path:path}", response_class=HTMLResponse)
async def dashboard_vault_doc(request: Request, path: str):
    """Single document preview (HTML fragment)."""
    pipeline = _get_pipeline()
    vault_path = pipeline.vault.vault_dir / path

    try:
        data = pipeline.vault.read_document(str(vault_path))
    except Exception:
        raise HTTPException(status_code=404, detail="Document not found")

    if data is None:
        raise HTTPException(status_code=404, detail="Document not found")

    templates = _get_templates()
    return templates.TemplateResponse(
        name="vault_doc.html",
        context={"request": request, "doc": data},
        request=request,
    )


@dashboard_router.get("/metrics", response_class=HTMLResponse)
async def dashboard_metrics(request: Request):
    """Metrics dashboard page."""
    pipeline = _get_pipeline()
    metrics = pipeline.get_metrics()

    total = metrics.get("ingest_tasks_total", 0)
    by_status = metrics.get("ingest_tasks_by_status", {})

    return _render_page(
        request,
        "metrics.html",
        {"total": total, "by_status": by_status},
        active_tab="metrics",
    )


# ── Registration function ───────────────────────────────────────────────


def _register_pkos_dashboard_routes(app: FastAPI):
    """Register dashboard routes if enabled.

    Called from chat.py (or any FastAPI app) to optionally mount
    the PKOS Dashboard. Controlled by PKOS_DASHBOARD_ENABLED env var.

    Args:
        app: FastAPI application instance.
    """
    config = PKOSConfig.from_base()
    if not config.pkos_dashboard_enabled:
        return

    # Mount static files
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    if os.path.isdir(static_dir):
        app.mount(
            "/pkos/v1/dashboard/static",
            StaticFiles(directory=static_dir),
            name="dashboard_static",
        )

    # Register dashboard router
    app.include_router(dashboard_router)
