"""
Collections management endpoints
"""

from app.core.config import settings
from app.core.database import get_db
from app.models.collection import Collection as CollectionModel
from lib.embedding.client import OllamaEmbeddingClient
from qdrant_client import QdrantClient
from lib.embedding.models import get_model_registry
from lib.qdrant.search import get_collection_stats

import os
import sys
import traceback
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

# Add the project root to Python path to access the shared lib
project_root = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../../../../..")
)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

router = APIRouter()


class CollectionResponse(BaseModel):
    """Collection information response model."""

    name: str
    points_count: int
    vectors_count: int
    status: str
    # New fields for embedding model support
    embedding_model: Optional[str] = None
    vector_size: Optional[int] = None
    distance_metric: Optional[str] = None
    created_at: Optional[str] = None
    description: Optional[str] = None


class CollectionCreate(BaseModel):
    """Collection creation request model."""

    name: str
    embedding_model: str = Field(
        ..., description="Embedding model to use for this collection"
    )
    vector_size: Optional[int] = Field(
        None, description="Vector size (auto-detected if not provided)"
    )
    distance_metric: str = Field("cosine", description="Distance metric for similarity")
    description: Optional[str] = Field(
        None, description="Optional collection description"
    )
    tags: Optional[str] = Field(None, description="Optional tags (JSON string)")


class CollectionStats(BaseModel):
    """Detailed collection statistics."""

    name: str
    points_count: int
    vectors_count: int
    status: str
    config: dict
    # Enhanced fields
    embedding_model: Optional[str] = None
    vector_size: Optional[int] = None
    distance_metric: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    description: Optional[str] = None
    last_stats_update: Optional[str] = None


class EmbeddingModelResponse(BaseModel):
    """Embedding model information response."""

    name: str
    display_name: str
    description: Optional[str] = None
    vector_size: int
    provider: Optional[str] = None
    is_available: str = "unknown"
    recommended: bool = False


@router.get("/", response_model=List[CollectionResponse])
async def list_collections(db: Session = Depends(get_db)):
    """List all collections in Qdrant with enhanced metadata."""
    try:
        client = QdrantClient(url=settings.QDRANT_URL)
        qdrant_collections = client.get_collections()

        result = []
        for qdrant_collection in qdrant_collections.collections:
            # Get Qdrant stats
            stats = get_collection_stats(client, qdrant_collection.name)

            # Get enhanced metadata from database
            collection_meta = (
                db.query(CollectionModel)
                .filter(CollectionModel.name == qdrant_collection.name)
                .first()
            )

            print("qdrant collectionn name:", qdrant_collection.name)
            print("Collection meta:", collection_meta)

            # Build response with both Qdrant and database info
            collection_data = {
                "name": qdrant_collection.name,
                "points_count": stats.get("points_count", 0),
                "vectors_count": stats.get("vectors_count", 0),
                "status": stats.get("status", "unknown"),
            }

            if collection_meta:
                collection_data.update(
                    {
                        "embedding_model": collection_meta.embedding_model,
                        "vector_size": collection_meta.vector_size,
                        "distance_metric": collection_meta.distance_metric,
                        "created_at": collection_meta.created_at.isoformat()
                        if collection_meta.created_at
                        else None,
                        "description": collection_meta.description,
                    }
                )

                # Update cached stats in database
                collection_meta.points_count = stats.get("points_count", 0)
                collection_meta.vectors_count = stats.get("vectors_count", 0)
                collection_meta.status = stats.get("status", "unknown")
                collection_meta.last_stats_update = datetime.utcnow()
            else:
                # Collection exists in Qdrant but not in our database
                # This could be a legacy collection or created outside our API
                collection_data.update(
                    {
                        "embedding_model": None,
                        "vector_size": None,
                        "distance_metric": None,
                        "created_at": None,
                        "description": "Legacy collection (created outside web UI)",
                    }
                )

            result.append(CollectionResponse(**collection_data))

        db.commit()  # Save any stats updates
        client.close()
        return result

    except Exception as e:
        traceback.print_exception(type(e), e, e.__traceback__)
        raise HTTPException(
            status_code=500, detail=f"Failed to list collections: {str(e)}"
        )


@router.get("/{collection_name}/stats", response_model=CollectionStats)
async def get_collection_statistics(
    collection_name: str, db: Session = Depends(get_db)
):
    """Get detailed statistics for a specific collection."""
    try:
        client = QdrantClient(url=settings.QDRANT_URL)

        # Check if collection exists in Qdrant
        try:
            info = client.get_collection(collection_name)
        except Exception:
            raise HTTPException(
                status_code=404, detail=f"Collection '{collection_name}' not found"
            )

        # Get Qdrant stats
        stats = get_collection_stats(client, collection_name)

        # Get enhanced metadata from database
        collection_meta = (
            db.query(CollectionModel)
            .filter(CollectionModel.name == collection_name)
            .first()
        )

        # Build enhanced response
        result_data = {
            "name": collection_name,
            "points_count": stats.get("points_count", 0),
            "vectors_count": stats.get("vectors_count", 0),
            "status": stats.get("status", "unknown"),
            "config": {
                "vector_size": info.config.params.vectors.size
                if hasattr(info.config.params, "vectors")
                else 0,
                "distance": str(info.config.params.vectors.distance)
                if hasattr(info.config.params, "vectors")
                else "unknown",
            },
        }

        if collection_meta:
            result_data.update(
                {
                    "embedding_model": collection_meta.embedding_model,
                    "vector_size": collection_meta.vector_size,
                    "distance_metric": collection_meta.distance_metric,
                    "created_at": collection_meta.created_at.isoformat()
                    if collection_meta.created_at
                    else None,
                    "updated_at": collection_meta.updated_at.isoformat()
                    if collection_meta.updated_at
                    else None,
                    "description": collection_meta.description,
                    "last_stats_update": collection_meta.last_stats_update.isoformat()
                    if collection_meta.last_stats_update
                    else None,
                }
            )

            # Update cached stats
            collection_meta.points_count = stats.get("points_count", 0)
            collection_meta.vectors_count = stats.get("vectors_count", 0)
            collection_meta.status = stats.get("status", "unknown")
            collection_meta.last_stats_update = datetime.utcnow()
            db.commit()

        result = CollectionStats(**result_data)
        client.close()
        return result

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exception(type(e), e, e.__traceback__)
        raise HTTPException(
            status_code=500, detail=f"Failed to get collection stats: {str(e)}"
        )


@router.post("/", response_model=CollectionResponse)
async def create_collection(
    collection_data: CollectionCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Create a new collection with embedding model support."""
    try:
        client = QdrantClient(url=settings.QDRANT_URL)
        embedding_registry = get_model_registry(settings.OLLAMA_URL)

        # Check if collection already exists in Qdrant
        try:
            client.get_collection(collection_data.name)
            raise HTTPException(
                status_code=409,
                detail=f"Collection '{collection_data.name}' already exists",
            )
        except Exception:
            pass  # Collection doesn't exist, which is good

        # Check if collection already exists in database
        existing_meta = (
            db.query(CollectionModel)
            .filter(CollectionModel.name == collection_data.name)
            .first()
        )
        if existing_meta:
            raise HTTPException(
                status_code=409,
                detail=f"Collection metadata for '{collection_data.name}' already exists",
            )

        # Validate embedding model and get vector size
        model_validation = embedding_registry.validate_model(
            collection_data.embedding_model
        )
        if not model_validation["is_valid"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid embedding model '{collection_data.embedding_model}': {model_validation.get('error', 'Unknown error')}",
            )

        # Use provided vector size or auto-detected size
        vector_size = collection_data.vector_size or model_validation["vector_size"]
        if not vector_size:
            raise HTTPException(
                status_code=400,
                detail=f"Could not determine vector size for model '{collection_data.embedding_model}'",
            )

        # Create collection in Qdrant
        from qdrant_client.models import Distance, VectorParams

        distance_map = {
            "cosine": Distance.COSINE,
            "euclidean": Distance.EUCLID,
            "dot": Distance.DOT,
        }

        client.create_collection(
            collection_name=collection_data.name,
            vectors_config=VectorParams(
                size=vector_size,
                distance=distance_map.get(
                    collection_data.distance_metric, Distance.COSINE
                ),
            ),
        )

        # Store collection metadata in database
        collection_meta = CollectionModel(
            name=collection_data.name,
            embedding_model=collection_data.embedding_model,
            vector_size=vector_size,
            distance_metric=collection_data.distance_metric,
            description=collection_data.description,
            tags=collection_data.tags,
            status="green",
            points_count=0,
            vectors_count=0,
        )

        db.add(collection_meta)
        db.commit()

        # Get fresh stats for the new collection
        stats = get_collection_stats(client, collection_data.name)

        result = CollectionResponse(
            name=collection_data.name,
            points_count=stats.get("points_count", 0),
            vectors_count=stats.get("vectors_count", 0),
            status=stats.get("status", "green"),
            embedding_model=collection_data.embedding_model,
            vector_size=vector_size,
            distance_metric=collection_data.distance_metric,
            created_at=collection_meta.created_at.isoformat()
            if collection_meta.created_at
            else None,
            description=collection_data.description,
        )

        client.close()
        return result

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exception(type(e), e, e.__traceback__)
        raise HTTPException(
            status_code=500, detail=f"Failed to create collection: {str(e)}"
        )


@router.delete("/{collection_name}")
async def delete_collection(collection_name: str, db: Session = Depends(get_db)):
    """Delete a collection from both Qdrant and database."""
    try:
        client = QdrantClient(url=settings.QDRANT_URL)

        # Check if collection exists in Qdrant
        collection_exists = False
        try:
            client.get_collection(collection_name)
            collection_exists = True
        except Exception:
            pass  # Collection might not exist in Qdrant but could exist in DB

        # Check if collection metadata exists in database
        collection_meta = (
            db.query(CollectionModel)
            .filter(CollectionModel.name == collection_name)
            .first()
        )

        if not collection_exists and not collection_meta:
            raise HTTPException(
                status_code=404, detail=f"Collection '{collection_name}' not found"
            )

        # Delete from Qdrant if it exists
        if collection_exists:
            client.delete_collection(collection_name)

        # Delete metadata from database if it exists
        if collection_meta:
            db.delete(collection_meta)
            db.commit()

        client.close()
        return {"message": f"Collection '{collection_name}' deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exception(type(e), e, e.__traceback__)
        raise HTTPException(
            status_code=500, detail=f"Failed to delete collection: {str(e)}"
        )


@router.get("/models/available", response_model=List[EmbeddingModelResponse])
async def list_available_embedding_models():
    """List all available embedding models."""
    try:
        registry = get_model_registry(settings.OLLAMA_URL)
        models = registry.list_available_models()

        result = []
        for model in models:
            # Check availability for each model
            is_available, status = registry.check_model_availability(model["name"])

            result.append(
                EmbeddingModelResponse(
                    name=model["name"],
                    display_name=model.get("display_name", model["name"]),
                    description=model.get("description"),
                    vector_size=model["vector_size"],
                    provider=model.get("provider"),
                    is_available="yes" if is_available else "no",
                    recommended=model["name"]
                    in [
                        "embeddinggemma:latest",
                        "bge-m3:567m",
                        "all-minilm-l6-v2",
                        "bge-large:latest",
                    ],
                )
            )

        return result

    except Exception as e:
        traceback.print_exception(type(e), e, e.__traceback__)
        raise HTTPException(
            status_code=500, detail=f"Failed to list embedding models: {str(e)}"
        )


@router.get("/models/recommended", response_model=List[EmbeddingModelResponse])
async def list_recommended_embedding_models():
    """List recommended embedding models for common use cases."""
    try:
        registry = get_model_registry(settings.OLLAMA_URL)
        models = registry.get_recommended_models()

        result = []
        for model in models:
            # Check availability for each model
            is_available, status = registry.check_model_availability(model["name"])

            result.append(
                EmbeddingModelResponse(
                    name=model["name"],
                    display_name=model.get("display_name", model["name"]),
                    description=model.get("description"),
                    vector_size=model["vector_size"],
                    provider=model.get("provider"),
                    is_available="yes" if is_available else "no",
                    recommended=True,
                )
            )

        return result

    except Exception as e:
        traceback.print_exception(type(e), e, e.__traceback__)
        raise HTTPException(
            status_code=500, detail=f"Failed to list recommended models: {str(e)}"
        )


@router.post("/models/{model_name}/validate")
async def validate_embedding_model(model_name: str):
    """Validate an embedding model and return its specifications."""
    try:
        registry = get_model_registry(settings.OLLAMA_URL)
        validation_result = registry.validate_model(model_name)

        return {
            "model_name": model_name,
            "is_valid": validation_result["is_valid"],
            "vector_size": validation_result.get("vector_size"),
            "availability_status": validation_result.get("availability_status"),
            "error": validation_result.get("error"),
            "model_info": validation_result.get("model_info"),
        }

    except Exception as e:
        traceback.print_exception(type(e), e, e.__traceback__)
        raise HTTPException(
            status_code=500, detail=f"Failed to validate model: {str(e)}"
        )


# Collection Records Models
class CollectionRecord(BaseModel):
    """Collection record response model."""

    id: str
    title: str
    content: str
    metadata: Optional[dict] = None
    created_at: Optional[str] = None


class CollectionRecordCreate(BaseModel):
    """Collection record creation model."""

    title: str
    content: str
    metadata: Optional[dict] = None


class CollectionRecordsResponse(BaseModel):
    """Paginated collection records response."""

    records: List[CollectionRecord]
    total: int
    page: int
    page_size: int
    total_pages: int


class BulkRecordCreate(BaseModel):
    """Bulk record creation model."""

    records: List[CollectionRecordCreate]


# Collection Records Endpoints
@router.get("/{collection_name}/records", response_model=CollectionRecordsResponse)
async def get_collection_records(
    collection_name: str,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
):
    """Get paginated records from a collection."""
    try:
        client = QdrantClient(url=settings.QDRANT_URL)

        # Check if collection exists
        try:
            client.get_collection(collection_name)
        except Exception:
            raise HTTPException(
                status_code=404, detail=f"Collection '{collection_name}' not found"
            )

        # Calculate offset
        offset = (page - 1) * page_size

        # Get records from Qdrant
        search_result = client.scroll(
            collection_name=collection_name,
            limit=page_size,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )

        records = []
        for point in search_result[0]:  # search_result is (points, next_page_offset)
            payload = point.payload or {}
            records.append(
                CollectionRecord(
                    id=str(point.id),
                    title=payload.get("title", ""),
                    content=payload.get("content", ""),
                    metadata=payload.get("metadata", {}),
                    created_at=payload.get("created_at"),
                )
            )

        # Get total count
        collection_info = client.get_collection(collection_name)
        total_records = collection_info.points_count
        total_pages = (total_records + page_size - 1) // page_size

        client.close()

        return CollectionRecordsResponse(
            records=records,
            total=total_records,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exception(type(e), e, e.__traceback__)
        raise HTTPException(
            status_code=500, detail=f"Failed to get collection records: {str(e)}"
        )


@router.post("/{collection_name}/records")
async def add_records(
    collection_name: str, records_data: BulkRecordCreate, db: Session = Depends(get_db)
):
    """Add records to a collection."""
    try:
        client = QdrantClient(url=settings.QDRANT_URL)
        embedding_client = OllamaEmbeddingClient(
            ollama_url=settings.OLLAMA_URL, timeout=120
        )
        embedding_registry = get_model_registry(settings.OLLAMA_URL)

        # Check if collection exists and get metadata
        try:
            client.get_collection(collection_name)
        except Exception:
            raise HTTPException(
                status_code=404, detail=f"Collection '{collection_name}' not found"
            )

        # Get collection metadata from database
        collection_meta = (
            db.query(CollectionModel)
            .filter(CollectionModel.name == collection_name)
            .first()
        )

        if not collection_meta or not collection_meta.embedding_model:
            raise HTTPException(
                status_code=400,
                detail=f"Collection '{collection_name}' has no embedding model configured",
            )

        # Process records
        points_to_upsert = []

        for record in records_data.records:
            # Generate embedding for content
            embedding = embedding_client.embed_text(
                record.content, collection_meta.embedding_model
            )

            if not embedding:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to generate embedding for record: {record.title}",
                )

            # Create point
            point_id = str(uuid4())
            payload = {
                "title": record.title,
                "content": record.content,
                "metadata": record.metadata or {},
                "created_at": datetime.utcnow().isoformat(),
            }

            from qdrant_client.models import PointStruct

            points_to_upsert.append(
                PointStruct(id=point_id, vector=embedding, payload=payload)
            )

        # Upsert points to Qdrant
        client.upsert(collection_name=collection_name, points=points_to_upsert)

        client.close()

        return {
            "message": f"Successfully added {len(records_data.records)} records to collection '{collection_name}'",
            "records_count": len(records_data.records),
        }

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exception(type(e), e, e.__traceback__)
        raise HTTPException(status_code=500, detail=f"Failed to add records: {str(e)}")


@router.get("/{collection_name}/records/{record_id}", response_model=CollectionRecord)
async def get_collection_record(
    collection_name: str, record_id: str, db: Session = Depends(get_db)
):
    """Get a specific record from a collection."""
    try:
        client = QdrantClient(url=settings.QDRANT_URL)

        # Check if collection exists
        try:
            client.get_collection(collection_name)
        except Exception:
            raise HTTPException(
                status_code=404, detail=f"Collection '{collection_name}' not found"
            )

        # Retrieve the record
        try:
            try:
                a_record_id = int(record_id)
            except ValueError:
                a_record_id = record_id

            records = client.retrieve(
                collection_name=collection_name, ids=[a_record_id], with_payload=True
            )
            if not records:
                raise HTTPException(
                    status_code=404,
                    detail=f"Record '{record_id}' not found in collection '{collection_name}'",
                )

            record = records[0]
            payload = record.payload or {}

            return CollectionRecord(
                id=str(record.id),
                title=payload.get("title", ""),
                content=payload.get("content", ""),
                metadata=payload.get("metadata", {}),
                created_at=payload.get("created_at"),
            )

        except Exception as e:
            if "404" in str(e):
                raise HTTPException(
                    status_code=404,
                    detail=f"Record '{record_id}' not found in collection '{collection_name}'",
                )
            raise

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exception(type(e), e, e.__traceback__)
        raise HTTPException(status_code=500, detail=f"Failed to get record: {str(e)}")


@router.delete("/{collection_name}/records/{record_id}")
async def delete_record(
    collection_name: str, record_id: str, db: Session = Depends(get_db)
):
    """Delete a specific record from a collection."""
    try:
        client = QdrantClient(url=settings.QDRANT_URL)

        # Check if collection exists
        try:
            client.get_collection(collection_name)
        except Exception:
            raise HTTPException(
                status_code=404, detail=f"Collection '{collection_name}' not found"
            )

        # Check if record exists
        try:
            record = client.retrieve(
                collection_name=collection_name, ids=[record_id], with_payload=True
            )
            if not record:
                raise HTTPException(
                    status_code=404,
                    detail=f"Record '{record_id}' not found in collection '{collection_name}'",
                )
        except Exception as e:
            if "404" in str(e):
                raise HTTPException(
                    status_code=404,
                    detail=f"Record '{record_id}' not found in collection '{collection_name}'",
                )
            raise

        # Delete the record
        client.delete(collection_name=collection_name, points_selector=[record_id])

        client.close()

        return {
            "message": f"Record '{record_id}' deleted successfully from collection '{collection_name}'"
        }

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exception(type(e), e, e.__traceback__)
        raise HTTPException(
            status_code=500, detail=f"Failed to delete record: {str(e)}"
        )
