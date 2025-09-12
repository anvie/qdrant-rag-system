"""
Search service for handling Qdrant operations and search logic.
"""

import asyncio
import functools
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
import sys
import os
import logging

from app.core.config import settings
from app.core.database import get_db_session
from app.models.collection import Collection as CollectionModel

# Add the project root to Python path to access the shared lib
project_root = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../../../../..")
)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from qdrant_client import QdrantClient
import requests

# Configure logger
logger = logging.getLogger(__name__)

# Import search functions from shared library
from lib.qdrant.search import (
    search_qdrant_simple,
    search_qdrant_hybrid,
    get_collection_stats,
    get_article_by_id,
    group_results_by_article,
    QdrantSearchClient,
)
from lib.embedding.client import embed_one_ollama, create_session
from lib.embedding.formatter import format_query


class SearchService:
    """Service for handling search operations with caching and connection management."""

    def __init__(
        self,
        qdrant_url: str = "http://localhost:6333",
        ollama_url: str = "http://localhost:11434",
        embedding_model: str = "embeddinggemma:latest",
        cache_ttl_minutes: int = 30,
    ):
        self.qdrant_url = qdrant_url
        self.ollama_url = ollama_url
        self.embedding_model = embedding_model
        self.cache_ttl = timedelta(minutes=cache_ttl_minutes)

        # Client instances (lazy initialization)
        self._qdrant_client: Optional[QdrantClient] = None
        self._http_session: Optional[requests.Session] = None

        # Simple in-memory cache for embeddings and search results
        self._embedding_cache: Dict[str, Tuple[List[float], datetime]] = {}
        self._search_cache: Dict[str, Tuple[List[Dict[str, Any]], datetime]] = {}

    @property
    def qdrant_client(self) -> QdrantClient:
        """Get or create Qdrant client instance."""
        if self._qdrant_client is None:
            self._qdrant_client = QdrantClient(url=self.qdrant_url)
        return self._qdrant_client

    @property
    def http_session(self) -> requests.Session:
        """Get or create HTTP session for Ollama requests."""
        if self._http_session is None:
            self._http_session = create_session()
        return self._http_session

    async def _run_sync_in_thread(self, func, *args, **kwargs):
        """Run synchronous function in thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, functools.partial(func, *args, **kwargs)
        )

    def _is_cache_valid(self, timestamp: datetime) -> bool:
        """Check if cache entry is still valid."""
        return datetime.now() - timestamp < self.cache_ttl

    def _get_cache_key(self, **kwargs) -> str:
        """Generate cache key from parameters."""
        sorted_items = sorted(kwargs.items())
        return str(hash(tuple(sorted_items)))

    def get_collection_embedding_model(self, collection_name: str) -> str:
        """Get the embedding model for a specific collection."""
        try:
            with get_db_session() as db:
                collection_meta = (
                    db.query(CollectionModel)
                    .filter(CollectionModel.name == collection_name)
                    .first()
                )

                if collection_meta and collection_meta.embedding_model:
                    logger.info(
                        f"Using collection-specific model '{collection_meta.embedding_model}' for collection '{collection_name}'"
                    )
                    return collection_meta.embedding_model
                else:
                    logger.warning(
                        f"No collection-specific model found for '{collection_name}', using default '{self.embedding_model}'"
                    )
                    return self.embedding_model

        except Exception as e:
            logger.error(
                f"Failed to get collection embedding model for '{collection_name}': {e}"
            )
            logger.info(f"Falling back to default model '{self.embedding_model}'")
            return self.embedding_model

    async def get_embedding(
        self,
        text: str,
        model: str = None,
        task_type: str = "search",
        use_cache: bool = True,
    ) -> List[float]:
        """Get embedding for text with optional caching and query formatting."""
        # Use provided model or fall back to default
        embedding_model = model or self.embedding_model

        # Format the text according to model requirements
        try:
            formatted_text = format_query(text, embedding_model, task_type)
        except NameError:
            # Fallback if format_query is not available
            formatted_text = text

        print(f"Formatted text: {formatted_text} (model: {embedding_model})")

        # Include model in cache key to prevent cross-model conflicts
        cache_key = f"{formatted_text}:{task_type}:{embedding_model}"

        if use_cache:
            cached_embedding, timestamp = self._embedding_cache.get(
                cache_key, (None, None)
            )
            if cached_embedding and self._is_cache_valid(timestamp):
                return cached_embedding

        # Generate new embedding
        embedding = await self._run_sync_in_thread(
            embed_one_ollama,
            formatted_text,
            embedding_model,
            self.ollama_url,
            120,
            self.http_session,
        )

        # Cache the result
        if use_cache:
            self._embedding_cache[cache_key] = (embedding, datetime.now())

        return embedding

    async def search_simple(
        self,
        query: str,
        collection: str = "articles",
        limit: int = 10,
        min_score: float = 0.0,
        article_id: Optional[int] = None,
        task_type: str = "search",
        use_cache: bool = True,
    ) -> List[Dict[str, Any]]:
        """Perform simple vector search with collection-specific embedding model."""
        # Get collection-specific embedding model
        embedding_model = self.get_collection_embedding_model(collection)

        cache_key = self._get_cache_key(
            query=query,
            collection=collection,
            limit=limit,
            min_score=min_score,
            article_id=article_id,
            task_type=task_type,
            search_type="simple",
            embedding_model=embedding_model,  # Include model in cache key
        )

        # Check cache
        if use_cache:
            cached_results, timestamp = self._search_cache.get(cache_key, (None, None))
            if cached_results and self._is_cache_valid(timestamp):
                return cached_results

        # Get embedding using collection-specific model
        query_embedding = await self.get_embedding(
            query, embedding_model, task_type, use_cache
        )

        results = await self._run_sync_in_thread(
            search_qdrant_simple,
            self.qdrant_client,
            collection,
            query_embedding,
            limit,
            min_score,
            article_id,
        )

        # Cache results
        if use_cache:
            self._search_cache[cache_key] = (results, datetime.now())

        return results

    async def search_hybrid(
        self,
        query: str,
        collection: str = "articles",
        limit: int = 10,
        min_score: float = 0.0,
        article_id: Optional[int] = None,
        fusion_method: str = "rrf",
        task_type: str = "search",
        use_cache: bool = True,
    ) -> List[Dict[str, Any]]:
        """Perform hybrid search combining vector similarity and text matching with collection-specific embedding model."""
        # Get collection-specific embedding model
        embedding_model = self.get_collection_embedding_model(collection)

        cache_key = self._get_cache_key(
            query=query,
            collection=collection,
            limit=limit,
            min_score=min_score,
            article_id=article_id,
            fusion_method=fusion_method,
            task_type=task_type,
            search_type="hybrid",
            embedding_model=embedding_model,  # Include model in cache key
        )

        # Check cache
        if use_cache:
            cached_results, timestamp = self._search_cache.get(cache_key, (None, None))
            if cached_results and self._is_cache_valid(timestamp):
                return cached_results

        # Get embedding using collection-specific model
        query_embedding = await self.get_embedding(
            query, embedding_model, task_type, use_cache
        )

        results = await self._run_sync_in_thread(
            search_qdrant_hybrid,
            self.qdrant_client,
            collection,
            query,
            query_embedding,
            limit,
            min_score,
            article_id,
            fusion_method,
        )

        # Cache results
        if use_cache:
            self._search_cache[cache_key] = (results, datetime.now())

        return results

    async def get_collection_stats(self, collection: str) -> Dict[str, Any]:
        """Get collection statistics."""
        return await self._run_sync_in_thread(
            get_collection_stats, self.qdrant_client, collection
        )

    async def get_article(
        self, collection: str, article_id: str
    ) -> List[Dict[str, Any]]:
        """Get all chunks for a specific article."""
        return await self._run_sync_in_thread(
            get_article_by_id, self.qdrant_client, collection, article_id
        )

    async def find_similar(
        self, document_id: int, collection: str = "articles", limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Find documents similar to the given document."""
        # Get the document first to extract its vector
        document = await self._run_sync_in_thread(
            self.qdrant_client.retrieve,
            collection_name=collection,
            ids=[document_id],
            with_vectors=True,
        )

        if not document or not document[0].vector:
            raise ValueError(f"Document {document_id} not found or has no vector")

        # Use the document's vector for similarity search
        query_vector = document[0].vector

        search_results = await self._run_sync_in_thread(
            search_qdrant_simple,
            self.qdrant_client,
            collection,
            query_vector,
            limit + 1,  # +1 to exclude self
            0.0,
        )

        # Filter out the original document
        filtered_results = [r for r in search_results if r["id"] != document_id]
        return filtered_results[:limit]

    def group_results_by_article(
        self, results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Group search results by article."""
        return group_results_by_article(results)

    def clear_cache(self):
        """Clear all cached data."""
        self._embedding_cache.clear()
        self._search_cache.clear()

    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        valid_embeddings = sum(
            1
            for _, timestamp in self._embedding_cache.values()
            if self._is_cache_valid(timestamp)
        )
        valid_searches = sum(
            1
            for _, timestamp in self._search_cache.values()
            if self._is_cache_valid(timestamp)
        )

        return {
            "total_embedding_cache_entries": len(self._embedding_cache),
            "valid_embedding_cache_entries": valid_embeddings,
            "total_search_cache_entries": len(self._search_cache),
            "valid_search_cache_entries": valid_searches,
        }

    def close(self):
        """Close connections and cleanup resources."""
        if self._http_session:
            self._http_session.close()
        if self._qdrant_client:
            # Qdrant client doesn't have explicit close method
            self._qdrant_client = None


# Global search service instance
_search_service: Optional[SearchService] = None


def get_search_service() -> SearchService:
    """Get or create global search service instance."""
    global _search_service
    if _search_service is None:
        _search_service = SearchService(
            qdrant_url=settings.QDRANT_URL,
            ollama_url=settings.OLLAMA_URL,
            embedding_model=settings.EMBEDDING_MODEL,
        )
    return _search_service


def close_search_service():
    """Close global search service instance."""
    global _search_service
    if _search_service:
        _search_service.close()
        _search_service = None
