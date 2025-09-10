"""
Search endpoints for querying documents
"""

from fastapi import APIRouter, HTTPException
from typing import List, Optional
from pydantic import BaseModel
import sys
import os

# Add parent directories to path to import existing modules
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../../..'))

from app.core.config import settings

router = APIRouter()


class SearchRequest(BaseModel):
    """Search request model."""
    query: str
    limit: int = 10
    min_score: float = 0.0
    hybrid: bool = False
    collection: str = "articles"


class SearchResult(BaseModel):
    """Search result model."""
    id: int
    score: float
    title: str
    content: str
    article_id: int
    chunk_index: int


@router.post("/", response_model=List[SearchResult])
async def search_documents(request: SearchRequest):
    """Search documents using vector similarity."""
    try:
        # TODO: Implement search using existing query_qdrant.py logic
        return []
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/history")
async def get_search_history():
    """Get search history."""
    return {"history": []}