#!/usr/bin/env python3
"""
RAG Chat System using Qdrant vector database and LLM.
Combines semantic search with LLM generation for context-aware responses.
"""

import argparse
import json
import sys
import time
from typing import List, Optional, Dict, Any, Generator
from datetime import datetime

import requests
from qdrant_client import QdrantClient, models
from qdrant_client.models import Filter, FieldCondition, MatchText


def embed_one_ollama(text: str, model: str, ollama_url: str, timeout: int = 120, session: Optional[requests.Session] = None) -> List[float]:
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
                if "embedding" in data and isinstance(data["embedding"], list) and len(data["embedding"]) > 0:
                    return data["embedding"]
                if "embeddings" in data and isinstance(data["embeddings"], list) and data["embeddings"] and len(data["embeddings"][0]) > 0:
                    return data["embeddings"][0]
            last_err = f"Unexpected response: {data}"
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
    raise RuntimeError(f"Ollama embedding failed. Last error: {last_err}")


def create_session() -> requests.Session:
    """Create a reusable HTTP session with connection pooling."""
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(
        pool_connections=10,
        pool_maxsize=20,
        max_retries=3
    )
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session


def search_qdrant_hybrid(
    client: QdrantClient,
    collection_name: str,
    query_text: str,
    query_vector: List[float],
    limit: int = 5,
    min_score: float = 0.0
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
                limit=limit * 2  # Get more candidates for fusion
            )
        )
        
        # 2. Title keyword matching
        if query_text.strip():
            prefetch_queries.append(
                models.Prefetch(
                    query=query_vector,
                    limit=limit * 2,
                    filter=Filter(must=[
                        FieldCondition(
                            key="title",
                            match=MatchText(text=query_text)
                        )
                    ])
                )
            )
        
        # 3. Content keyword matching
        if query_text.strip():
            prefetch_queries.append(
                models.Prefetch(
                    query=query_vector,
                    limit=limit * 2,
                    filter=Filter(must=[
                        FieldCondition(
                            key="content",
                            match=MatchText(text=query_text)
                        )
                    ])
                )
            )
        
        # Execute hybrid query with RRF fusion
        results = client.query_points(
            collection_name=collection_name,
            prefetch=prefetch_queries,
            query=models.FusionQuery(fusion=models.Fusion.DBSF),
            limit=limit,
            with_payload=True,
            score_threshold=min_score if min_score > 0 else None
        )
        
        return [
            {
                "id": result.id,
                "score": result.score,
                "payload": result.payload or {}
            }
            for result in results.points
        ]
        
    except Exception as e:
        # Fallback to simple vector search if hybrid fails
        print(f"⚠️ Hybrid search failed, falling back to simple search: {e}")
        
        search_params = {
            "collection_name": collection_name,
            "query_vector": query_vector,
            "limit": limit,
            "with_payload": True,
            "score_threshold": min_score if min_score > 0 else None
        }
        
        results = client.search(**search_params)
        return [
            {
                "id": result.id,
                "score": result.score,
                "payload": result.payload or {}
            }
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
    session: Optional[requests.Session] = None
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
        "stream": stream
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
    session: Optional[requests.Session] = None
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
        "stream": True
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
    query: str,
    context_chunks: List[Dict[str, Any]],
    max_context_length: int = 3000
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
        
        sources.append({
            "index": i,
            "title": title,
            "article_id": article_id,
            "chunk_index": chunk_index,
            "score": score
        })
    
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


def format_sources(sources: List[Dict[str, Any]]) -> str:
    """Format source citations for display."""
    if not sources:
        return ""
    
    output = ["\n📚 Sources:"]
    for source in sources:
        output.append(
            f"  [{source['index']}] {source['title']} "
            f"(Article {source['article_id']}, Chunk {source['chunk_index']}, "
            f"Score: {source['score']:.3f})"
        )
    
    return "\n".join(output)


def chat_with_rag(
    query: str,
    client: QdrantClient,
    session: requests.Session,
    args: argparse.Namespace
) -> tuple[str, List[Dict[str, Any]]]:
    """
    Main RAG pipeline: search, augment, generate.
    
    Args:
        query: User query
        client: Qdrant client
        session: HTTP session
        args: Command-line arguments
    
    Returns:
        Tuple of (response text, source citations)
    """
    # Step 1: Generate query embedding
    print("🔍 Searching for relevant context...")
    query_vector = embed_one_ollama(
        query,
        args.embedding_model,
        args.ollama_url,
        session=session
    )
    
    # Step 2: Search Qdrant for relevant context
    context_chunks = search_qdrant_hybrid(
        client,
        args.collection,
        query,
        query_vector,
        limit=args.top_k,
        min_score=args.min_score
    )
    
    if not context_chunks:
        return "I couldn't find any relevant information to answer your question.", []
    
    print(f"📖 Found {len(context_chunks)} relevant context chunks")
    
    # Step 3: Build augmented prompt
    augmented_prompt, sources = build_rag_prompt(
        query,
        context_chunks,
        max_context_length=args.max_context_length
    )
    
    # Step 4: Generate response with LLM
    print("🤖 Generating response...")
    
    if args.stream:
        # Stream the response
        response_parts = []
        for chunk in stream_llm_response(
            augmented_prompt,
            args.llm_model,
            args.ollama_url,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            system_prompt=args.system_prompt,
            session=session
        ):
            print(chunk, end="", flush=True)
            response_parts.append(chunk)
        print()  # New line after streaming
        response = "".join(response_parts)
    else:
        response = generate_llm_response(
            augmented_prompt,
            args.llm_model,
            args.ollama_url,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            system_prompt=args.system_prompt,
            session=session
        )
    
    return response, sources


def interactive_chat(args: argparse.Namespace) -> None:
    """Run interactive RAG chat mode."""
    session = create_session()
    client = QdrantClient(url=args.qdrant_url, timeout=60.0)
    
    print("\n🤖 RAG Chat Mode (Powered by Qdrant + Ollama)")
    print("=" * 50)
    print("Type 'help' for commands or 'quit' to exit")
    print(f"Model: {args.llm_model} | Collection: {args.collection}")
    print(f"Context: Top {args.top_k} chunks | Temperature: {args.temperature}")
    print("-" * 50)
    
    conversation_history = []
    
    try:
        while True:
            try:
                # Get user input
                query = input("\n💬 You: ").strip()
                
                if not query:
                    continue
                
                # Handle commands
                if query.lower() in ['quit', 'exit', 'q']:
                    print("\n👋 Goodbye!")
                    break
                
                if query.lower() == 'help':
                    print("\n📋 Available commands:")
                    print("  help        - Show this help")
                    print("  clear       - Clear conversation history")
                    print("  sources     - Show sources from last response")
                    print("  settings    - Show current settings")
                    print("  save        - Save conversation to file")
                    print("  quit/exit/q - Exit chat")
                    continue
                
                if query.lower() == 'clear':
                    conversation_history = []
                    print("🗑️ Conversation history cleared")
                    continue
                
                if query.lower() == 'settings':
                    print("\n⚙️ Current Settings:")
                    print(f"  LLM Model: {args.llm_model}")
                    print(f"  Embedding Model: {args.embedding_model}")
                    print(f"  Collection: {args.collection}")
                    print(f"  Top-K Context: {args.top_k}")
                    print(f"  Temperature: {args.temperature}")
                    print(f"  Max Tokens: {args.max_tokens}")
                    print(f"  Min Score: {args.min_score}")
                    print(f"  Streaming: {args.stream}")
                    continue
                
                if query.lower() == 'sources':
                    if conversation_history and 'sources' in conversation_history[-1]:
                        sources = conversation_history[-1]['sources']
                        print(format_sources(sources))
                    else:
                        print("No sources available from last response")
                    continue
                
                if query.lower() == 'save':
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"chat_history_{timestamp}.json"
                    with open(filename, 'w', encoding='utf-8') as f:
                        json.dump(conversation_history, f, indent=2, ensure_ascii=False)
                    print(f"💾 Conversation saved to {filename}")
                    continue
                
                # Process the query with RAG
                print("\n🤖 Assistant: ", end="")
                start_time = time.time()
                
                response, sources = chat_with_rag(query, client, session, args)
                
                elapsed_time = time.time() - start_time
                
                # If not streaming, print the response
                if not args.stream:
                    print(response)
                
                # Show sources if requested
                if args.show_sources and sources:
                    print(format_sources(sources))
                
                print(f"\n⏱️ Response time: {elapsed_time:.2f}s")
                
                # Add to conversation history
                conversation_history.append({
                    "query": query,
                    "response": response,
                    "sources": sources,
                    "timestamp": datetime.now().isoformat()
                })
                
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
                continue
    
    finally:
        client.close()
        session.close()


def main():
    parser = argparse.ArgumentParser(
        description="RAG Chat System using Qdrant vector database and Ollama LLM",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic RAG chat with default settings
  python chat_rag.py
  
  # Use specific LLM model
  python chat_rag.py --llm-model llama2 --embedding-model mxbai-embed-large
  
  # Adjust RAG parameters
  python chat_rag.py --top-k 5 --temperature 0.5 --max-tokens 1000
  
  # Show sources and use streaming
  python chat_rag.py --show-sources --stream
  
  # Custom system prompt
  python chat_rag.py --system-prompt "You are a helpful Islamic scholar assistant."
        """
    )
    
    # Connection arguments
    parser.add_argument("--qdrant-url", default="http://localhost:6333", 
                       help="Qdrant server URL")
    parser.add_argument("--ollama-url", default="http://localhost:11434", 
                       help="Ollama server URL")
    parser.add_argument("--collection", default="articles", 
                       help="Qdrant collection name")
    
    # Model arguments
    parser.add_argument("--llm-model", default="llama2", 
                       help="Ollama LLM model for generation")
    parser.add_argument("--embedding-model", default="embeddinggemma:latest", 
                       help="Ollama model for embeddings")
    
    # RAG parameters
    parser.add_argument("--top-k", type=int, default=5, 
                       help="Number of context chunks to retrieve")
    parser.add_argument("--min-score", type=float, default=0.5, 
                       help="Minimum similarity score for context retrieval")
    parser.add_argument("--max-context-length", type=int, default=3000, 
                       help="Maximum context length in characters")
    
    # LLM parameters
    parser.add_argument("--temperature", type=float, default=0.7, 
                       help="LLM sampling temperature (0.0-1.0)")
    parser.add_argument("--max-tokens", type=int, default=2000, 
                       help="Maximum tokens in LLM response")
    parser.add_argument("--system-prompt", type=str, 
                       help="System prompt for the LLM")
    
    # Display options
    parser.add_argument("--stream", action="store_true", 
                       help="Stream LLM responses")
    parser.add_argument("--show-sources", action="store_true", 
                       help="Show source citations with responses")
    
    # Utility options
    parser.add_argument("--timeout", type=int, default=120, 
                       help="HTTP timeout in seconds")
    
    args = parser.parse_args()
    
    print("🎯 Starting RAG Chat System")
    print("=" * 50)
    
    # Set default system prompt if not provided
    if not args.system_prompt:
        args.system_prompt = (
            "You are a helpful assistant that answers questions based on the provided context. "
            "Always be accurate and cite information from the context when possible. "
            "If the context doesn't contain relevant information, say so clearly."
        )
    
    try:
        interactive_chat(args)
    except Exception as e:
        print(f"❌ Fatal error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
