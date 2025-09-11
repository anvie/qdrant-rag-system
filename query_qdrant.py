#!/usr/bin/env python3
import argparse
import json
import sys
import time
from collections import defaultdict
from typing import List, Optional, Dict, Any

import requests
from qdrant_client import QdrantClient, models
from qdrant_client.models import (
    Filter,
    FieldCondition,
    MatchText,
    MatchValue,
    Condition,
)
from embedding_formatter import format_query


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
    # Configure connection pooling and keep-alive
    adapter = requests.adapters.HTTPAdapter(
        pool_connections=10, pool_maxsize=20, max_retries=3
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def search_qdrant_simple(
    client: QdrantClient,
    collection_name: str,
    query_vector: List[float],
    limit: int = 10,
    min_score: float = 0.0,
    article_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Simple vector search in Qdrant collection.

    Args:
        client: Qdrant client instance
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
        "query_vector": query_vector,
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
        # results = client.query_points(**search_params)
        results = client.query_points(
            collection_name=collection_name,
            query=query_vector,
            limit=limit,
            with_payload=True,
            score_threshold=min_score if min_score > 0 else None,
        )

        return [
            {"id": result.id, "score": result.score, "payload": result.payload or {}}
            for result in results.points
        ]
    except Exception as e:
        raise RuntimeError(f"Simple search failed: {e}")


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
    """
    Hybrid search combining vector similarity and text matching for better relevance.

    Args:
        client: Qdrant client instance
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
                    FieldCondition(key="article_id", match=MatchValue(value=article_id))
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
                    FieldCondition(key="article_id", match=MatchValue(value=article_id))
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
            models.Fusion.RRF if fusion_method.lower() == "rrf" else models.Fusion.DBSF
        )

        # Execute hybrid query
        results = client.query_points(
            collection_name=collection_name,
            prefetch=prefetch_queries,
            query=models.FusionQuery(fusion=fusion),
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
        print(f"⚠️ Hybrid search failed, falling back to simple search: {e}")

        return search_qdrant_simple(
            client, collection_name, query_vector, limit, min_score, article_id
        )


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


def get_collection_stats(client: QdrantClient, collection_name: str) -> Dict[str, Any]:
    """Get basic statistics about the collection."""
    try:
        info = client.get_collection(collection_name)
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


def _get_article_by_id(
    client: QdrantClient, collection_name: str, article_id: str | int
) -> List[Dict[str, Any]]:
    """
    Retrieve all chunks belonging to a specific article ID.

    Args:
        client: Qdrant client instance
        collection_name: Name of the collection
        article_id: Article ID to retrieve

    Returns:
        List of chunks belonging to the article, sorted by chunk_index
    """
    try:
        # Create filter for specific article
        conditions: List[Condition] = [
            FieldCondition(key="article_id", match=MatchValue(value=article_id))
        ]

        # Scroll through all chunks of the article
        results = client.scroll(
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
        raise RuntimeError(f"Failed to retrieve article {article_id}: {e}")


def get_article_by_id(
    client: QdrantClient, collection_name: str, article_id: str
) -> List[Dict[str, Any]]:
    rv = _get_article_by_id(client, collection_name, article_id)
    if not rv:
        # try to use integer article_id
        rv = _get_article_by_id(client, collection_name, int(article_id))
    return rv or []


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

        output.append(f"{i:2d}. [{score:.3f}] {title}")
        output.append(f"    ID:{article_id} | {content}...")

    return "\n".join(output)


def format_grouped_results(
    grouped_results: Dict[int, List[Dict[str, Any]]], query: str
) -> str:
    """Format results grouped by article."""
    if not grouped_results:
        return "No results found."

    output = [f"\n📚 Articles found for: '{query}' ({len(grouped_results)} articles)"]
    output.append("=" * 60)

    for article_id, chunks in grouped_results.items():
        # Get article info from first chunk
        first_chunk = chunks[0]
        title = first_chunk["payload"].get("title", "No title")
        best_score = max(chunk["score"] for chunk in chunks)

        output.append(f"\n📖 Article {article_id} | Best Score: {best_score:.4f}")
        output.append(f"🏷️  {title}")
        output.append(f"📊 {len(chunks)} relevant chunk(s):")

        for chunk in chunks[:3]:  # Show top 3 chunks
            content = chunk["payload"].get("content", "")[:150].replace("\n", " ")
            chunk_idx = chunk["payload"].get("chunk_index", 0)
            score = chunk["score"]

            output.append(f"   • Chunk {chunk_idx} [{score:.3f}]: {content}...")

        if len(chunks) > 3:
            output.append(f"   ... and {len(chunks) - 3} more chunks")

        output.append("-" * 50)

    return "\n".join(output)


def format_json_results(
    results: List[Dict[str, Any]], query: str, grouped: bool = False
) -> str:
    """Format results as JSON."""
    output_data = {"query": query, "total_results": len(results), "results": results}

    if grouped:
        grouped_results = group_results_by_article(results)
        output_data["grouped_by_article"] = grouped_results
        output_data["total_articles"] = len(grouped_results)

    return json.dumps(output_data, indent=2, ensure_ascii=False)


def perform_search(args, session: requests.Session) -> None:
    """Perform a single search operation."""
    # Connect to Qdrant
    client = QdrantClient(url=args.qdrant_url, timeout=60.0)

    try:
        # Show collection stats if requested
        if args.stats:
            print("📊 Collection Statistics:")
            stats = get_collection_stats(client, args.collection)
            for key, value in stats.items():
                print(f"   {key}: {value}")
            print()

        # Generate query embedding
        print(f"🔍 Searching for: '{args.query}'")

        # Format query according to model requirements
        formatted_query = format_query(args.query, args.model, args.task_type)

        if formatted_query != args.query:
            print(f"📝 Formatted query: '{formatted_query}'")

        print("⏳ Generating query embedding...")

        embed_start = time.time()
        query_vector = embed_one_ollama(
            formatted_query,
            args.model,
            args.ollama_url,
            timeout=args.connection_timeout,
            session=session,
        )
        embed_time = (time.time() - embed_start) * 1000

        print(f"✅ Embedding generated in {embed_time:.1f}ms")

        # Perform search
        search_method = "hybrid" if args.hybrid else "simple"
        print(f"🔎 Performing {search_method} search...")
        search_start = time.time()

        if args.hybrid:
            results = search_qdrant_hybrid(
                client,
                args.collection,
                args.query,
                query_vector,
                limit=args.limit,
                min_score=args.min_score,
                article_id=args.article_id,
                fusion_method=args.fusion_method,
            )
        else:
            results = search_qdrant_simple(
                client,
                args.collection,
                query_vector,
                limit=args.limit,
                min_score=args.min_score,
                article_id=args.article_id,
            )

        search_time = (time.time() - search_start) * 1000

        print(f"✅ {search_method.title()} search completed in {search_time:.1f}ms")
        print(f"📈 Found {len(results)} results")

        # Format and display results
        if args.output_format == "json":
            output = format_json_results(results, args.query, args.group_by_article)
        elif args.output_format == "compact":
            output = format_compact_results(results, args.query)
        elif args.group_by_article:
            grouped = group_results_by_article(results)
            output = format_grouped_results(grouped, args.query)
        else:
            output = format_detailed_results(results, args.query)

        print(output)

        # Save results if output file specified
        if args.output_file:
            with open(args.output_file, "w", encoding="utf-8") as f:
                f.write(output)
            print(f"\n💾 Results saved to: {args.output_file}")

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        client.close()


def interactive_mode(args) -> None:
    """Run interactive search mode."""
    session = create_session()
    print("\n🎯 Interactive Search Mode")
    print("Type 'quit', 'exit', or 'q' to exit")
    print("Type 'help' for commands")
    print("-" * 40)
    if args.hybrid:
        print("Using Hybrid Search (vector + keyword matching)")
        print(f"Fusion Method: {args.fusion_method.upper()}")

    query_history = []

    while True:
        try:
            query = input("\n🔍 Enter search query: ").strip()

            if not query:
                continue

            if query.lower() in ["quit", "exit", "q"]:
                break

            if query.lower() == "help":
                print("\n📋 Available commands:")
                print("  help           - Show this help")
                print("  history        - Show query history")
                print("  stats          - Show collection statistics")
                print("  settings       - Show current settings")
                print(
                    "  read <id>      - Read full article by ID (e.g., 'read 146412')"
                )
                print("  quit/exit/q    - Exit interactive mode")
                continue

            if query.lower() == "history":
                if query_history:
                    print("\n📚 Query History:")
                    for i, hist_query in enumerate(query_history, 1):
                        print(f"  {i}. {hist_query}")
                else:
                    print("No query history yet.")
                continue

            if query.lower() == "settings":
                print("\n⚙️ Current Settings:")
                print(f"  Collection: {args.collection}")
                print(f"  Model: {args.model}")
                print(f"  Task Type: {args.task_type}")
                print(f"  Limit: {args.limit}")
                print(f"  Min Score: {args.min_score}")
                print(f"  Output Format: {args.output_format}")
                print(f"  Group by Article: {args.group_by_article}")
                print(f"  Hybrid Search: {args.hybrid}")
                print(f"  Fusion Method: {args.fusion_method}")
                continue

            if query.lower() == "stats":
                client = QdrantClient(url=args.qdrant_url, timeout=60.0)
                try:
                    stats = get_collection_stats(client, args.collection)
                    print("\n📊 Collection Statistics:")
                    for key, value in stats.items():
                        print(f"   {key}: {value}")
                finally:
                    client.close()
                continue

            # Handle 'read' command
            if query.lower().startswith("read "):
                try:
                    # Extract article ID from command
                    parts = query.split()
                    if len(parts) < 2:
                        print("❌ Usage: read <article_id>")
                        print("   Example: read 146412")
                        continue

                    # try:
                    #     article_id = int(parts[1])
                    # except ValueError:
                    #     print(f"❌ Invalid article ID: {parts[1]}")
                    #     print("   Article ID must be a number")
                    #     continue
                    article_id = parts[1]

                    # Retrieve and display article
                    client = QdrantClient(url=args.qdrant_url, timeout=60.0)
                    try:
                        print(f"📖 Retrieving article {article_id}...")
                        chunks = get_article_by_id(client, args.collection, article_id)
                        output = format_article_content(chunks, article_id)
                        print(output)

                        # Optionally save to file
                        save_prompt = (
                            input("\n💾 Save to file? (y/n): ").strip().lower()
                        )
                        if save_prompt == "y":
                            filename = f"article_{article_id}.txt"
                            with open(filename, "w", encoding="utf-8") as f:
                                f.write(output)
                            print(f"✅ Saved to {filename}")
                    finally:
                        client.close()

                except Exception as e:
                    print(f"❌ Error reading article: {e}")
                continue

            # Perform search
            query_history.append(query)
            args.query = query
            perform_search(args, session)

        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except EOFError:
            break

    session.close()


def main():
    parser = argparse.ArgumentParser(
        description="Search Islamic articles using semantic vector search with Qdrant and Ollama",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic semantic search
  python query_qdrant.py --query "hukum shalat jamaah"
  
  # Hybrid search (recommended for better relevance)
  python query_qdrant.py --query "zakat fitrah" --hybrid
  
  # Advanced hybrid search with DBSF fusion
  python query_qdrant.py --query "umrah haji" --hybrid --fusion-method dbsf --limit 5
  
  # Question answering task type for EmbeddingGemma
  python query_qdrant.py --query "Bagaimana cara shalat yang benar?" --model embeddinggemma:latest --task-type qa
  
  # Hybrid search with filtering
  python query_qdrant.py --query "puasa ramadan" --hybrid --min-score 0.7 --group-by-article
  
  # JSON output for integration
  python query_qdrant.py --query "umrah haji" --hybrid --output-format json
  
  # Interactive mode
  python query_qdrant.py --interactive --hybrid
  
  # Search within specific article
  python query_qdrant.py --article-id 146412 --query "makmum bersuara" --hybrid
        """,
    )

    # Required arguments
    parser.add_argument("--query", type=str, help="Search query text")

    # Connection arguments
    parser.add_argument(
        "--qdrant-url", default="http://localhost:6333", help="Qdrant server URL"
    )
    parser.add_argument(
        "--collection", default="articles", help="Qdrant collection name"
    )
    parser.add_argument(
        "--ollama-url", default="http://localhost:11434", help="Ollama server URL"
    )
    parser.add_argument("--model", default="bge-m3:567m", help="Ollama embedding model")

    # Search parameters
    parser.add_argument(
        "--limit", type=int, default=10, help="Maximum number of results"
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=0.0,
        help="Minimum similarity score threshold",
    )
    parser.add_argument(
        "--article-id", type=int, help="Search within specific article only"
    )
    parser.add_argument(
        "--hybrid",
        action="store_true",
        help="Use hybrid search (vector + keyword matching)",
    )
    parser.add_argument(
        "--fusion-method",
        choices=["rrf", "dbsf"],
        default="rrf",
        help="Fusion method for hybrid search: RRF (Reciprocal Rank Fusion) or DBSF (Distribution-Based Score Fusion)",
    )
    parser.add_argument(
        "--task-type",
        choices=[
            "search",
            "qa",
            "question_answering",
            "classification",
            "similarity",
            "code",
        ],
        default="search",
        help="Task type for query formatting (affects embedding generation for models like embeddinggemma)",
    )

    # Output options
    parser.add_argument(
        "--output-format",
        choices=["detailed", "compact", "json"],
        default="detailed",
        help="Output format",
    )
    parser.add_argument(
        "--group-by-article",
        action="store_true",
        help="Group results by article (show article-level results)",
    )
    parser.add_argument("--output-file", type=str, help="Save results to file")

    # Utility options
    parser.add_argument(
        "--stats", action="store_true", help="Show collection statistics"
    )
    parser.add_argument(
        "--interactive", action="store_true", help="Run in interactive mode"
    )
    parser.add_argument(
        "--connection-timeout",
        type=int,
        default=120,
        help="HTTP timeout for embedding requests (seconds)",
    )

    args = parser.parse_args()

    print("🕌 Qdrant Article Search - Islamic Articles Database")
    print("=" * 55)

    # Validate arguments
    if not args.interactive and not args.query:
        parser.error("--query is required unless using --interactive mode")

    if args.interactive:
        interactive_mode(args)
    else:
        session = create_session()
        try:
            perform_search(args, session)
        finally:
            session.close()


if __name__ == "__main__":
    main()
