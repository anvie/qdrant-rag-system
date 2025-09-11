"""
Embedding model registry and management service.
Provides model-to-vector-size mappings and auto-detection capabilities.
"""

import requests
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import json

from app.core.config import settings
from app.core.database import get_db_session
from app.models.collection import EmbeddingModel

logger = logging.getLogger(__name__)

# Predefined embedding models with their specifications
EMBEDDING_MODELS = {
    # Ollama models
    "embeddinggemma:latest": {
        "display_name": "Embedding Gemma (Latest)",
        "description": "Google Gemma embedding model - fast and efficient for general use",
        "vector_size": 768,
        "provider": "ollama",
        "model_type": "transformer",
        "max_sequence_length": 8192,
        "supports_multilingual": "limited",
        "processing_speed": 1000.0,  # tokens/second estimate
        "memory_usage": 512,  # MB estimate
    },
    "bge-m3:567m": {
        "display_name": "BGE-M3 (567M params)",
        "description": "Multilingual embedding model optimized for retrieval tasks",
        "vector_size": 1024,
        "provider": "ollama",
        "model_type": "transformer",
        "max_sequence_length": 8192,
        "supports_multilingual": "yes",
        "processing_speed": 800.0,
        "memory_usage": 1200,
    },
    "bge-large:latest": {
        "display_name": "BGE Large (Latest)",
        "description": "Large BGE model for high-quality embeddings",
        "vector_size": 1024,
        "provider": "ollama",
        "model_type": "transformer",
        "max_sequence_length": 512,
        "supports_multilingual": "limited",
        "processing_speed": 600.0,
        "memory_usage": 2048,
    },
    "bge-base:latest": {
        "display_name": "BGE Base (Latest)",
        "description": "Base BGE model balancing quality and speed",
        "vector_size": 768,
        "provider": "ollama",
        "model_type": "transformer",
        "max_sequence_length": 512,
        "supports_multilingual": "limited",
        "processing_speed": 1200.0,
        "memory_usage": 800,
    },
    "all-minilm-l6-v2": {
        "display_name": "All-MiniLM-L6-v2",
        "description": "Compact sentence transformer model - very fast",
        "vector_size": 384,
        "provider": "ollama",
        "model_type": "sentence-transformer",
        "max_sequence_length": 256,
        "supports_multilingual": "limited",
        "processing_speed": 2000.0,
        "memory_usage": 256,
    },
    "all-mpnet-base-v2": {
        "display_name": "All-MPNet-Base-v2",
        "description": "High-quality sentence transformer based on MPNet",
        "vector_size": 768,
        "provider": "ollama",
        "model_type": "sentence-transformer",
        "max_sequence_length": 384,
        "supports_multilingual": "limited",
        "processing_speed": 1000.0,
        "memory_usage": 400,
    },
    # Sentence Transformers (if using directly)
    "sentence-transformers/all-MiniLM-L6-v2": {
        "display_name": "Sentence-T All-MiniLM-L6-v2",
        "description": "Direct sentence transformer - compact and fast",
        "vector_size": 384,
        "provider": "huggingface",
        "model_type": "sentence-transformer",
        "max_sequence_length": 256,
        "supports_multilingual": "limited",
        "processing_speed": 1500.0,
        "memory_usage": 256,
    },
    "sentence-transformers/all-mpnet-base-v2": {
        "display_name": "Sentence-T All-MPNet-Base-v2",
        "description": "Direct sentence transformer - high quality",
        "vector_size": 768,
        "provider": "huggingface",
        "model_type": "sentence-transformer",
        "max_sequence_length": 384,
        "supports_multilingual": "limited",
        "processing_speed": 800.0,
        "memory_usage": 400,
    },
}


class EmbeddingModelRegistry:
    """Registry for managing embedding models and their specifications."""

    def __init__(self, ollama_url: str = None):
        self.ollama_url = ollama_url or settings.OLLAMA_URL
        self._cache = {}  # Cache for model availability

    def get_model_info(self, model_name: str) -> Optional[Dict]:
        """Get model information from registry."""
        return EMBEDDING_MODELS.get(model_name)

    def get_vector_size(self, model_name: str) -> Optional[int]:
        """Get vector size for a model."""
        model_info = self.get_model_info(model_name)
        return model_info.get("vector_size") if model_info else None

    def list_available_models(self) -> List[Dict]:
        """List all available embedding models."""
        models = []
        for name, info in EMBEDDING_MODELS.items():
            model_data = {"name": name, **info}
            models.append(model_data)
        return models

    def detect_vector_size_from_ollama(self, model_name: str) -> Optional[int]:
        """
        Auto-detect vector size by querying Ollama with test text.
        This is used as fallback when model is not in our registry.
        """
        try:
            # Import the embedding function
            import sys
            import os

            sys.path.append(os.path.join(os.path.dirname(__file__), "../../../../.."))
            from query_qdrant import embed_one_ollama, create_session

            # Test with simple text
            test_text = "test"
            session = create_session()

            logger.info(f"Auto-detecting vector size for model: {model_name}")
            embedding = embed_one_ollama(
                text=test_text,
                model=model_name,
                url=self.ollama_url,
                timeout=30,
                session=session,
            )

            if embedding and isinstance(embedding, list):
                vector_size = len(embedding)
                logger.info(
                    f"Detected vector size {vector_size} for model {model_name}"
                )
                return vector_size

            logger.warning(f"Could not detect vector size for model {model_name}")
            return None

        except Exception as e:
            logger.error(f"Failed to auto-detect vector size for {model_name}: {e}")
            return None

    def check_model_availability(self, model_name: str) -> Tuple[bool, str]:
        """
        Check if a model is available in Ollama.
        Returns (is_available, status_message)
        """
        try:
            # Check cache first
            cache_key = f"availability_{model_name}"
            if cache_key in self._cache:
                cached_time, cached_result = self._cache[cache_key]
                # Use cache for 5 minutes
                if (datetime.now() - cached_time).seconds < 300:
                    return cached_result

            # Query Ollama API for available models
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=10)
            response.raise_for_status()

            available_models = response.json().get("models", [])
            model_names = [
                model.get("name", "").split(":")[0] for model in available_models
            ]

            # Check if our model is available (with or without tag)
            model_base_name = model_name.split(":")[0]
            is_available = any(
                model_name in name or model_base_name in name
                for name in [model.get("name", "") for model in available_models]
            )

            status = "available" if is_available else "not_found"
            result = (is_available, status)

            # Cache result
            self._cache[cache_key] = (datetime.now(), result)

            return result

        except requests.RequestException as e:
            logger.error(f"Failed to check model availability for {model_name}: {e}")
            return False, f"connection_error: {e}"
        except Exception as e:
            logger.error(f"Unexpected error checking model {model_name}: {e}")
            return False, f"error: {e}"

    def validate_model(self, model_name: str) -> Dict:
        """
        Validate a model and return comprehensive information.
        """
        result = {
            "name": model_name,
            "is_valid": False,
            "vector_size": None,
            "availability_status": "unknown",
            "error": None,
            "model_info": None,
        }

        try:
            # Get model info from registry
            model_info = self.get_model_info(model_name)
            result["model_info"] = model_info

            # Check availability
            is_available, status = self.check_model_availability(model_name)
            result["availability_status"] = status

            if not is_available:
                result["error"] = f"Model not available in Ollama: {status}"
                return result

            # Get vector size (from registry or auto-detect)
            vector_size = None
            if model_info:
                vector_size = model_info.get("vector_size")

            if not vector_size:
                # Try auto-detection
                vector_size = self.detect_vector_size_from_ollama(model_name)

            if not vector_size:
                result["error"] = "Could not determine vector size"
                return result

            result.update(
                {
                    "is_valid": True,
                    "vector_size": vector_size,
                }
            )

        except Exception as e:
            result["error"] = f"Validation failed: {e}"

        return result

    def sync_to_database(self):
        """Sync predefined models to database."""
        try:
            with get_db_session() as db:
                for name, info in EMBEDDING_MODELS.items():
                    # Check if model already exists
                    existing = (
                        db.query(EmbeddingModel)
                        .filter(EmbeddingModel.name == name)
                        .first()
                    )

                    if existing:
                        # Update existing model
                        for key, value in info.items():
                            if hasattr(existing, key):
                                setattr(existing, key, value)
                        existing.updated_at = datetime.utcnow()
                    else:
                        # Create new model
                        model = EmbeddingModel(
                            name=name,
                            **info,
                            is_available="unknown",
                            is_tested="no",
                        )
                        db.add(model)

                db.commit()
                logger.info(f"Synced {len(EMBEDDING_MODELS)} models to database")

        except Exception as e:
            logger.error(f"Failed to sync models to database: {e}")
            raise

    def get_models_from_database(self) -> List[Dict]:
        """Get all models from database."""
        try:
            with get_db_session() as db:
                models = db.query(EmbeddingModel).all()
                return [model.to_dict() for model in models]
        except Exception as e:
            logger.error(f"Failed to get models from database: {e}")
            return []

    def get_recommended_models(self) -> List[Dict]:
        """Get recommended models based on common use cases."""
        recommended = [
            "embeddinggemma:latest",  # Good default
            "bge-m3:567m",  # Best for multilingual
            "all-minilm-l6-v2",  # Fastest, smallest
            "bge-large:latest",  # Best quality
        ]

        models = []
        for name in recommended:
            info = self.get_model_info(name)
            if info:
                model_data = {"name": name, **info, "recommended": True}
                models.append(model_data)

        return models


# Global registry instance
embedding_registry = EmbeddingModelRegistry()


def get_embedding_registry() -> EmbeddingModelRegistry:
    """Get the global embedding model registry."""
    return embedding_registry


def init_embedding_models():
    """Initialize embedding models in database."""
    try:
        registry = get_embedding_registry()
        registry.sync_to_database()
        logger.info("Embedding models initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize embedding models: {e}")
        return False


if __name__ == "__main__":
    # Test the registry
    registry = EmbeddingModelRegistry()

    print("Available models:")
    for model in registry.list_available_models():
        print(f"  {model['name']}: {model['vector_size']} dimensions")

    print("\nTesting model validation:")
    result = registry.validate_model("embeddinggemma:latest")
    print(f"Validation result: {result}")
