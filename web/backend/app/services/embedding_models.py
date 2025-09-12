"""
Embedding model registry and management service.
Provides model-to-vector-size mappings and auto-detection capabilities.

This module now uses the shared library for model management.
"""

import sys
import os
import logging
from typing import Dict, List, Optional

# Add the project root to Python path to access the shared lib
project_root = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../../../../..")
)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.core.config import settings
from app.core.database import get_db_session
from app.models.collection import EmbeddingModel

# Import from shared library
from lib.embedding.models import (
    EmbeddingModelRegistry,
    get_model_registry,
    EMBEDDING_MODELS,
    get_model_info,
    get_vector_size,
    list_available_models,
)

logger = logging.getLogger(__name__)


# Wrapper functions for web backend compatibility
def get_embedding_registry(ollama_url: str = None) -> EmbeddingModelRegistry:
    """Get the embedding model registry instance."""
    return get_model_registry(ollama_url or settings.OLLAMA_URL)


def init_embedding_models() -> bool:
    """
    Initialize embedding models and verify Ollama connection.

    Returns:
        True if initialization successful, False otherwise
    """
    try:
        registry = get_embedding_registry()

        # Test connection to Ollama
        available_models = registry.get_ollama_models(timeout=5)

        if not available_models:
            logger.warning(
                "⚠️  No models available from Ollama - verify Ollama is running"
            )
            return False

        logger.info(f"✅ Found {len(available_models)} models available in Ollama")

        # Log some basic model info
        for model in available_models[:3]:  # Show first 3 models
            name = model.get("name", "unknown")
            size = model.get("size", "unknown")
            logger.info(f"  📦 {name} ({size})")

        return True

    except Exception as e:
        logger.error(f"❌ Failed to initialize embedding models: {e}")
        return False


def sync_models_to_database(db_session=None) -> None:
    """
    Sync embedding models from registry to database.

    Args:
        db_session: Optional database session
    """
    if not db_session:
        db_session = get_db_session()

    try:
        registry = get_embedding_registry()

        # Get models from shared registry
        available_models = registry.list_available_models()

        for model_data in available_models:
            name = model_data["name"]

            # Check if model exists in database
            existing = db_session.query(EmbeddingModel).filter_by(name=name).first()

            if not existing:
                # Create new model record
                new_model = EmbeddingModel(
                    name=name,
                    display_name=model_data.get("display_name", name),
                    description=model_data.get("description", ""),
                    vector_size=model_data.get("vector_size"),
                    provider=model_data.get("provider", "ollama"),
                    model_type=model_data.get("model_type", "transformer"),
                    max_sequence_length=model_data.get("max_sequence_length"),
                    supports_multilingual=model_data.get(
                        "supports_multilingual", "unknown"
                    ),
                    processing_speed=model_data.get("processing_speed"),
                    memory_usage=model_data.get("memory_usage"),
                    is_available=True,
                )
                db_session.add(new_model)
            else:
                # Update existing model
                existing.display_name = model_data.get("display_name", name)
                existing.description = model_data.get(
                    "description", existing.description
                )
                existing.vector_size = model_data.get(
                    "vector_size", existing.vector_size
                )
                existing.is_available = True

        db_session.commit()
        logger.info(f"✅ Synced {len(available_models)} models to database")

    except Exception as e:
        logger.error(f"❌ Failed to sync models to database: {e}")
        if db_session:
            db_session.rollback()


# Export the legacy functions for backward compatibility
__all__ = [
    "get_embedding_registry",
    "init_embedding_models",
    "sync_models_to_database",
    "EMBEDDING_MODELS",
    "EmbeddingModelRegistry",
]
