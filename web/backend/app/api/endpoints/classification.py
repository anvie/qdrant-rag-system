"""
API endpoints for text classification.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field
import logging

from core.database import get_db
from services.classification_service import classification_service

logger = logging.getLogger(__name__)

router = APIRouter()


# Pydantic models
class CategoryCreate(BaseModel):
    """Request model for creating a category."""
    name: str = Field(..., min_length=1, max_length=255)
    sample_texts: List[str] = Field(..., min_items=1)
    model: Optional[str] = None


class CategoryUpdate(BaseModel):
    """Request model for updating a category."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    sample_texts: Optional[List[str]] = Field(None, min_items=1)
    model: Optional[str] = None


class CategoryResponse(BaseModel):
    """Response model for category data."""
    id: int
    name: str
    sample_texts: List[str]
    model_name: Optional[str]
    sample_count: int
    created_at: str
    updated_at: Optional[str]

    class Config:
        from_attributes = True


class ClassificationRequest(BaseModel):
    """Request model for text classification."""
    text: str = Field(..., min_length=1)
    model: Optional[str] = None
    top_k: int = Field(default=5, ge=1, le=10)


class ClassificationResult(BaseModel):
    """Individual classification result."""
    category_id: int
    category_name: str
    confidence: float
    sample_count: int


class ClassificationResponse(BaseModel):
    """Response model for classification results."""
    text: str
    model: str
    results: List[ClassificationResult]


class ModelInfo(BaseModel):
    """Model information."""
    name: str
    size: Optional[int] = None
    modified: Optional[str] = None


@router.post("/categories", response_model=CategoryResponse)
async def create_category(
    category_data: CategoryCreate,
    db: Session = Depends(get_db)
):
    """Create a new classification category."""
    try:
        category = await classification_service.create_category(
            db=db,
            name=category_data.name,
            sample_texts=category_data.sample_texts,
            model=category_data.model
        )

        return CategoryResponse(
            id=category.id,
            name=category.name,
            sample_texts=category.sample_texts,
            model_name=category.model_name,
            sample_count=len(category.sample_texts) if category.sample_texts else 0,
            created_at=category.created_at.isoformat() if category.created_at else "",
            updated_at=category.updated_at.isoformat() if category.updated_at else None
        )
    except Exception as e:
        logger.error(f"Error creating category: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create category: {str(e)}"
        )


@router.get("/categories", response_model=List[CategoryResponse])
async def get_categories(db: Session = Depends(get_db)):
    """Get all classification categories."""
    try:
        categories = await classification_service.get_categories(db)

        return [
            CategoryResponse(
                id=category.id,
                name=category.name,
                sample_texts=category.sample_texts or [],
                model_name=category.model_name,
                sample_count=len(category.sample_texts) if category.sample_texts else 0,
                created_at=category.created_at.isoformat() if category.created_at else "",
                updated_at=category.updated_at.isoformat() if category.updated_at else None
            )
            for category in categories
        ]
    except Exception as e:
        logger.error(f"Error getting categories: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get categories: {str(e)}"
        )


@router.put("/categories/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: int,
    category_data: CategoryUpdate,
    db: Session = Depends(get_db)
):
    """Update an existing classification category."""
    try:
        category = await classification_service.update_category(
            db=db,
            category_id=category_id,
            name=category_data.name,
            sample_texts=category_data.sample_texts,
            model=category_data.model
        )

        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found"
            )

        return CategoryResponse(
            id=category.id,
            name=category.name,
            sample_texts=category.sample_texts or [],
            model_name=category.model_name,
            sample_count=len(category.sample_texts) if category.sample_texts else 0,
            created_at=category.created_at.isoformat() if category.created_at else "",
            updated_at=category.updated_at.isoformat() if category.updated_at else None
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating category: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update category: {str(e)}"
        )


@router.delete("/categories/{category_id}")
async def delete_category(
    category_id: int,
    db: Session = Depends(get_db)
):
    """Delete a classification category."""
    try:
        success = await classification_service.delete_category(db, category_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found"
            )

        return {"message": "Category deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting category: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete category: {str(e)}"
        )


@router.post("/classify", response_model=ClassificationResponse)
async def classify_text(
    request: ClassificationRequest,
    db: Session = Depends(get_db)
):
    """Classify input text and return top matching categories."""
    try:
        results = await classification_service.classify_text(
            db=db,
            text=request.text,
            model=request.model,
            top_k=request.top_k
        )

        model_name = request.model or classification_service.default_model

        return ClassificationResponse(
            text=request.text,
            model=model_name,
            results=[
                ClassificationResult(
                    category_id=result["category_id"],
                    category_name=result["category_name"],
                    confidence=result["confidence"],
                    sample_count=result["sample_count"]
                )
                for result in results
            ]
        )
    except Exception as e:
        logger.error(f"Error classifying text: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to classify text: {str(e)}"
        )


@router.get("/models", response_model=List[ModelInfo])
async def get_available_models():
    """Get available embedding models from Ollama."""
    try:
        models = await classification_service.get_available_models()
        return [
            ModelInfo(
                name=model["name"],
                size=model.get("size"),
                modified=model.get("modified")
            )
            for model in models
        ]
    except Exception as e:
        logger.error(f"Error getting models: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get available models: {str(e)}"
        )