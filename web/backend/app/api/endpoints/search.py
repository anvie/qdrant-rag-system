"""
Search endpoints for querying documents
"""

from fastapi import APIRouter, HTTPException
from typing import List, Optional
from pydantic import BaseModel
import sys
import os
import traceback
from datetime import datetime

# Add parent directories to path to import existing modules
sys.path.append(os.path.join(os.path.dirname(__file__), "../../../../.."))


router = APIRouter()


class SearchRequest(BaseModel):
    """Enhanced search request model."""

    query: str
    collection: str = "articles"
    limit: int = 10
    min_score: float = 0.0
    hybrid: bool = False
    fusion_method: str = "rrf"  # rrf or dbsf
    article_id: Optional[int] = None
    group_by_article: bool = False


class SearchResult(BaseModel):
    """Enhanced search result model."""

    id: str
    score: float
    article_id: str
    chunk_index: int
    title: str
    content: str
    text: str


class SearchResponse(BaseModel):
    """Search response with metadata."""

    results: List[SearchResult]
    total_found: int
    query_time: float
    collection: str
    query: str
    hybrid: bool
    fusion_method: Optional[str] = None
    grouped_by_article: bool = False


class ArticleResponse(BaseModel):
    """Article with all chunks response."""

    article_id: str
    title: str
    chunks: List[SearchResult]
    total_chunks: int


class CollectionStats(BaseModel):
    """Collection statistics model."""

    collection_name: str
    total_points: int
    indexed_points: int
    total_vectors: int
    dimension: int
    status: str


# Import search service
from app.services.search_service import get_search_service


@router.post("/", response_model=SearchResponse)
async def search_documents(request: SearchRequest):
    """Search documents using vector similarity with hybrid option."""
    start_time = datetime.now()

    try:
        search_service = get_search_service()

        # Perform search based on mode
        if request.hybrid:
            search_results = await search_service.search_hybrid(
                query=request.query,
                collection=request.collection,
                limit=request.limit,
                min_score=request.min_score,
                article_id=request.article_id,
                fusion_method=request.fusion_method,
            )
        else:
            search_results = await search_service.search_simple(
                query=request.query,
                collection=request.collection,
                limit=request.limit,
                min_score=request.min_score,
                article_id=request.article_id,
            )

        # Group results by article if requested
        if request.group_by_article and search_results:
            search_results = search_service.group_results_by_article(search_results)

        # Convert to response format
        results = []
        for result in search_results:
            payload = result.get("payload", {})
            results.append(
                SearchResult(
                    id=str(result["id"]),
                    score=result["score"],
                    article_id=str(payload.get("article_id", 0)),
                    chunk_index=payload.get("chunk_index", 0),
                    title=payload.get("title", ""),
                    content=payload.get("content", ""),
                    text=payload.get("text", ""),
                )
            )

        query_time = (datetime.now() - start_time).total_seconds()

        return SearchResponse(
            results=results,
            total_found=len(results),
            query_time=query_time,
            collection=request.collection,
            query=request.query,
            hybrid=request.hybrid,
            fusion_method=request.fusion_method if request.hybrid else None,
            grouped_by_article=request.group_by_article,
        )

    except Exception as e:
        traceback.print_exception(type(e), e, e.__traceback__)
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/collections/{collection_name}/stats", response_model=CollectionStats)
async def get_collection_statistics(collection_name: str):
    """Get collection statistics."""
    try:
        search_service = get_search_service()
        stats = await search_service.get_collection_stats(collection_name)

        return CollectionStats(
            collection_name=collection_name,
            total_points=stats.get("points_count", 0),
            indexed_points=stats.get("indexed_vectors_count", 0),
            total_vectors=stats.get("vectors_count", 0),
            dimension=stats.get("config", {})
            .get("params", {})
            .get("vectors", {})
            .get("size", 0),
            status=stats.get("status", "unknown"),
        )

    except Exception as e:
        traceback.print_exception(type(e), e, e.__traceback__)
        raise HTTPException(
            status_code=500, detail=f"Failed to get collection stats: {str(e)}"
        )


@router.get("/article/{article_id}", response_model=ArticleResponse)
async def get_full_article(article_id: str, collection: str = "articles"):
    """Get full article with all chunks."""
    try:
        search_service = get_search_service()
        chunks = await search_service.get_article(collection, article_id)

        if not chunks:
            raise HTTPException(
                status_code=404, detail=f"Article {article_id} not found"
            )

        # Convert chunks to SearchResult format
        search_results = []
        title = ""
        for chunk in chunks:
            payload = chunk.get("payload", {})
            if not title:
                title = payload.get("title", f"Article {article_id}")

            search_results.append(
                SearchResult(
                    id=str(chunk["id"]),
                    score=1.0,  # Full article retrieval, no scoring
                    article_id=str(article_id),
                    chunk_index=payload.get("chunk_index", 0),
                    title=payload.get("title", ""),
                    content=payload.get("content", ""),
                    text=payload.get("text", ""),
                )
            )

        # Sort by chunk index for proper ordering
        search_results.sort(key=lambda x: x.chunk_index)

        return ArticleResponse(
            article_id=article_id,
            title=title,
            chunks=search_results,
            total_chunks=len(search_results),
        )

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exception(type(e), e, e.__traceback__)
        raise HTTPException(status_code=500, detail=f"Failed to get article: {str(e)}")


@router.post("/similar", response_model=SearchResponse)
async def find_similar_documents(
    document_id: int, collection: str = "articles", limit: int = 10
):
    """Find documents similar to the given document."""
    try:
        search_service = get_search_service()
        search_results = await search_service.find_similar(
            document_id, collection, limit
        )

        # Convert to response format
        results = []
        for result in search_results:
            payload = result.get("payload", {})
            results.append(
                SearchResult(
                    id=str(result["id"]),
                    score=result["score"],
                    article_id=str(payload.get("article_id", 0)),
                    chunk_index=payload.get("chunk_index", 0),
                    title=payload.get("title", ""),
                    content=payload.get("content", ""),
                    text=payload.get("text", ""),
                )
            )

        return SearchResponse(
            results=results,
            total_found=len(results),
            query_time=0.0,
            collection=collection,
            query=f"Similar to document {document_id}",
            hybrid=False,
            grouped_by_article=False,
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        traceback.print_exception(type(e), e, e.__traceback__)
        raise HTTPException(
            status_code=500, detail=f"Failed to find similar documents: {str(e)}"
        )


@router.get("/history")
async def get_search_history():
    """Get search history (placeholder for future implementation)."""
    return {"history": []}
