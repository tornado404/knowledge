"""PKOS FastAPI router for ingest pipeline endpoints."""

from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel, Field

from .pipeline import IngestPipeline


router = APIRouter(prefix="/pkos/v1", tags=["pkos"])

# Global pipeline instance (lazy init)
_pipeline: Optional[IngestPipeline] = None


def get_pipeline() -> IngestPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = IngestPipeline()
    return _pipeline


class IngestResponse(BaseModel):
    task_id: str
    status: str
    created_at: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    stage: Optional[str] = None
    error: Optional[str] = None
    vault_path: Optional[str] = None
    created_at: str
    updated_at: str


class VaultDocument(BaseModel):
    path: str
    title: str
    identities: list = []
    tags: list = []


class VaultSearchResponse(BaseModel):
    documents: list = []


class MetricsResponse(BaseModel):
    ingest_tasks_total: int
    ingest_tasks_by_status: dict


@router.post("/ingest", response_model=IngestResponse, status_code=201)
async def ingest(
    source_type: str = Form(...),
    source_url: Optional[str] = Form(None),
    identities: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
):
    """Register a new ingest task."""
    pipeline = get_pipeline()

    id_list = []
    if identities:
        id_list = [i.strip() for i in identities.split(",") if i.strip()]

    task = pipeline.register(
        source_type=source_type,
        source_url=source_url,
        identities=id_list,
    )

    # If file uploaded, save to inbox for later processing
    if file:
        inbox_path = pipeline.inbox_dir / f"{task.task_id}_{file.filename}"
        content = await file.read()
        with open(inbox_path, "wb") as f:
            f.write(content)

    return IngestResponse(
        task_id=task.task_id,
        status=task.status.value,
        created_at=task.created_at,
    )


@router.get("/ingest/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """Get ingest task status."""
    pipeline = get_pipeline()
    task = pipeline.store.load(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return TaskStatusResponse(
        task_id=task.task_id,
        status=task.status.value,
        stage=task.status.value,
        error=task.error,
        vault_path=task.vault_path,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@router.get("/vault/documents", response_model=VaultSearchResponse)
async def list_vault_documents(
    identity: Optional[str] = None,
    tag: Optional[str] = None,
    topic: Optional[str] = None,
):
    """List Vault documents with optional filtering."""
    pipeline = get_pipeline()
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

            results.append(VaultDocument(
                path=str(doc_path.relative_to(pipeline.vault.vault_dir)),
                title=fm.get("title", doc_path.stem),
                identities=doc_identities,
                tags=doc_tags,
            ))
        except Exception:
            continue

    return VaultSearchResponse(documents=results)


@router.get("/vault/search")
async def search_vault(q: str, k: int = 4):
    """Search Vault documents using Milvus vector search."""
    from ..knowledge_vector.vectorstore import MilvusVectorStore

    try:
        vs = MilvusVectorStore()
        vs.load()
        docs = vs.search(q, k=k)
        return {
            "results": [
                {
                    "source": doc.metadata.get("source", ""),
                    "content": doc.page_content[:300],
                }
                for doc in docs
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {e}")


@router.get("/metrics", response_model=MetricsResponse)
async def get_metrics():
    """Get pipeline metrics."""
    pipeline = get_pipeline()
    metrics = pipeline.get_metrics()
    return MetricsResponse(
        ingest_tasks_total=metrics["ingest_tasks_total"],
        ingest_tasks_by_status=metrics["ingest_tasks_by_status"],
    )


@router.post("/ingest/{task_id}/retry")
async def retry_task(task_id: str):
    """Retry a failed task from dead letter."""
    pipeline = get_pipeline()
    task = pipeline.store.load(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status.value not in ("FAILED", "DEAD_LETTER"):
        raise HTTPException(status_code=400, detail="Task is not in retryable state")

    # Reset and re-process
    from .models import TaskStatus
    task.status = TaskStatus.REGISTERED
    task.retry_count = 0
    task.error = None
    pipeline.store.save(task)

    return {"task_id": task_id, "status": "REGISTERED", "message": "Task queued for retry"}
