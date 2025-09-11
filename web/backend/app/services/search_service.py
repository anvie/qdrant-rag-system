"""
Search service for handling Qdrant operations and search logic.
"""

import asyncio
import functools
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
import sys
import os

from app.core.config import settings

# Add parent directories to path to import existing modules
sys.path.append(os.path.join(os.path.dirname(__file__), "../../../../.."))

from qdrant_client import QdrantClient
import requests

# Import search functions from parent directory
try:
    from query_qdrant import (
        search_qdrant_simple,
        search_qdrant_hybrid,
        embed_one_ollama,
        get_collection_stats,
        get_article_by_id,
        group_results_by_article,
        create_session,
    )
except ImportError as e:
    print(f"Warning: Could not import search functions: {e}")


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

    async def get_embedding(self, text: str, use_cache: bool = True) -> List[float]:
        """Get embedding for text with optional caching."""
        if use_cache:
            cached_embedding, timestamp = self._embedding_cache.get(text, (None, None))
            if cached_embedding and self._is_cache_valid(timestamp):
                return cached_embedding

        print(f"Generate embedding for text {text} with model {self.embedding_model}")
        # Generate new embedding
        embedding = await self._run_sync_in_thread(
            embed_one_ollama,
            text,
            self.embedding_model,
            self.ollama_url,
            120,
            self.http_session,
        )

        # Cache the result
        if use_cache:
            self._embedding_cache[text] = (embedding, datetime.now())

        return embedding

    async def search_simple(
        self,
        query: str,
        collection: str = "articles",
        limit: int = 10,
        min_score: float = 0.0,
        article_id: Optional[int] = None,
        use_cache: bool = True,
    ) -> List[Dict[str, Any]]:
        """Perform simple vector search."""
        cache_key = self._get_cache_key(
            query=query,
            collection=collection,
            limit=limit,
            min_score=min_score,
            article_id=article_id,
            search_type="simple",
        )

        # Check cache
        if use_cache:
            cached_results, timestamp = self._search_cache.get(cache_key, (None, None))
            if cached_results and self._is_cache_valid(timestamp):
                return cached_results

        # Get embedding and search
        query_embedding = await self.get_embedding(query, use_cache)

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
        use_cache: bool = True,
    ) -> List[Dict[str, Any]]:
        """Perform hybrid search combining vector similarity and text matching."""
        cache_key = self._get_cache_key(
            query=query,
            collection=collection,
            limit=limit,
            min_score=min_score,
            article_id=article_id,
            fusion_method=fusion_method,
            search_type="hybrid",
        )

        # Check cache
        if use_cache:
            cached_results, timestamp = self._search_cache.get(cache_key, (None, None))
            if cached_results and self._is_cache_valid(timestamp):
                return cached_results

        # Get embedding and search
        query_embedding = await self.get_embedding(query, use_cache)

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
