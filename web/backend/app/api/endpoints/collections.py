"""
Collections management endpoints
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Optional
from pydantic import BaseModel
import sys
import os

# Add parent directories to path to import existing modules
sys.path.append(os.path.join(os.path.dirname(__file__), "../../../../.."))

from query_qdrant import get_collection_stats
from qdrant_client import QdrantClient
from app.core.config import settings

router = APIRouter()


class CollectionResponse(BaseModel):
    """Collection information response model."""

    name: str
    points_count: int
    vectors_count: int
    status: str


class CollectionCreate(BaseModel):
    """Collection creation request model."""

    name: str
    vector_size: int
    distance_metric: str = "cosine"


class CollectionStats(BaseModel):
    """Detailed collection statistics."""

    name: str
    points_count: int
    vectors_count: int
    status: str
    config: dict


@router.get("/", response_model=List[CollectionResponse])
async def list_collections():
    """List all collections in Qdrant."""
    try:
        client = QdrantClient(url=settings.QDRANT_URL)
        collections = client.get_collections()

        result = []
        for collection in collections.collections:
            stats = get_collection_stats(client, collection.name)
            result.append(
                CollectionResponse(
                    name=collection.name,
                    points_count=stats.get("points_count", 0),
                    vectors_count=stats.get("vectors_count", 0),
                    status=stats.get("status", "unknown"),
                )
            )

        client.close()
        return result

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to list collections: {str(e)}"
        )


@router.get("/{collection_name}/stats", response_model=CollectionStats)
async def get_collection_statistics(collection_name: str):
    """Get detailed statistics for a specific collection."""
    try:
        client = QdrantClient(url=settings.QDRANT_URL)

        # Check if collection exists
        try:
            info = client.get_collection(collection_name)
        except Exception:
            raise HTTPException(
                status_code=404, detail=f"Collection '{collection_name}' not found"
            )

        # Get stats
        stats = get_collection_stats(client, collection_name)

        result = CollectionStats(
            name=collection_name,
            points_count=stats.get("points_count", 0),
            vectors_count=stats.get("vectors_count", 0),
            status=stats.get("status", "unknown"),
            config={
                "vector_size": info.config.params.vectors.size
                if hasattr(info.config.params, "vectors")
                else 0,
                "distance": str(info.config.params.vectors.distance)
                if hasattr(info.config.params, "vectors")
                else "unknown",
            },
        )

        client.close()
        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get collection stats: {str(e)}"
        )


@router.post("/", response_model=CollectionResponse)
async def create_collection(
    collection_data: CollectionCreate, background_tasks: BackgroundTasks
):
    """Create a new collection."""
    try:
        client = QdrantClient(url=settings.QDRANT_URL)

        # Check if collection already exists
        try:
            client.get_collection(collection_data.name)
            raise HTTPException(
                status_code=409,
                detail=f"Collection '{collection_data.name}' already exists",
            )
        except Exception:
            pass  # Collection doesn't exist, which is good

        # Create collection
        from qdrant_client.models import Distance, VectorParams

        distance_map = {
            "cosine": Distance.COSINE,
            "euclidean": Distance.EUCLID,
            "dot": Distance.DOT,
        }

        client.create_collection(
            collection_name=collection_data.name,
            vectors_config=VectorParams(
                size=collection_data.vector_size,
                distance=distance_map.get(
                    collection_data.distance_metric, Distance.COSINE
                ),
            ),
        )

        # Get stats for the new collection
        stats = get_collection_stats(client, collection_data.name)

        result = CollectionResponse(
            name=collection_data.name,
            points_count=stats.get("points_count", 0),
            vectors_count=stats.get("vectors_count", 0),
            status=stats.get("status", "green"),
        )

        client.close()
        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to create collection: {str(e)}"
        )


@router.delete("/{collection_name}")
async def delete_collection(collection_name: str):
    """Delete a collection."""
    try:
        client = QdrantClient(url=settings.QDRANT_URL)

        # Check if collection exists
        try:
            client.get_collection(collection_name)
        except Exception:
            raise HTTPException(
                status_code=404, detail=f"Collection '{collection_name}' not found"
            )

        # Delete collection
        client.delete_collection(collection_name)

        client.close()
        return {"message": f"Collection '{collection_name}' deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to delete collection: {str(e)}"
        )
