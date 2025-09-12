#!/usr/bin/env python3
"""
RAG Chat CLI for the Qdrant RAG system.

This script provides a command-line chat interface that combines semantic search
with LLM generation for context-aware responses using the shared library.
"""

import argparse
import json
import sys
import time
from typing import List, Optional, Dict, Any, Generator

from qdrant_client import QdrantClient

# Import from shared library (use PYTHONPATH environment variable)
from lib.embedding.client import OllamaEmbeddingClient, create_session
from lib.embedding.formatter import format_query
from lib.qdrant.search import QdrantSearchClient
from lib.utils.config import get_config, setup_logging


class RAGChatClient:
    """RAG Chat client combining search and generation."""

    def __init__(
        self,
        qdrant_url: str,
        ollama_url: str,
        collection_name: str,
        embedding_model: str,
        chat_model: str,
        timeout: int = 120,
    ):
        """Initialize the RAG chat client."""
        self.qdrant_url = qdrant_url
        self.ollama_url = ollama_url.rstrip("/")
        self.collection_name = collection_name
        self.embedding_model = embedding_model
        self.chat_model = chat_model
        self.timeout = timeout

        # Initialize clients
        self.qdrant_client = QdrantClient(url=qdrant_url, timeout=60.0)
        self.search_client = QdrantSearchClient(self.qdrant_client)
        self.embedding_client = OllamaEmbeddingClient(ollama_url, timeout)
        self.session = create_session()

        # Chat history
        self.conversation_history = []

    def search_context(
        self,
        query: str,
        limit: int = 5,
        min_score: float = 0.4,
        use_hybrid: bool = True,
    ) -> List[Dict[str, Any]]:
        """Search for relevant context using the query."""
        try:
            # Format query for embedding
            formatted_query = format_query(query, self.embedding_model, "search")
            print(f"🔍 Formatted query: {formatted_query}")

            # Generate query embedding
            query_vector = self.embedding_client.embed_text(
                formatted_query, self.embedding_model
            )

            # Perform search
            if use_hybrid:
                results = self.search_client.hybrid_search(
                    collection_name=self.collection_name,
                    query_text=query,
                    query_vector=query_vector,
                    limit=limit,
                    min_score=min_score,
                )
            else:
                results = self.search_client.simple_search(
                    collection_name=self.collection_name,
                    query_vector=query_vector,
                    limit=limit,
                    min_score=min_score,
                )

            return results

        except Exception as e:
            print(f"⚠️ Search failed: {e}")
            return []

    def format_context(self, search_results: List[Dict[str, Any]]) -> str:
        """Format search results into context for the LLM."""
        if not search_results:
            return "No relevant context found in the knowledge base."

        context_parts = []
        context_parts.append("Here is relevant information from the knowledge base:\n")

        for i, result in enumerate(search_results, 1):
            payload = result["payload"]
            title = payload.get("title", "Untitled")
            content = payload.get("content", "")
            score = result["score"]

            context_parts.append(f"[Source {i}] {title} (Relevance: {score:.3f})")
            context_parts.append(content)
            context_parts.append("")  # Empty line between sources

        return "\n".join(context_parts)

    def generate_response(
        self,
        query: str,
        context: str,
        system_prompt: Optional[str] = None,
        stream: bool = True,
    ) -> Generator[str, None, None]:
        """Generate response using LLM with context."""
        # Default system prompt
        if system_prompt is None:
            system_prompt = """You are a helpful AI assistant that answers questions based on the provided context. 
Use the information from the knowledge base to provide accurate, helpful responses. 
If the context doesn't contain enough information to answer the question, say so clearly.
Keep your responses concise and relevant."""

        # Construct the prompt
        messages = [{"role": "system", "content": system_prompt}]

        # Add conversation history
        for msg in self.conversation_history[-6:]:  # Keep last 6 messages for context
            messages.append(msg)

        # Add current query with context
        user_message = f"Context:\n{context}\n\nQuestion: {query}"
        messages.append({"role": "user", "content": user_message})

        # Prepare API request
        payload = {
            "model": self.chat_model,
            "messages": messages,
            "stream": stream,
            "options": {
                "temperature": 0.6,
                "top_p": 0.9,
            },
        }

        try:
            response = self.session.post(
                f"{self.ollama_url}/api/chat",
                json=payload,
                timeout=self.timeout,
                stream=stream,
            )
            response.raise_for_status()

            if stream:
                # Stream response
                full_response = ""
                for line in response.iter_lines():
                    if line:
                        try:
                            data = json.loads(line.decode("utf-8"))
                            if "message" in data and "content" in data["message"]:
                                chunk = data["message"]["content"]
                                full_response += chunk
                                yield chunk

                            if data.get("done", False):
                                break
                        except json.JSONDecodeError:
                            continue

                # Add to conversation history
                self.conversation_history.append({"role": "user", "content": query})
                self.conversation_history.append(
                    {"role": "assistant", "content": full_response}
                )
            else:
                # Non-streaming response
                data = response.json()
                if "message" in data and "content" in data["message"]:
                    response_text = data["message"]["content"]
                    self.conversation_history.append({"role": "user", "content": query})
                    self.conversation_history.append(
                        {"role": "assistant", "content": response_text}
                    )
                    yield response_text

        except Exception as e:
            yield f"❌ Error generating response: {e}"

    def chat(
        self,
        query: str,
        search_limit: int = 5,
        min_score: float = 0.4,
        use_hybrid: bool = True,
        system_prompt: Optional[str] = None,
        stream: bool = True,
        show_sources: bool = True,
    ) -> None:
        """Perform a complete RAG chat interaction."""
        print(f"\n🤖 Processing: {query}")

        # Search for context
        print("🔍 Searching for relevant context...")
        search_start = time.time()

        search_results = self.search_context(
            query,
            limit=search_limit,
            min_score=min_score,
            use_hybrid=use_hybrid,
        )

        search_time = (time.time() - search_start) * 1000
        print(f"✅ Found {len(search_results)} relevant sources in {search_time:.1f}ms")

        # Show sources if requested
        if show_sources and search_results:
            print("\n📚 Sources:")
            for i, result in enumerate(search_results, 1):
                payload = result["payload"]
                title = payload.get("title", "Untitled")
                score = result["score"]
                article_id = payload.get("article_id", "Unknown")
                print(f"  {i}. {title} (Score: {score:.3f}, ID: {article_id})")

        # Format context
        context = self.format_context(search_results)

        # Generate response
        print(f"\n💭 Generating response with {self.chat_model}...\n")

        response_start = time.time()
        if stream:
            print("📝 ", end="", flush=True)
            for chunk in self.generate_response(
                query, context, system_prompt, stream=True
            ):
                print(chunk, end="", flush=True)
            print()  # New line after streaming
        else:
            for response in self.generate_response(
                query, context, system_prompt, stream=False
            ):
                print(f"📝 {response}")

        response_time = (time.time() - response_start) * 1000
        print(f"\n⏱️ Response generated in {response_time:.1f}ms")

    def close(self):
        """Close all connections."""
        self.qdrant_client.close()
        self.session.close()


def interactive_chat(args) -> None:
    """Run interactive chat mode."""
    config = get_config(args.config_file) if args.config_file else get_config()

    # Initialize RAG client
    chat_client = RAGChatClient(
        qdrant_url=args.qdrant_url,
        ollama_url=args.ollama_url,
        collection_name=args.collection,
        embedding_model=args.embedding_model,
        chat_model=args.chat_model,
        timeout=args.timeout,
    )

    print("🎯 RAG Chat Mode")
    print("=" * 50)
    print(f"📦 Collection: {args.collection}")
    print(f"🔍 Embedding Model: {args.embedding_model}")
    print(f"💬 Chat Model: {args.chat_model}")
    print(f"🔎 Search Type: {'Hybrid' if args.hybrid else 'Vector'}")
    print(f"📊 Max Sources: {args.search_limit}")
    print("=" * 50)
    print("Type 'quit', 'exit', or 'q' to exit")
    print("Type 'help' for commands")
    print("Type 'clear' to clear conversation history")
    print("Type 'sources on/off' to toggle source display")

    show_sources = args.show_sources

    try:
        while True:
            try:
                query = input("\n💬 You: ").strip()

                if not query:
                    continue

                if query.lower() in ["quit", "exit", "q"]:
                    print("👋 Goodbye!")
                    break

                if query.lower() == "help":
                    print("\nAvailable commands:")
                    print("  help            - Show this help message")
                    print("  clear           - Clear conversation history")
                    print("  sources on/off  - Toggle source display")
                    print("  quit/exit/q     - Exit chat mode")
                    print("\nSettings:")
                    print(f"  Collection: {args.collection}")
                    print(f"  Search limit: {args.search_limit}")
                    print(f"  Min score: {args.min_score}")
                    print(f"  Search type: {'Hybrid' if args.hybrid else 'Vector'}")
                    continue

                if query.lower() == "clear":
                    chat_client.conversation_history.clear()
                    print("🗑️ Conversation history cleared")
                    continue

                if query.lower().startswith("sources "):
                    setting = query.split()[1].lower()
                    if setting == "on":
                        show_sources = True
                        print("✅ Source display enabled")
                    elif setting == "off":
                        show_sources = False
                        print("❌ Source display disabled")
                    else:
                        print("Usage: sources on/off")
                    continue

                # Perform RAG chat
                chat_client.chat(
                    query=query,
                    search_limit=args.search_limit,
                    min_score=args.min_score,
                    use_hybrid=args.hybrid,
                    system_prompt=args.system_prompt,
                    stream=not args.no_stream,
                    show_sources=show_sources,
                )

            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except EOFError:
                print("\n👋 Goodbye!")
                break

    finally:
        chat_client.close()


def single_query(args) -> None:
    """Process a single query and exit."""
    config = get_config(args.config_file) if args.config_file else get_config()

    # Initialize RAG client
    chat_client = RAGChatClient(
        qdrant_url=args.qdrant_url,
        ollama_url=args.ollama_url,
        collection_name=args.collection,
        embedding_model=args.embedding_model,
        chat_model=args.chat_model,
        timeout=args.timeout,
    )

    try:
        chat_client.chat(
            query=args.query,
            search_limit=args.search_limit,
            min_score=args.min_score,
            use_hybrid=args.hybrid,
            system_prompt=args.system_prompt,
            stream=not args.no_stream,
            show_sources=args.show_sources,
        )
    finally:
        chat_client.close()


def main():
    """Main CLI entry point."""
    # Load configuration
    config = get_config()

    parser = argparse.ArgumentParser(
        description="RAG Chat with Qdrant vector search and LLM generation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --interactive
  %(prog)s "What is machine learning?" --chat-model llama3
  %(prog)s --interactive --collection docs --hybrid
  %(prog)s "Explain neural networks" --search-limit 3 --show-sources

The chat system combines semantic search with LLM generation to provide
context-aware responses based on your indexed documents.
    """,
    )

    # Main operation mode
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument(
        "query", nargs="?", help="Single query to process (non-interactive mode)"
    )
    operation.add_argument(
        "--interactive", "-i", action="store_true", help="Start interactive chat mode"
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

    # Model settings
    parser.add_argument(
        "--embedding-model",
        default=config.embedding.model,
        help=f"Embedding model for search (default: {config.embedding.model})",
    )
    parser.add_argument(
        "--chat-model",
        default="llama3",
        help="Chat/LLM model for generation (default: llama3)",
    )

    # Search parameters
    parser.add_argument(
        "--search-limit",
        type=int,
        default=5,
        help="Maximum number of sources to retrieve (default: 5)",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=0.4,
        help="Minimum similarity score for search results (default: 0.4)",
    )
    parser.add_argument(
        "--hybrid",
        action="store_true",
        default=config.search.enable_hybrid_search,
        help="Use hybrid search (vector + keyword matching)",
    )

    # Generation parameters
    parser.add_argument("--system-prompt", help="Custom system prompt for the LLM")
    parser.add_argument(
        "--no-stream", action="store_true", help="Disable streaming responses"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=config.embedding.timeout,
        help=f"Request timeout in seconds (default: {config.embedding.timeout})",
    )

    # Display options
    parser.add_argument(
        "--show-sources",
        action="store_true",
        default=True,
        help="Show source information (default: True)",
    )
    parser.add_argument(
        "--no-sources", action="store_true", help="Don't show source information"
    )

    # Configuration
    parser.add_argument("--config-file", help="Path to configuration file")

    args = parser.parse_args()

    # Handle conflicting source options
    if args.no_sources:
        args.show_sources = False

    # Setup logging
    setup_logging()

    # Validate arguments
    if not args.query and not args.interactive:
        parser.error("Must provide a query or use --interactive mode")

    try:
        if args.interactive:
            interactive_chat(args)
        else:
            single_query(args)

    except KeyboardInterrupt:
        print("\n👋 Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
