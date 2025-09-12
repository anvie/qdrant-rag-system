"""
Embedding model registry and management.

This module provides model specifications, vector size mappings, and model
management functionality for various embedding models.
"""

import logging
from typing import Dict, List, Optional, Any
import requests

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

    def __init__(self, ollama_url: str = "http://localhost:11434"):
        """
        Initialize the model registry.

        Args:
            ollama_url: Base URL for Ollama API
        """
        self.ollama_url = ollama_url.rstrip("/")
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

    def get_models_by_provider(self, provider: str) -> List[Dict]:
        """Get models filtered by provider."""
        models = []
        for name, info in EMBEDDING_MODELS.items():
            if info.get("provider") == provider:
                model_data = {"name": name, **info}
                models.append(model_data)
        return models

    def get_models_by_vector_size(self, vector_size: int) -> List[Dict]:
        """Get models filtered by vector size."""
        models = []
        for name, info in EMBEDDING_MODELS.items():
            if info.get("vector_size") == vector_size:
                model_data = {"name": name, **info}
                models.append(model_data)
        return models

    def detect_vector_size_from_ollama(self, model_name: str) -> Optional[int]:
        """
        Auto-detect vector size by querying Ollama with test text.
        This is used as fallback when model is not in our registry.
        """
        try:
            from ..embedding.client import embed_one_ollama

            # Use a simple test text
            test_text = "test"
            embedding = embed_one_ollama(
                test_text, model_name, self.ollama_url, timeout=30
            )

            if embedding:
                vector_size = len(embedding)
                logger.info(
                    f"Auto-detected vector size for '{model_name}': {vector_size}"
                )

                # Cache the result
                self._cache[model_name] = {"vector_size": vector_size}
                return vector_size

        except Exception as e:
            logger.error(f"Failed to auto-detect vector size for '{model_name}': {e}")

        return None

    def get_or_detect_vector_size(self, model_name: str) -> Optional[int]:
        """
        Get vector size from registry or auto-detect from Ollama.

        Args:
            model_name: Name of the model

        Returns:
            Vector size if found, None otherwise
        """
        # First check our predefined registry
        vector_size = self.get_vector_size(model_name)
        if vector_size:
            return vector_size

        # Check cache
        if model_name in self._cache:
            return self._cache[model_name].get("vector_size")

        # Try to auto-detect
        return self.detect_vector_size_from_ollama(model_name)

    def get_ollama_models(self, timeout: int = 10) -> List[Dict]:
        """
        Get list of available models from Ollama API.

        Args:
            timeout: Request timeout in seconds

        Returns:
            List of model dictionaries
        """
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=timeout)
            response.raise_for_status()

            data = response.json()
            models = data.get("models", [])

            # Enhance with registry information if available
            enhanced_models = []
            for model in models:
                model_name = model.get("name", "")
                registry_info = self.get_model_info(model_name)

                if registry_info:
                    # Merge registry info with Ollama info
                    enhanced_model = {**model, **registry_info}
                else:
                    # Use Ollama info as-is
                    enhanced_model = model

                enhanced_models.append(enhanced_model)

            return enhanced_models

        except Exception as e:
            logger.error(f"Failed to get models from Ollama: {e}")
            return []

    def is_model_available(self, model_name: str, timeout: int = 5) -> bool:
        """
        Check if a model is available in Ollama.

        Args:
            model_name: Name of the model to check
            timeout: Request timeout in seconds

        Returns:
            True if model is available, False otherwise
        """
        try:
            ollama_models = self.get_ollama_models(timeout)
            available_names = [model.get("name", "") for model in ollama_models]
            return model_name in available_names
        except Exception:
            return False

    def recommend_models(
        self,
        use_case: str = "general",
        max_memory_mb: Optional[int] = None,
        min_speed: Optional[float] = None,
        multilingual: bool = False,
    ) -> List[Dict]:
        """
        Recommend models based on requirements.

        Args:
            use_case: Use case ('general', 'fast', 'quality', 'multilingual')
            max_memory_mb: Maximum memory usage in MB
            min_speed: Minimum processing speed in tokens/second
            multilingual: Whether multilingual support is required

        Returns:
            List of recommended models sorted by suitability
        """
        candidates = []

        for name, info in EMBEDDING_MODELS.items():
            # Apply filters
            if max_memory_mb and info.get("memory_usage", 0) > max_memory_mb:
                continue

            if min_speed and info.get("processing_speed", 0) < min_speed:
                continue

            if multilingual and info.get("supports_multilingual") not in [
                "yes",
                "good",
            ]:
                continue

            # Calculate suitability score
            score = 0.0

            if use_case == "fast":
                score = info.get("processing_speed", 0) / 1000.0
            elif use_case == "quality":
                score = info.get("vector_size", 0) / 1000.0
            elif use_case == "multilingual":
                if info.get("supports_multilingual") == "yes":
                    score = 2.0
                elif info.get("supports_multilingual") == "good":
                    score = 1.5
                else:
                    score = 0.5
            else:  # general
                # Balance of speed, quality, and memory efficiency
                speed_score = info.get("processing_speed", 0) / 2000.0
                quality_score = info.get("vector_size", 0) / 1000.0
                memory_score = 1000.0 / max(info.get("memory_usage", 1000), 100)
                score = (speed_score + quality_score + memory_score) / 3.0

            candidates.append({"name": name, **info, "suitability_score": score})

        # Sort by suitability score (descending)
        candidates.sort(key=lambda x: x["suitability_score"], reverse=True)

        return candidates[:5]  # Return top 5 recommendations


# Global registry instance
_global_registry: Optional[EmbeddingModelRegistry] = None


def get_model_registry(
    ollama_url: str = "http://localhost:11434",
) -> EmbeddingModelRegistry:
    """Get the global model registry instance."""
    global _global_registry
    if _global_registry is None:
        _global_registry = EmbeddingModelRegistry(ollama_url)
    return _global_registry


# Convenience functions
def get_model_info(model_name: str) -> Optional[Dict]:
    """Get model information from the global registry."""
    registry = get_model_registry()
    return registry.get_model_info(model_name)


def get_vector_size(
    model_name: str, ollama_url: str = "http://localhost:11434"
) -> Optional[int]:
    """Get vector size for a model, with auto-detection fallback."""
    registry = get_model_registry(ollama_url)
    return registry.get_or_detect_vector_size(model_name)


def list_available_models() -> List[Dict]:
    """List all available embedding models."""
    registry = get_model_registry()
    return registry.list_available_models()


def recommend_models(**kwargs) -> List[Dict]:
    """Recommend models based on requirements."""
    registry = get_model_registry()
    return registry.recommend_models(**kwargs)


# Example usage and testing
if __name__ == "__main__":
    registry = EmbeddingModelRegistry()

    print("Available models:")
    for model in registry.list_available_models():
        print(
            f"  {model['name']}: {model['vector_size']} dims - {model['description']}"
        )

    print("\nFast models:")
    for model in registry.recommend_models(use_case="fast"):
        print(f"  {model['name']}: {model['processing_speed']} tokens/s")

    print("\nMultilingual models:")
    for model in registry.recommend_models(multilingual=True):
        print(f"  {model['name']}: {model['supports_multilingual']}")

    print("\nTesting vector size detection:")
    test_model = "embeddinggemma:latest"
    vector_size = registry.get_or_detect_vector_size(test_model)
    print(f"  {test_model}: {vector_size} dimensions")
