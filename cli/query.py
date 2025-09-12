#!/usr/bin/env python3
"""
Query CLI for the Qdrant RAG system.

This script provides command-line access to semantic search functionality
using the shared library components.
"""

import argparse
import json
import sys
import time
from typing import List, Dict, Any

from qdrant_client import QdrantClient

# Import from shared library (use PYTHONPATH environment variable)
from lib.embedding.client import OllamaEmbeddingClient
from lib.embedding.formatter import format_query
from lib.qdrant.search import (
    QdrantSearchClient,
    group_results_by_article,
    format_article_content,
    format_detailed_results,
    format_compact_results,
)
from lib.utils.config import get_config, setup_logging


def format_grouped_results(
    grouped_results: Dict[int, List[Dict[str, Any]]], query: str
) -> str:
    """Format search results grouped by article."""
    if not grouped_results:
        return "No results found."

    output = [f"\n📚 Search Results Grouped by Article for: '{query}'"]
    output.append("=" * 60)
    output.append(f"Found {len(grouped_results)} articles with relevant content")

    for article_id, chunks in grouped_results.items():
        title = chunks[0]["payload"].get("title", "No title")
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


def perform_search(args, embedding_client: OllamaEmbeddingClient) -> None:
    """Perform a single search operation."""
    # Connect to Qdrant
    qdrant_client = QdrantClient(url=args.qdrant_url, timeout=60.0)
    search_client = QdrantSearchClient(qdrant_client)

    try:
        # Show collection stats if requested
        if args.stats:
            print("📊 Collection Statistics:")
            stats = search_client.get_collection_stats(args.collection)
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
        query_vector = embedding_client.embed_text(formatted_query, args.model)
        embed_time = (time.time() - embed_start) * 1000

        print(f"✅ Embedding generated in {embed_time:.1f}ms")

        # Perform search
        search_method = "hybrid" if args.hybrid else "simple"
        print(f"🔎 Performing {search_method} search...")
        search_start = time.time()

        if args.hybrid:
            results = search_client.hybrid_search(
                args.collection,
                args.query,
                query_vector,
                limit=args.limit,
                min_score=args.min_score,
                article_id=args.article_id,
                fusion_method=args.fusion_method,
            )
        else:
            results = search_client.simple_search(
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
        qdrant_client.close()


def show_article(args, search_client: QdrantSearchClient) -> None:
    """Show full article content."""
    print(f"📖 Retrieving article {args.article_id}...")

    try:
        chunks = search_client.get_article_by_id(args.collection, str(args.article_id))
        output = format_article_content(chunks, str(args.article_id))
        print(output)

        # Save to file if specified
        if args.output_file:
            with open(args.output_file, "w", encoding="utf-8") as f:
                f.write(output)
            print(f"\n💾 Article saved to: {args.output_file}")

    except Exception as e:
        print(f"❌ Error retrieving article: {e}", file=sys.stderr)
        sys.exit(1)


def interactive_mode(args) -> None:
    """Run interactive search mode."""
    # Initialize clients
    embedding_client = OllamaEmbeddingClient(
        args.ollama_url, timeout=args.connection_timeout
    )
    qdrant_client = QdrantClient(url=args.qdrant_url, timeout=60.0)
    search_client = QdrantSearchClient(qdrant_client)

    print("\n🎯 Interactive Search Mode")
    print("Type 'quit', 'exit', or 'q' to exit")
    print("Type 'help' for commands")
    print("Type 'stats' for collection statistics")
    print("Type 'article <id>' to view full article")
    print("-" * 40)
    if args.hybrid:
        print("Using Hybrid Search (vector + keyword matching)")
        print(f"Fusion Method: {args.fusion_method.upper()}")

    query_history = []

    try:
        while True:
            try:
                query = input("\n🔍 Enter search query: ").strip()

                if not query:
                    continue

                if query.lower() in ["quit", "exit", "q"]:
                    print("👋 Goodbye!")
                    break

                if query.lower() == "help":
                    print("\nAvailable commands:")
                    print("  help           - Show this help message")
                    print("  stats          - Show collection statistics")
                    print("  article <id>   - View full article by ID")
                    print("  history        - Show query history")
                    print("  quit/exit/q    - Exit interactive mode")
                    print("\nSearch options:")
                    print(f"  Collection: {args.collection}")
                    print(f"  Model: {args.model}")
                    print(f"  Limit: {args.limit}")
                    print(f"  Min Score: {args.min_score}")
                    print(f"  Search Type: {'Hybrid' if args.hybrid else 'Simple'}")
                    continue

                if query.lower() == "stats":
                    stats = search_client.get_collection_stats(args.collection)
                    print("\n📊 Collection Statistics:")
                    for key, value in stats.items():
                        print(f"   {key}: {value}")
                    continue

                if query.lower().startswith("article "):
                    try:
                        article_id = query.split()[1]
                        chunks = search_client.get_article_by_id(
                            args.collection, article_id
                        )
                        output = format_article_content(chunks, article_id)
                        print(output)
                        continue
                    except (IndexError, ValueError):
                        print("❌ Usage: article <id>")
                        continue

                if query.lower() == "history":
                    if query_history:
                        print("\n📜 Query History:")
                        for i, hist_query in enumerate(query_history[-10:], 1):
                            print(f"   {i}. {hist_query}")
                    else:
                        print("No search history yet.")
                    continue

                # Add to history
                query_history.append(query)

                # Perform search
                args.query = query
                perform_search(args, embedding_client)

            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except EOFError:
                print("\n👋 Goodbye!")
                break

    finally:
        qdrant_client.close()


def main():
    """Main CLI entry point."""
    # Load configuration
    config = get_config()
    setup_logging(config.logging)

    parser = argparse.ArgumentParser(
        description="Query Qdrant vector database with semantic search",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "machine learning algorithms"
  %(prog)s "what is neural network" --hybrid --limit 5
  %(prog)s --interactive --collection docs
  %(prog)s --article-id 123 --collection articles
  %(prog)s "deep learning" --output-format json --output results.json

Supported output formats: detailed, compact, json
    """,
    )

    # Main operation mode
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument("query", nargs="?", help="Search query text")
    operation.add_argument(
        "--interactive", "-i", action="store_true", help="Start interactive search mode"
    )
    operation.add_argument(
        "--article-id", type=int, help="Show full content of specific article by ID"
    )

    # Connection settings
    parser.add_argument(
        "--qdrant-url",
        default=config.database.url,
        help=f"Qdrant server URL (default: {config.database.url})",
    )
    parser.add_argument(
        "--ollama-url",
        default=config.embedding.url,
        help=f"Ollama API URL (default: {config.embedding.url})",
    )
    parser.add_argument(
        "--collection",
        "-c",
        default="docs",
        help="Collection name to search (default: docs)",
    )

    # Search parameters
    parser.add_argument(
        "--model",
        "-m",
        default=config.embedding.model,
        help=f"Embedding model to use (default: {config.embedding.model})",
    )
    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=config.search.default_limit,
        help=f"Maximum number of results (default: {config.search.default_limit})",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=config.search.min_score,
        help=f"Minimum similarity score (default: {config.search.min_score})",
    )

    # Search type
    parser.add_argument(
        "--hybrid",
        action="store_true",
        default=config.search.enable_hybrid_search,
        help="Use hybrid search (vector + keyword matching)",
    )
    parser.add_argument(
        "--fusion-method",
        choices=["rrf", "dbsf"],
        default=config.search.fusion_method,
        help=f"Fusion method for hybrid search (default: {config.search.fusion_method})",
    )
    parser.add_argument(
        "--task-type",
        default="search",
        help="Task type for query formatting (default: search)",
    )

    # Output options
    parser.add_argument(
        "--output-format",
        choices=["detailed", "compact", "json"],
        default="detailed",
        help="Output format (default: detailed)",
    )
    parser.add_argument(
        "--group-by-article", action="store_true", help="Group results by article"
    )
    parser.add_argument("--output-file", "-o", help="Save results to file")

    # Utility options
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show collection statistics before searching",
    )
    parser.add_argument(
        "--connection-timeout",
        type=int,
        default=config.embedding.timeout,
        help=f"Connection timeout in seconds (default: {config.embedding.timeout})",
    )
    parser.add_argument("--config-file", help="Path to configuration file")

    args = parser.parse_args()

    # Load config from file if specified
    if args.config_file:
        config = get_config(args.config_file)

    # Validate arguments
    if not args.query and not args.interactive and args.article_id is None:
        parser.error("Must provide query, --interactive, or --article-id")

    try:
        if args.interactive:
            interactive_mode(args)
        elif args.article_id is not None:
            qdrant_client = QdrantClient(url=args.qdrant_url, timeout=60.0)
            search_client = QdrantSearchClient(qdrant_client)
            try:
                show_article(args, search_client)
            finally:
                qdrant_client.close()
        else:
            embedding_client = OllamaEmbeddingClient(
                args.ollama_url, timeout=args.connection_timeout
            )
            perform_search(args, embedding_client)

    except KeyboardInterrupt:
        print("\n👋 Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
