"""
Indexing endpoints for managing document indexing jobs
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Optional
from pydantic import BaseModel
import sys
import os
import uuid

# Add parent directories to path to import existing modules
sys.path.append(os.path.join(os.path.dirname(__file__), "../../../../.."))

from app.core.config import settings

router = APIRouter()


class IndexingJob(BaseModel):
    """Indexing job model."""

    id: str
    status: str
    progress: float
    total_documents: int
    processed_documents: int
    error_message: Optional[str] = None


class IndexingRequest(BaseModel):
    """Indexing request model."""

    source_type: str  # "json" or "markdown"
    source_path: str
    collection_name: str = "articles"
    chunk_size: int = 150
    chunk_overlap: int = 30
    embedding_model: str = "embeddinggemma:latest"


@router.post("/", response_model=IndexingJob)
async def start_indexing(request: IndexingRequest, background_tasks: BackgroundTasks):
    """Start an indexing job."""
    try:
        job_id = str(uuid.uuid4())

        # TODO: Implement indexing using existing index_qdrant.py logic
        # background_tasks.add_task(run_indexing_job, job_id, request)

        return IndexingJob(
            id=job_id,
            status="running",
            progress=0.0,
            total_documents=0,
            processed_documents=0,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to start indexing: {str(e)}"
        )


@router.get("/jobs", response_model=List[IndexingJob])
async def get_indexing_jobs():
    """Get all indexing jobs."""
    return []


@router.get("/jobs/{job_id}", response_model=IndexingJob)
async def get_indexing_job(job_id: str):
    """Get specific indexing job status."""
    # TODO: Implement job status tracking
    return IndexingJob(
        id=job_id,
        status="completed",
        progress=100.0,
        total_documents=0,
        processed_documents=0,
    )
