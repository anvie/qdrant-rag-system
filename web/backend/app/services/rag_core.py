"""
Core RAG (Retrieval-Augmented Generation) functions.
Extracted from the working chat_rag.py implementation.
"""

import asyncio
import json
import time
from typing import List, Optional, Dict, Any, Generator
import logging

import requests
from qdrant_client import QdrantClient, models
from qdrant_client.models import Filter, FieldCondition, MatchText

logger = logging.getLogger(__name__)


def embed_one_ollama(
    text: str,
    model: str,
    ollama_url: str,
    timeout: int = 120,
    session: Optional[requests.Session] = None,
) -> List[float]:
    """Generate embedding for a single text using Ollama API."""
    if session is None:
        session = requests

    # Try the working combinations first
    attempts = [
        (f"{ollama_url.rstrip('/')}/api/embeddings", {"model": model, "prompt": text}),
        (f"{ollama_url.rstrip('/')}/api/embed", {"model": model, "input": text}),
    ]

    last_err: Optional[str] = None
    for endpoint, payload in attempts:
        try:
            r = session.post(endpoint, json=payload, timeout=timeout)
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


def create_session() -> requests.Session:
    """Create a reusable HTTP session with connection pooling."""
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(
        pool_connections=10, pool_maxsize=20, max_retries=3
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def search_qdrant_hybrid(
    client: QdrantClient,
    collection_name: str,
    query_text: str,
    query_vector: List[float],
    limit: int = 5,
    min_score: float = 0.0,
) -> List[Dict[str, Any]]:
    """
    Hybrid search combining vector similarity and text matching.

    Args:
        client: Qdrant client instance
        collection_name: Name of the collection to search
        query_text: Original query text for keyword matching
        query_vector: Query embedding vector for semantic search
        limit: Maximum number of results
        min_score: Minimum similarity score threshold

    Returns:
        List of search results with scores and payload
    """
    try:
        # Build prefetch queries for hybrid search
        prefetch_queries = []

        # 1. Semantic search (vector similarity)
        prefetch_queries.append(
            models.Prefetch(
                query=query_vector,
                limit=limit * 2,  # Get more candidates for fusion
            )
        )

        # 2. Title keyword matching
        if query_text.strip():
            prefetch_queries.append(
                models.Prefetch(
                    query=query_vector,
                    limit=limit * 2,
                    filter=Filter(
                        must=[
                            FieldCondition(
                                key="title", match=MatchText(text=query_text)
                            )
                        ]
                    ),
                )
            )

        # 3. Content keyword matching
        if query_text.strip():
            prefetch_queries.append(
                models.Prefetch(
                    query=query_vector,
                    limit=limit * 2,
                    filter=Filter(
                        must=[
                            FieldCondition(
                                key="content", match=MatchText(text=query_text)
                            )
                        ]
                    ),
                )
            )

        # Execute hybrid query with fusion
        try:
            # Try RRF fusion first (newer Qdrant versions)
            results = client.query_points(
                collection_name=collection_name,
                prefetch=prefetch_queries,
                query=models.FusionQuery(fusion=models.Fusion.RRF),
                limit=limit,
                with_payload=True,
                score_threshold=min_score if min_score > 0 else None,
            )
        except (AttributeError, TypeError):
            # Fallback to DBSF fusion if RRF is not available
            results = client.query_points(
                collection_name=collection_name,
                prefetch=prefetch_queries,
                query=models.FusionQuery(fusion=models.Fusion.DBSF),
                limit=limit,
                with_payload=True,
                score_threshold=min_score if min_score > 0 else None,
            )

        return [
            {"id": result.id, "score": result.score, "payload": result.payload or {}}
            for result in results.points
        ]

    except Exception as e:
        # Fallback to simple vector search if hybrid fails
        logger.warning(f"Hybrid search failed, falling back to simple search: {e}")

        search_params = {
            "collection_name": collection_name,
            "query_vector": query_vector,
            "limit": limit,
            "with_payload": True,
            "score_threshold": min_score if min_score > 0 else None,
        }

        results = client.search(**search_params)
        return [
            {"id": result.id, "score": result.score, "payload": result.payload or {}}
            for result in results
        ]


def generate_llm_response(
    prompt: str,
    model: str,
    ollama_url: str,
    temperature: float = 0.7,
    max_tokens: int = 2000,
    stream: bool = False,
    system_prompt: Optional[str] = None,
    session: Optional[requests.Session] = None,
) -> str:
    """
    Generate response from Ollama LLM.

    Args:
        prompt: User prompt with context
        model: LLM model name
        ollama_url: Ollama API URL
        temperature: Sampling temperature
        max_tokens: Maximum tokens in response
        stream: Whether to stream the response
        system_prompt: System instructions
        session: HTTP session

    Returns:
        Generated response text
    """
    if session is None:
        session = requests

    endpoint = f"{ollama_url.rstrip('/')}/api/generate"

    payload = {
        "model": model,
        "prompt": prompt,
        "temperature": temperature,
        "num_predict": max_tokens,
        "stream": stream,
    }

    if system_prompt:
        payload["system"] = system_prompt

    try:
        response = session.post(endpoint, json=payload, timeout=120, stream=stream)
        response.raise_for_status()

        if stream:
            # Return generator for streaming
            return response
        else:
            data = response.json()
            return data.get("response", "")

    except Exception as e:
        raise RuntimeError(f"LLM generation failed: {e}")


def stream_llm_response(
    prompt: str,
    model: str,
    ollama_url: str,
    temperature: float = 0.7,
    max_tokens: int = 2000,
    system_prompt: Optional[str] = None,
    session: Optional[requests.Session] = None,
) -> Generator[str, None, None]:
    """
    Stream response from Ollama LLM.

    Yields chunks of generated text as they arrive.
    """
    if session is None:
        session = requests

    endpoint = f"{ollama_url.rstrip('/')}/api/generate"

    payload = {
        "model": model,
        "prompt": prompt,
        "temperature": temperature,
        "num_predict": max_tokens,
        "stream": True,
    }

    if system_prompt:
        payload["system"] = system_prompt

    try:
        response = session.post(endpoint, json=payload, timeout=120, stream=True)
        response.raise_for_status()

        for line in response.iter_lines():
            if line:
                try:
                    data = json.loads(line)
                    if "response" in data:
                        yield data["response"]
                    if data.get("done", False):
                        break
                except json.JSONDecodeError:
                    continue

    except Exception as e:
        yield f"\n❌ Error: {e}"


def build_rag_prompt(
    query: str, context_chunks: List[Dict[str, Any]], max_context_length: int = 3000
) -> tuple[str, List[Dict[str, Any]]]:
    """
    Build augmented prompt with retrieved context.

    Args:
        query: User query
        context_chunks: Retrieved context chunks from Qdrant
        max_context_length: Maximum context length in characters

    Returns:
        Tuple of (augmented prompt, source citations)
    """
    sources = []
    context_parts = []
    total_length = 0

    for i, chunk in enumerate(context_chunks, 1):
        payload = chunk["payload"]
        content = payload.get("content", "")
        title = payload.get("title", "Unknown")
        article_id = payload.get("article_id", "")
        chunk_index = payload.get("chunk_index", 0)
        score = chunk["score"]

        # Check if adding this chunk would exceed max length
        if total_length + len(content) > max_context_length and i > 1:
            break

        context_parts.append(f"[Context {i}]:\n{content}")
        total_length += len(content)

        sources.append(
            {
                "index": i,
                "title": title,
                "article_id": article_id,
                "chunk_index": chunk_index,
                "score": score,
            }
        )

    # Build the augmented prompt
    context_text = "\n\n".join(context_parts)

    prompt = f"""Based on the following context, please answer the user's question. 
If the context doesn't contain relevant information, please say so.
Just answer don't mention about how you get the information from the context in your answer.

Context:
{context_text}

User Question: {query}

Please provide a helpful, detailed, completed, and accurate answer --in bahasa Indonesia-- based on the context provided:"""

    return prompt, sources


async def async_search_qdrant_hybrid(
    client: QdrantClient,
    collection_name: str,
    query_text: str,
    query_vector: List[float],
    limit: int = 5,
    min_score: float = 0.0,
) -> List[Dict[str, Any]]:
    """Async wrapper for hybrid search."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        search_qdrant_hybrid,
        client,
        collection_name,
        query_text,
        query_vector,
        limit,
        min_score,
    )


async def async_embed_one_ollama(
    text: str,
    model: str,
    ollama_url: str,
    timeout: int = 120,
    session: Optional[requests.Session] = None,
) -> List[float]:
    """Async wrapper for embedding generation."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, embed_one_ollama, text, model, ollama_url, timeout, session
    )


async def async_stream_llm_response(
    prompt: str,
    model: str,
    ollama_url: str,
    temperature: float = 0.7,
    max_tokens: int = 2000,
    system_prompt: Optional[str] = None,
    session: Optional[requests.Session] = None,
) -> Generator[str, None, None]:
    """Async wrapper for streaming LLM response."""
    loop = asyncio.get_event_loop()

    def stream_wrapper():
        try:
            return list(
                stream_llm_response(
                    prompt=prompt,
                    model=model,
                    ollama_url=ollama_url,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    system_prompt=system_prompt,
                    session=session,
                )
            )
        except Exception as e:
            logger.error(f"Stream wrapper error: {e}")
            return [f"Error: {str(e)}"]

    chunks = await loop.run_in_executor(None, stream_wrapper)
    for chunk in chunks:
        yield chunk
