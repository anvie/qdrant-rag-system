"""
Classification service for text categorization using embeddings.
"""

import json
import numpy as np
from typing import List, Dict, Tuple, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import select
import logging
import sys
import os

# Add the project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from lib.embedding.client import OllamaEmbeddingClient
from app.models.classification import Category
from app.core.config import settings

logger = logging.getLogger(__name__)


class ClassificationService:
    """Service for text classification using embeddings."""

    def __init__(self):
        """Initialize the classification service."""
        self.embedding_client = OllamaEmbeddingClient(
            ollama_url=settings.OLLAMA_URL
        )
        self.default_model = settings.EMBEDDING_MODEL

    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        vec1_np = np.array(vec1)
        vec2_np = np.array(vec2)

        dot_product = np.dot(vec1_np, vec2_np)
        norm1 = np.linalg.norm(vec1_np)
        norm2 = np.linalg.norm(vec2_np)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    def format_text_for_model(
        self, text: str, model: str, is_category: bool = False
    ) -> str:
        """
        Format text based on the model requirements.

        Args:
            text: The text to format
            model: The model name
            is_category: Whether this is a category label

        Returns:
            Formatted text string
        """
        # EmbeddingGemma uses special classification format
        if "embeddinggemma" in model.lower():
            return f"task: classification | query: {text}"
        # BGE models and others use plain text
        else:
            return text

    async def create_category(
        self, db: Session, name: str, sample_texts: List[str], model: Optional[str] = None
    ) -> Category:
        """
        Create a new category with sample texts and generate its embedding.

        Args:
            db: Database session
            name: Category name
            sample_texts: List of sample texts for this category
            model: Embedding model to use (optional)

        Returns:
            Created category object
        """
        model = model or self.default_model

        # Generate embeddings for all sample texts
        embeddings = []
        for text in sample_texts:
            formatted_text = self.format_text_for_model(text, model)
            try:
                embedding = self.embedding_client.embed_text(formatted_text, model)
                embeddings.append(embedding)
            except Exception as e:
                logger.error(f"Error generating embedding for text: {e}")
                raise

        # Calculate average embedding for the category
        if embeddings:
            avg_embedding = np.mean(embeddings, axis=0).tolist()
        else:
            avg_embedding = []

        # Create and save category
        category = Category(
            name=name,
            sample_texts=sample_texts,
            embedding=avg_embedding,
            model_name=model
        )

        db.add(category)
        db.commit()
        db.refresh(category)

        logger.info(f"Created category '{name}' with {len(sample_texts)} samples")
        return category

    async def update_category(
        self,
        db: Session,
        category_id: int,
        name: Optional[str] = None,
        sample_texts: Optional[List[str]] = None,
        model: Optional[str] = None
    ) -> Optional[Category]:
        """
        Update an existing category.

        Args:
            db: Database session
            category_id: ID of the category to update
            name: New category name (optional)
            sample_texts: New sample texts (optional)
            model: Embedding model to use (optional)

        Returns:
            Updated category object or None if not found
        """
        category = db.get(Category, category_id)
        if not category:
            return None

        if name:
            category.name = name

        if sample_texts:
            model = model or category.model_name or self.default_model

            # Generate new embeddings
            embeddings = []
            for text in sample_texts:
                formatted_text = self.format_text_for_model(text, model)
                try:
                    embedding = self.embedding_client.embed_text(formatted_text, model)
                    embeddings.append(embedding)
                except Exception as e:
                    logger.error(f"Error generating embedding for text: {e}")
                    raise

            # Calculate average embedding
            if embeddings:
                avg_embedding = np.mean(embeddings, axis=0).tolist()
                category.embedding = avg_embedding
                category.sample_texts = sample_texts
                category.model_name = model

        db.commit()
        db.refresh(category)
        return category

    async def delete_category(self, db: Session, category_id: int) -> bool:
        """
        Delete a category.

        Args:
            db: Database session
            category_id: ID of the category to delete

        Returns:
            True if deleted, False if not found
        """
        category = db.get(Category, category_id)
        if not category:
            return False

        db.delete(category)
        db.commit()
        return True

    async def get_categories(self, db: Session) -> List[Category]:
        """
        Get all categories.

        Args:
            db: Database session

        Returns:
            List of all categories
        """
        stmt = select(Category).order_by(Category.name)
        result = db.execute(stmt)
        return list(result.scalars().all())

    async def classify_text(
        self,
        db: Session,
        text: str,
        model: Optional[str] = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Classify text into categories based on embedding similarity.

        Args:
            db: Database session
            text: Text to classify
            model: Embedding model to use (optional)
            top_k: Number of top results to return

        Returns:
            List of classification results with scores
        """
        model = model or self.default_model

        # Get all categories with embeddings
        stmt = select(Category).where(Category.embedding.is_not(None))
        result = db.execute(stmt)
        categories = list(result.scalars().all())

        if not categories:
            return []

        # Generate embedding for input text
        formatted_text = self.format_text_for_model(text, model)
        try:
            text_embedding = self.embedding_client.embed_text(formatted_text, model)
        except Exception as e:
            logger.error(f"Error generating embedding for input text: {e}")
            raise

        # Calculate similarities with all categories
        similarities = []
        for category in categories:
            # Only use categories with matching model or if model matches default
            if category.model_name != model:
                # Re-generate embedding if model doesn't match
                if category.sample_texts:
                    embeddings = []
                    for sample_text in category.sample_texts:
                        formatted = self.format_text_for_model(sample_text, model)
                        try:
                            embedding = self.embedding_client.embed_text(formatted, model)
                            embeddings.append(embedding)
                        except Exception:
                            continue

                    if embeddings:
                        avg_embedding = np.mean(embeddings, axis=0).tolist()
                        similarity = self.cosine_similarity(text_embedding, avg_embedding)
                    else:
                        similarity = 0.0
                else:
                    similarity = 0.0
            else:
                similarity = self.cosine_similarity(text_embedding, category.embedding)

            similarities.append({
                "category_id": category.id,
                "category_name": category.name,
                "confidence": similarity,
                "sample_count": len(category.sample_texts) if category.sample_texts else 0
            })

        # Sort by confidence and return top k
        similarities.sort(key=lambda x: x["confidence"], reverse=True)
        return similarities[:top_k]

    async def get_available_models(self) -> List[Dict[str, Any]]:
        """
        Get list of available embedding models from Ollama.

        Returns:
            List of model information
        """
        try:
            models = self.embedding_client.get_available_models()
            # Filter to only include embedding models
            embedding_models = []
            for model in models:
                model_name = model.get("name", "")
                # Common embedding model patterns
                if any(pattern in model_name.lower() for pattern in ["embed", "bge", "e5", "gte"]):
                    embedding_models.append({
                        "name": model_name,
                        "size": model.get("size"),
                        "modified": model.get("modified_at")
                    })
            return embedding_models
        except Exception as e:
            logger.error(f"Failed to get available models: {e}")
            return []


# Singleton instance
classification_service = ClassificationService()