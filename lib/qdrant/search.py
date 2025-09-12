"""
Qdrant search operations for semantic and hybrid search functionality.

This module provides search functions for querying Qdrant vector collections,
including simple vector search, hybrid search, and result formatting.
"""

import logging
from collections import defaultdict
from typing import List, Optional, Dict, Any

from qdrant_client import QdrantClient, models
from qdrant_client.models import (
    Filter,
    FieldCondition,
    MatchText,
    MatchValue,
    Condition,
)

logger = logging.getLogger(__name__)


class QdrantSearchClient:
    """Client for performing searches in Qdrant vector collections."""

    def __init__(self, client: QdrantClient):
        """
        Initialize the search client.

        Args:
            client: Initialized QdrantClient instance
        """
        self.client = client

    def simple_search(
        self,
        collection_name: str,
        query_vector: List[float],
        limit: int = 10,
        min_score: float = 0.0,
        article_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Simple vector search in Qdrant collection.

        Args:
            collection_name: Name of the collection to search
            query_vector: Query embedding vector
            limit: Maximum number of results
            min_score: Minimum similarity score threshold
            article_id: Optional article ID to search within specific article

        Returns:
            List of search results with scores and payload
        """
        search_params = {
            "collection_name": collection_name,
            "query": query_vector,
            "limit": limit,
            "with_payload": True,
            "score_threshold": min_score if min_score > 0 else None,
        }

        # Add filter for specific article if requested
        if article_id:
            conditions: List[Condition] = [
                FieldCondition(key="article_id", match=MatchValue(value=article_id))
            ]
            search_params["query_filter"] = Filter(must=conditions)

        try:
            results = self.client.query_points(**search_params)

            return [
                {
                    "id": result.id,
                    "score": result.score,
                    "payload": result.payload or {},
                }
                for result in results.points
            ]
        except Exception as e:
            raise RuntimeError(f"Simple search failed: {e}")

    def hybrid_search(
        self,
        collection_name: str,
        query_text: str,
        query_vector: List[float],
        limit: int = 10,
        min_score: float = 0.0,
        article_id: Optional[int] = None,
        fusion_method: str = "rrf",
    ) -> List[Dict[str, Any]]:
        """
        Hybrid search combining vector similarity and text matching for better relevance.

        Args:
            collection_name: Name of the collection to search
            query_text: Original query text for keyword matching
            query_vector: Query embedding vector for semantic search
            limit: Maximum number of results
            min_score: Minimum similarity score threshold
            article_id: Optional article ID to search within specific article
            fusion_method: Fusion method ('rrf' or 'dbsf')

        Returns:
            List of search results with hybrid scores and payload
        """
        try:
            # Prepare filters
            query_filter = None
            if article_id:
                article_conditions: List[Condition] = [
                    FieldCondition(key="article_id", match=MatchValue(value=article_id))
                ]
                query_filter = Filter(must=article_conditions)

            # Build prefetch queries for hybrid search
            prefetch_queries = []

            # 1. Semantic search (vector similarity)
            prefetch_queries.append(
                models.Prefetch(
                    query=query_vector,
                    limit=limit * 2,  # Get more candidates for fusion
                    filter=query_filter,
                )
            )

            # 2. Title keyword matching (boost title relevance)
            if query_text.strip():
                title_conditions: List[Condition] = [
                    FieldCondition(key="title", match=MatchText(text=query_text))
                ]
                if article_id:
                    title_conditions.append(
                        FieldCondition(
                            key="article_id", match=MatchValue(value=article_id)
                        )
                    )
                prefetch_queries.append(
                    models.Prefetch(
                        query=query_vector,
                        limit=limit * 2,
                        filter=Filter(must=title_conditions),
                    )
                )

            # 3. Content keyword matching
            if query_text.strip():
                content_conditions: List[Condition] = [
                    FieldCondition(key="content", match=MatchText(text=query_text))
                ]
                if article_id:
                    content_conditions.append(
                        FieldCondition(
                            key="article_id", match=MatchValue(value=article_id)
                        )
                    )
                prefetch_queries.append(
                    models.Prefetch(
                        query=query_vector,
                        limit=limit * 2,
                        filter=Filter(must=content_conditions),
                    )
                )

            # Select fusion method
            fusion = (
                models.Fusion.RRF
                if fusion_method.lower() == "rrf"
                else models.Fusion.DBSF
            )

            # Execute hybrid query
            results = self.client.query_points(
                collection_name=collection_name,
                prefetch=prefetch_queries,
                query=models.FusionQuery(fusion=fusion),
                limit=limit,
                with_payload=True,
                score_threshold=min_score if min_score > 0 else None,
            )

            return [
                {
                    "id": result.id,
                    "score": result.score,
                    "payload": result.payload or {},
                }
                for result in results.points
            ]

        except Exception as e:
            # Fallback to simple vector search if hybrid fails
            logger.warning(f"Hybrid search failed, falling back to simple search: {e}")

            return self.simple_search(
                collection_name, query_vector, limit, min_score, article_id
            )

    def get_article_by_id(
        self, collection_name: str, article_id: str
    ) -> List[Dict[str, Any]]:
        """
        Retrieve all chunks belonging to a specific article ID.

        Args:
            collection_name: Name of the collection
            article_id: Article ID to retrieve

        Returns:
            List of chunks belonging to the article, sorted by chunk_index
        """

        def _get_article_by_id_internal(art_id):
            """Internal function to get article by ID (int or str)."""
            try:
                # Create filter for specific article
                conditions: List[Condition] = [
                    FieldCondition(key="article_id", match=MatchValue(value=art_id))
                ]

                # Scroll through all chunks of the article
                results = self.client.scroll(
                    collection_name=collection_name,
                    scroll_filter=Filter(must=conditions),
                    limit=100,  # Max chunks per article
                    with_payload=True,
                    with_vectors=False,  # Don't need vectors for display
                )

                chunks = []
                if results and results[0]:
                    for point in results[0]:
                        chunks.append({"id": point.id, "payload": point.payload or {}})

                # Sort by chunk_index
                chunks.sort(key=lambda x: x["payload"].get("chunk_index", 0))

                return chunks

            except Exception as e:
                raise RuntimeError(f"Failed to retrieve article {art_id}: {e}")

        # Try with original article_id first
        rv = _get_article_by_id_internal(article_id)
        if not rv:
            # Try to use integer article_id
            try:
                rv = _get_article_by_id_internal(int(article_id))
            except (ValueError, TypeError):
                pass
        return rv or []

    def get_collection_stats(self, collection_name: str) -> Dict[str, Any]:
        """Get basic statistics about the collection."""
        try:
            info = self.client.get_collection(collection_name)
            return {
                "points_count": info.points_count or 0,
                "vectors_count": info.vectors_count or 0
                if hasattr(info, "vectors_count")
                else info.points_count or 0,
                "status": info.status.name
                if hasattr(info.status, "name")
                else str(info.status),
            }
        except Exception as e:
            return {"error": str(e)}


# Utility functions for result processing
def group_results_by_article(
    results: List[Dict[str, Any]],
) -> Dict[int, List[Dict[str, Any]]]:
    """
    Group search results by article_id.

    Args:
        results: List of search results

    Returns:
        Dictionary mapping article_id to list of chunks
    """
    grouped = defaultdict(list)

    for result in results:
        article_id = result["payload"].get("article_id")
        if article_id:
            grouped[article_id].append(result)

    # Sort chunks within each article by chunk_index
    for article_id in grouped:
        grouped[article_id].sort(key=lambda x: x["payload"].get("chunk_index", 0))

    return dict(grouped)


def format_article_content(chunks: List[Dict[str, Any]], article_id: str) -> str:
    """
    Format all chunks of an article into a readable display.

    Args:
        chunks: List of chunks belonging to the article
        article_id: Article ID

    Returns:
        Formatted article content string
    """
    if not chunks:
        return f"❌ Article with ID {article_id} not found."

    output = []

    # Get article info from first chunk
    first_chunk = chunks[0]["payload"]
    title = first_chunk.get("title", "No title")

    output.append("\n" + "=" * 70)
    output.append(f"📖 ARTICLE ID: {article_id}")
    output.append(f"📚 Title: {title}")
    output.append(f"📄 Total Chunks: {len(chunks)}")
    output.append("=" * 70)

    # Display all chunks in order
    for chunk_data in chunks:
        payload = chunk_data["payload"]
        chunk_index = payload.get("chunk_index", 0)
        content = payload.get("content", "")

        output.append(f"\n[Chunk {chunk_index}]")
        output.append("-" * 40)
        output.append(content)

    output.append("\n" + "=" * 70)
    output.append(f"📊 End of Article {article_id} ({len(chunks)} chunks)")
    output.append("=" * 70)

    return "\n".join(output)


def format_detailed_results(results: List[Dict[str, Any]], query: str) -> str:
    """Format search results in detailed human-readable format."""
    if not results:
        return "No results found."

    output = [f"\n🔍 Search Results for: '{query}'"]
    output.append("=" * 60)

    for i, result in enumerate(results, 1):
        payload = result["payload"]
        title = payload.get("title", "No title")
        content = payload.get("content", "")
        article_id = payload.get("article_id", "")
        chunk_index = payload.get("chunk_index", 0)
        score = result["score"]

        output.append(f"\n📄 Result {i} | Score: {score:.4f}")
        output.append(f"🏷️  Title: {title}")
        output.append(f"🔗 Article ID: {article_id} | Chunk: {chunk_index}")
        output.append("📝 Content:")

        # Format content with line breaks for readability
        content_lines = content.split("\n")
        for line in content_lines[:10]:  # Limit to first 10 lines
            if line.strip():
                output.append(f"   {line.strip()}")

        if len(content_lines) > 10:
            output.append("   ... (content truncated)")

        output.append("-" * 60)

    return "\n".join(output)


def format_compact_results(results: List[Dict[str, Any]], query: str) -> str:
    """Format search results in compact format."""
    if not results:
        return "No results found."

    output = [f"\nCompact Results for: '{query}' ({len(results)} results)"]
    output.append("=" * 50)

    for i, result in enumerate(results, 1):
        payload = result["payload"]
        title = payload.get("title", "No title")[:50]
        content = payload.get("content", "")[:100].replace("\n", " ")
        article_id = payload.get("article_id", "")
        score = result["score"]

        output.append(f"{i:2d}. [{score:.3f}] {title}...")
        output.append(f"    ID:{article_id} | {content}...")

    return "\n".join(output)


# Legacy functions for backward compatibility
def search_qdrant_simple(
    client: QdrantClient,
    collection_name: str,
    query_vector: List[float],
    limit: int = 10,
    min_score: float = 0.0,
    article_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Legacy function for backward compatibility."""
    search_client = QdrantSearchClient(client)
    return search_client.simple_search(
        collection_name, query_vector, limit, min_score, article_id
    )


def search_qdrant_hybrid(
    client: QdrantClient,
    collection_name: str,
    query_text: str,
    query_vector: List[float],
    limit: int = 10,
    min_score: float = 0.0,
    article_id: Optional[int] = None,
    fusion_method: str = "rrf",
) -> List[Dict[str, Any]]:
    """Legacy function for backward compatibility."""
    search_client = QdrantSearchClient(client)
    return search_client.hybrid_search(
        collection_name,
        query_text,
        query_vector,
        limit,
        min_score,
        article_id,
        fusion_method,
    )


def get_article_by_id(
    client: QdrantClient, collection_name: str, article_id: str
) -> List[Dict[str, Any]]:
    """Legacy function for backward compatibility."""
    search_client = QdrantSearchClient(client)
    return search_client.get_article_by_id(collection_name, article_id)


def get_collection_stats(client: QdrantClient, collection_name: str) -> Dict[str, Any]:
    """Legacy function for backward compatibility."""
    search_client = QdrantSearchClient(client)
    return search_client.get_collection_stats(collection_name)
