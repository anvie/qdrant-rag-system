"""
Ollama embedding client for generating text embeddings.

This module provides a client for the Ollama API to generate embeddings
for text content using various embedding models.
"""

import requests
import logging
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


class OllamaEmbeddingClient:
    """Client for generating embeddings using Ollama API."""

    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        timeout: int = 120,
        session: Optional[requests.Session] = None,
    ):
        """
        Initialize the Ollama embedding client.

        Args:
            ollama_url: Base URL for Ollama API
            timeout: Request timeout in seconds
            session: Optional requests session for connection pooling
        """
        self.ollama_url = ollama_url.rstrip("/")
        self.timeout = timeout
        self.session = session or self._create_session()

    def _create_session(self) -> requests.Session:
        """Create a reusable HTTP session with connection pooling."""
        session = requests.Session()
        # Configure connection pooling and keep-alive
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10, pool_maxsize=20, max_retries=3
        )
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def embed_text(self, text: str, model: str) -> List[float]:
        """
        Generate embedding for a single text using Ollama API.

        Args:
            text: Text to embed
            model: Model name to use for embedding

        Returns:
            List of embedding values

        Raises:
            RuntimeError: If embedding generation fails
        """
        # Try the working combinations first
        attempts = [
            (f"{self.ollama_url}/api/embeddings", {"model": model, "prompt": text}),
            (f"{self.ollama_url}/api/embed", {"model": model, "input": text}),
        ]

        last_err: Optional[str] = None
        for endpoint, payload in attempts:
            try:
                r = self.session.post(endpoint, json=payload, timeout=self.timeout)
                r.raise_for_status()
                data = r.json()
                if isinstance(data, dict):
                    if (
                        "embedding" in data
                        and isinstance(data["embedding"], list)
                        and len(data["embedding"]) > 0
                    ):
                        return data["embedding"]
                    if (
                        "embeddings" in data
                        and isinstance(data["embeddings"], list)
                        and data["embeddings"]
                        and len(data["embeddings"][0]) > 0
                    ):
                        return data["embeddings"][0]
                last_err = f"Unexpected response: {data}"
            except Exception as e:
                last_err = f"{type(e).__name__}: {e}"
        raise RuntimeError(f"Ollama embedding failed. Last error: {last_err}")

    def embed_batch(
        self, texts: List[str], model: str, batch_size: int = 10
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed
            model: Model name to use for embedding
            batch_size: Number of texts to process at once

        Returns:
            List of embedding vectors
        """
        embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            batch_embeddings = [self.embed_text(text, model) for text in batch]
            embeddings.extend(batch_embeddings)
        return embeddings

    def get_available_models(self) -> List[Dict[str, Any]]:
        """
        Get list of available models from Ollama.

        Returns:
            List of model information dictionaries
        """
        try:
            response = self.session.get(
                f"{self.ollama_url}/api/tags", timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()
            return data.get("models", [])
        except Exception as e:
            logger.error(f"Failed to get available models: {e}")
            return []

    def health_check(self) -> bool:
        """
        Check if Ollama service is available.

        Returns:
            True if service is healthy, False otherwise
        """
        try:
            response = self.session.get(f"{self.ollama_url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception:
            return False


# Legacy function for backward compatibility
def embed_one_ollama(
    text: str,
    model: str,
    ollama_url: str,
    timeout: int = 120,
    session: Optional[requests.Session] = None,
) -> List[float]:
    """
    Generate embedding for a single text using Ollama API.

    This is a legacy function maintained for backward compatibility.
    New code should use OllamaEmbeddingClient instead.
    """
    client = OllamaEmbeddingClient(ollama_url, timeout, session)
    return client.embed_text(text, model)


# Create a default session for backward compatibility
def create_session() -> requests.Session:
    """Create a reusable HTTP session with connection pooling."""
    client = OllamaEmbeddingClient()
    return client.session
