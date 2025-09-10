#!/usr/bin/env python3
import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Optional, Dict

import requests
from qdrant_client import QdrantClient, models
from qdrant_client.models import Distance, VectorParams, PointStruct
from snowflake_utils import get_snowflake_id


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

    text = text.lower().strip()

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


def embed_batch_concurrent(
    texts: List[str],
    model: str,
    ollama_url: str,
    max_workers: int = 4,
    timeout: int = 120,
) -> List[List[float]]:
    """Generate embeddings for multiple texts concurrently."""
    session = create_session()
    results = [None] * len(texts)  # Pre-allocate results list

    def embed_single(index_text_pair):
        index, text = index_text_pair
        try:
            embedding = embed_one_ollama(text, model, ollama_url, timeout, session)
            return index, embedding
        except Exception as e:
            raise RuntimeError(f"Failed to embed text at index {index}: {e}")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_index = {
            executor.submit(embed_single, (i, text)): i for i, text in enumerate(texts)
        }

        # Collect results
        for future in as_completed(future_to_index):
            try:
                index, embedding = future.result()
                results[index] = embedding
            except Exception as e:
                session.close()
                raise e

    session.close()
    return results


def chunk_text(text: str, chunk_size: int = 150, overlap: int = 30) -> List[str]:
    """
    Split text into chunks with overlap.

    Args:
        text: The text to chunk
        chunk_size: Number of words per chunk (default 150 words)
        overlap: Number of words to overlap between chunks (default 30 words = 20% of 150)

    Returns:
        List of text chunks
    """
    if not text:
        return []

    # Split text into words
    words = text.split()

    if len(words) <= chunk_size:
        return [text]

    chunks = []
    start = 0

    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk = " ".join(words[start:end])
        chunks.append(chunk)

        # Move forward by (chunk_size - overlap) words
        if end >= len(words):
            break
        start += chunk_size - overlap

    return chunks


def create_chunk_objects(
    article: Dict,
    chunk_size: int = 150,
    chunk_overlap: int = 30,
    max_chunks_per_article: int = 10,
) -> List[Dict]:
    """
    Create chunk objects from an article.

    Args:
        article: Article dictionary with id, title and content
        chunk_size: Number of words per chunk
        chunk_overlap: Number of overlapping words between chunks
        max_chunks_per_article: Maximum number of chunks per article (to avoid very long articles)

    Returns:
        List of chunk objects ready for indexing
    """
    content = article.get("content", "")
    title = article.get("title", "")
    article_id = article.get("id")

    chunks = chunk_text(content, chunk_size, chunk_overlap)

    # Limit chunks per article to avoid overwhelming the index
    chunks = chunks[:max_chunks_per_article]

    chunk_objects = []
    for i, chunk in enumerate(chunks):
        # Include title in each chunk for better context
        # Format: "Title: [article title]\n\n[chunk content]"
        chunk_with_title = f"# {title}\n\n{chunk}"

        # Generate unique Snowflake ID for each chunk
        chunk_id = get_snowflake_id()

        chunk_objects.append(
            {
                "chunk_id": chunk_id,
                "article_id": article_id,
                "chunk_index": i,
                "title": title,
                "content": chunk,
                "text": chunk_with_title,  # Combined text for embedding
                "source": article.get("source", "unknown"),
            }
        )

    return chunk_objects


def read_markdown_files(
    directory_path: str, max_docs: Optional[int] = None
) -> List[Dict]:
    """
    Read and parse markdown files from a directory.

    Args:
        directory_path: Path to directory containing markdown files
        max_docs: Maximum number of documents to process

    Returns:
        List of document dictionaries with id, title, and content
    """
    documents = []
    directory = Path(directory_path)

    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory_path}")

    if not directory.is_dir():
        raise ValueError(f"Path is not a directory: {directory_path}")

    # Find all markdown files recursively
    md_files = sorted(directory.rglob("*.md"))

    if not md_files:
        raise ValueError(f"No markdown files found in: {directory_path}")

    print(f"Found {len(md_files)} markdown files in {directory_path}")

    if max_docs:
        md_files = md_files[:max_docs]
        print(f"Limited to {len(md_files)} files (--max-docs {max_docs})")

    for idx, md_file in enumerate(md_files):
        try:
            # Read file content
            with open(md_file, "r", encoding="utf-8") as f:
                content = f.read()

            if not content.strip():
                print(f"Skipping empty file: {md_file}")
                continue

            # Extract title from first H1 heading or use filename
            title = extract_title_from_markdown(content)
            if not title:
                # Use filename without extension as title
                # Keep original casing and just replace underscores/hyphens with spaces
                title = md_file.stem.replace("_", " ").replace("-", " ")

            # Create document with unique ID based on file index
            doc = {
                "id": idx + 1,  # Start from 1
                "title": title,
                "content": content,
                "file_path": str(md_file.relative_to(directory)),
                "category": md_file.parent.name
                if md_file.parent != directory
                else "root",
            }

            documents.append(doc)

            if (idx + 1) % 10 == 0:
                print(f"Processed {idx + 1}/{len(md_files)} files")

        except Exception as e:
            print(f"Error reading file {md_file}: {e}")
            continue

    print(f"Successfully loaded {len(documents)} markdown documents")
    return documents


def extract_title_from_markdown(content: str) -> Optional[str]:
    """
    Extract title from markdown content.
    Looks for the first H1 heading (# Title) or underlined title.

    Args:
        content: Markdown content

    Returns:
        Title string or None if not found
    """
    lines = content.split("\n")

    # Check for H1 heading (# Title)
    for line in lines:
        line = line.strip()
        if line.startswith("# ") and len(line) > 2:
            # Found H1 heading
            return line[2:].strip()

    # Check for underlined title (Title\n=====)
    for i, line in enumerate(lines[:-1]):
        next_line = lines[i + 1].strip()
        if next_line and all(c == "=" for c in next_line) and len(next_line) >= 3:
            # Previous line is likely a title
            if line.strip():
                return line.strip()

    return None


def read_json_files(directory_path: str, max_docs: Optional[int] = None) -> List[Dict]:
    """
    Read and parse JSON files from a directory.

    Args:
        directory_path: Path to directory containing JSON files
        max_docs: Maximum number of documents to process

    Returns:
        List of document dictionaries with id, title, and content
    """
    documents = []
    directory = Path(directory_path)

    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory_path}")

    if not directory.is_dir():
        raise ValueError(f"Path is not a directory: {directory_path}")

    # Find all JSON files recursively
    json_files = sorted(directory.rglob("*.json"))

    if not json_files:
        raise ValueError(f"No JSON files found in: {directory_path}")

    print(f"Found {len(json_files)} JSON files in {directory_path}")

    if max_docs:
        # When max_docs is specified, we need to be careful since each JSON file
        # can contain multiple documents
        print(f"Will process up to {max_docs} documents total from JSON files")

    total_processed_files = 0

    for json_file in json_files:
        if max_docs and len(documents) >= max_docs:
            print(f"Reached maximum document limit ({max_docs}), stopping")
            break

        try:
            # Read JSON file content
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Handle both single objects and arrays
            if isinstance(data, dict):
                # Single JSON object
                json_documents = [data]
            elif isinstance(data, list):
                # Array of JSON objects
                json_documents = data
            else:
                print(
                    f"Skipping {json_file}: Invalid JSON structure (not object or array)"
                )
                continue

            file_doc_count = 0

            for item in json_documents:
                if max_docs and len(documents) >= max_docs:
                    break

                # Validate required fields
                if not isinstance(item, dict):
                    continue

                article_id = item.get("article_id") or item.get("id")
                title = item.get("title", "")
                content = item.get("content", "")

                if not article_id:
                    continue

                # Ensure article_id is integer for consistent indexing
                # try:
                #     article_id = int(article_id)
                # except (ValueError, TypeError):
                #     print(
                #         f"Warning: Invalid article_id '{article_id}' in {json_file}, skipping document"
                #     )
                #     continue

                if article_id is None:
                    print(
                        f"Warning: Missing article_id in {json_file}, skipping document"
                    )
                    continue

                if not content.strip():
                    continue

                # Convert to consistent document format
                doc = {
                    "id": article_id,
                    "title": title,
                    "content": content,
                    "file_path": str(json_file.relative_to(directory)),
                    "category": json_file.parent.name
                    if json_file.parent != directory
                    else "root",
                }

                documents.append(doc)
                file_doc_count += 1

            total_processed_files += 1

            if file_doc_count > 0:
                if total_processed_files % 5 == 0 or total_processed_files == 1:
                    print(
                        f"Processed {total_processed_files}/{len(json_files)} files, {len(documents)} documents so far"
                    )

        except json.JSONDecodeError as e:
            print(f"Error parsing JSON file {json_file}: {e}")
            continue
        except Exception as e:
            print(f"Error reading file {json_file}: {e}")
            continue

    print(
        f"Successfully loaded {len(documents)} documents from {total_processed_files} JSON files"
    )
    return documents


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qdrant-url", default="http://localhost:6333")
    ap.add_argument("--collection", default="articles")
    ap.add_argument("--ollama-url", default="http://localhost:11434")
    ap.add_argument("--model", default="embeddinggemma:latest")
    ap.add_argument(
        "--recreate", action="store_true", help="Recreate collection from scratch"
    )
    ap.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of chunks to process in each batch. (defult=100)",
    )
    ap.add_argument(
        "--max-docs",
        type=int,
        help="Maximum number of documents to index (useful for testing)",
    )
    ap.add_argument(
        "--chunk-size",
        type=int,
        default=150,
        help="Number of words per chunk. (default=150)",
    )
    ap.add_argument(
        "--chunk-overlap",
        type=int,
        default=30,
        help="Number of overlapping words between chunks. (default=30)",
    )
    ap.add_argument(
        "--max-chunks-per-article",
        type=int,
        default=10,
        help="Maximum number of chunks per article. (default=10)",
    )
    ap.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of concurrent embedding workers. (default=4)",
    )
    ap.add_argument(
        "--embedding-batch-size",
        type=int,
        default=20,
        help="Number of texts to embed concurrently in each batch. (default=20)",
    )
    ap.add_argument(
        "--quiet", action="store_true", help="Reduce verbose logging during processing"
    )
    ap.add_argument(
        "--connection-timeout",
        type=int,
        default=120,
        help="HTTP timeout for embedding requests (seconds). (default=120)",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Only scan and validate files without processing embeddings or uploading to Qdrant",
    )

    # Create mutually exclusive group for input source
    input_group = ap.add_mutually_exclusive_group()
    input_group.add_argument(
        "--json-file", default="articles_clean.json", help="Path to articles JSON file"
    )
    input_group.add_argument(
        "--scan-dir",
        help="Directory path to scan for markdown and JSON files (overrides --json-file)",
    )

    args = ap.parse_args()

    # In dry-run mode, skip Qdrant client connection
    if not args.dry_run:
        client = QdrantClient(url=args.qdrant_url, timeout=60.0)
    else:
        client = None

    try:
        dim = 1024
        if not args.dry_run:
            print(f"Connecting to Qdrant @ {args.qdrant_url} ...")

            # --- determine vector size first ---
            print("Getting embedding dimension from Ollama ...")
            probe_embedding = embed_one_ollama(
                "dimension probe", args.model, args.ollama_url
            )
            dim = len(probe_embedding)
            print(f"Embedding dimension = {dim}")
        else:
            print(
                "DRY RUN MODE: Skipping Qdrant connection and embedding dimension probe"
            )

        # --- (re)create collection in a version-compatible way ---
        if not args.dry_run:
            if client is None:
                raise RuntimeError("Qdrant client is not initialized")
            print(f"Preparing collection '{args.collection}' ...")
            if args.recreate:
                try:
                    client.delete_collection(args.collection)
                    print(f"Deleted existing collection '{args.collection}'")
                except Exception:
                    pass

            try:
                client.create_collection(
                    collection_name=args.collection,
                    vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
                )
                print(f"Created collection '{args.collection}'")
                index_params = models.TextIndexParams(
                    type=models.TextIndexType.TEXT,
                    tokenizer=models.TokenizerType.WORD,
                    lowercase=True,
                    phrase_matching=True,
                )
                # Create payload index for article_id to enable fast filtering operations.
                # This index is essential because article_id is frequently used for:
                # - Filtering search results to specific articles
                # - Retrieving all chunks belonging to an article
                # - Hybrid search operations that filter by article
                # Using KEYWORD type to handle both string and integer article_id values from JSON data
                client.create_payload_index(
                    collection_name=args.collection,
                    field_name="article_id",
                    field_type=models.PayloadSchemaType.KEYWORD,
                )
                client.create_payload_index(
                    collection_name=args.collection,
                    field_name="title",
                    field_type=models.PayloadSchemaType.TEXT,
                    field_schema=index_params,
                )
                client.create_payload_index(
                    collection_name=args.collection,
                    field_name="content",
                    field_type=models.PayloadSchemaType.TEXT,
                    field_schema=index_params,
                )
            except Exception as e:
                if "already exists" in str(e).lower():
                    print(
                        f"Collection '{args.collection}' already exists, continuing..."
                    )
                else:
                    raise
        else:
            print("DRY RUN MODE: Skipping collection preparation")

        # --- index articles as chunks in batches ---
        batch_points = []
        total_chunks_indexed = 0
        total_articles_processed = 0

        # Load articles from either JSON file or markdown/JSON directory
        if args.scan_dir:
            print(f"Scanning directory {args.scan_dir} for markdown and JSON files ...")
            articles = []

            try:
                directory = Path(args.scan_dir)
                if not directory.exists():
                    raise FileNotFoundError(f"Directory not found: {args.scan_dir}")
                if not directory.is_dir():
                    raise ValueError(f"Path is not a directory: {args.scan_dir}")

                # Find both markdown and JSON files
                md_files = sorted(directory.rglob("*.md"))
                json_files = sorted(directory.rglob("*.json"))

                print(
                    f"Found {len(md_files)} markdown files and {len(json_files)} JSON files"
                )

                # Read markdown files if present
                if md_files:
                    try:
                        print("Processing markdown files...")
                        md_articles = read_markdown_files(args.scan_dir, args.max_docs)
                        articles.extend(md_articles)
                        print(
                            f"Loaded {len(md_articles)} documents from markdown files"
                        )
                    except Exception as e:
                        print(f"Error reading markdown files: {e}")

                # Read JSON files if present and we haven't reached max_docs
                if json_files and (not args.max_docs or len(articles) < args.max_docs):
                    try:
                        print("Processing JSON files...")
                        remaining_docs = (
                            args.max_docs - len(articles) if args.max_docs else None
                        )
                        json_articles = read_json_files(args.scan_dir, remaining_docs)
                        articles.extend(json_articles)
                        print(f"Loaded {len(json_articles)} documents from JSON files")
                    except Exception as e:
                        print(f"Error reading JSON files: {e}")

                if not articles:
                    if not md_files and not json_files:
                        raise ValueError(
                            f"No markdown or JSON files found in: {args.scan_dir}"
                        )
                    else:
                        raise ValueError(
                            f"No valid documents could be loaded from: {args.scan_dir}"
                        )

                print(f"Total documents loaded: {len(articles)}")

            except (FileNotFoundError, ValueError) as e:
                print(f"Error scanning directory: {e}", file=sys.stderr)
                sys.exit(1)
            except Exception as e:
                print(f"Unexpected error scanning directory: {e}", file=sys.stderr)
                sys.exit(1)
        else:
            print(f"Reading articles from {args.json_file} ...")
            try:
                with open(args.json_file, "r", encoding="utf-8") as f:
                    articles = json.load(f)

                # Limit articles if max-docs is specified
                if args.max_docs:
                    articles = articles[: args.max_docs]
                    print(
                        f"Limited to {len(articles)} articles (--max-docs {args.max_docs})"
                    )
                else:
                    print(f"Found {len(articles)} articles to index")
            except FileNotFoundError:
                print(f"Error: JSON file not found: {args.json_file}", file=sys.stderr)
                sys.exit(1)
            except json.JSONDecodeError as e:
                print(
                    f"Error: Invalid JSON in file {args.json_file}: {e}",
                    file=sys.stderr,
                )
                sys.exit(1)

        print(
            f"Chunking settings: {args.chunk_size} words per chunk, {args.chunk_overlap} word overlap, max {args.max_chunks_per_article} chunks per article"
        )
        print(
            f"Performance settings: {args.workers} concurrent workers, {args.embedding_batch_size} texts per embedding batch"
        )

        # Exit early in dry-run mode after validating file loading
        if args.dry_run:
            print("\n=== DRY RUN COMPLETE ===")
            print(f"✓ Successfully validated {len(articles)} articles")
            print("✓ File scanning and parsing completed successfully")
            print("✓ All documents have required fields (id, title, content)")
            print("\nTo process these files, run again without --dry-run")
            return

        print("Phase 1: Creating chunks from articles...")
        all_chunks = []

        for i, article in enumerate(articles):
            if not args.quiet and ((i + 1) % 10 == 0 or i == 0):
                print(
                    f"Chunking article {i + 1}/{len(articles)} (ID: {article.get('id', 'unknown')}) - {article.get('title', '')}"
                )

            # Extract only the fields we need
            article_id = article.get("id")
            title = article.get("title", "")
            content = article.get("content", "")

            if not article_id:
                if not args.quiet:
                    print(f"Skipping article at index {i}: missing id")
                continue

            # Ensure article_id is integer for consistent indexing
            # try:
            #     article_id = int(article_id)
            # except (ValueError, TypeError):
            #     if not args.quiet:
            #         print(
            #             f"Skipping article at index {i}: invalid article_id '{article_id}'"
            #         )
            #     continue

            if not content:
                if not args.quiet:
                    print(f"Skipping article {article_id}: empty content")
                continue

            try:
                # Create chunks for this article
                chunk_objects = create_chunk_objects(
                    article,
                    chunk_size=args.chunk_size,
                    chunk_overlap=args.chunk_overlap,
                    max_chunks_per_article=args.max_chunks_per_article,
                )

                all_chunks.extend(chunk_objects)
                total_articles_processed += 1

                # if not args.quiet:
                #     print(f"  → Created {len(chunk_objects)} chunks for article {article_id}")

            except Exception as e:
                print(f"Error processing article {article_id}: {e}")
                continue

        print(
            f"✓ Created {len(all_chunks)} chunks from {total_articles_processed} articles"
        )

        # Phase 2: Generate embeddings in concurrent batches
        print("Phase 2: Generating embeddings concurrently...")

        # Process chunks in batches for embedding
        embedding_batch_size = args.embedding_batch_size
        total_chunks_indexed = 0

        for batch_start in range(0, len(all_chunks), embedding_batch_size):
            batch_end = min(batch_start + embedding_batch_size, len(all_chunks))
            chunk_batch = all_chunks[batch_start:batch_end]

            print(
                f"Embedding batch {batch_start // embedding_batch_size + 1}/{(len(all_chunks) + embedding_batch_size - 1) // embedding_batch_size}: processing {len(chunk_batch)} chunks..."
            )

            # Extract texts to embed
            texts_to_embed = [chunk_obj["text"] for chunk_obj in chunk_batch]
            # print("texts_to_embed:", texts_to_embed, "\n\n")  # Debugging line

            try:
                # Get embeddings concurrently
                batch_start_time = time.time()
                embeddings = embed_batch_concurrent(
                    texts_to_embed,
                    args.model,
                    args.ollama_url,
                    max_workers=args.workers,
                    timeout=args.connection_timeout,
                )
                embed_time = time.time() - batch_start_time

                # Create points for this embedding batch
                for chunk_obj, embedding in zip(chunk_batch, embeddings):
                    if len(embedding) != dim:
                        raise ValueError(
                            f"Embedding dimension changed: got {len(embedding)} vs expected {dim}"
                        )

                    # Create point with chunk-specific ID and payload
                    point = PointStruct(
                        id=chunk_obj["chunk_id"],
                        vector=embedding,
                        payload={
                            "article_id": chunk_obj["article_id"],
                            "chunk_index": chunk_obj["chunk_index"],
                            "title": chunk_obj["title"],
                            "content": chunk_obj["content"],  # Chunk content only
                            "text": chunk_obj[
                                "text"
                            ],  # Title + chunk content for search results
                        },
                    )
                    batch_points.append(point)
                    total_chunks_indexed += 1

                print(
                    f"  ✓ Generated {len(embeddings)} embeddings in {embed_time:.2f}s ({len(embeddings) / embed_time:.1f} embeddings/sec)"
                )

                # Upload to Qdrant when batch is full
                if len(batch_points) >= args.batch_size:
                    print(f"  → Upserting {len(batch_points)} chunks to Qdrant...")
                    upsert_start_time = time.time()
                    client.upsert(collection_name=args.collection, points=batch_points)
                    upsert_time = time.time() - upsert_start_time
                    batch_points = []
                    print(f"  ✓ Upsert completed in {upsert_time:.2f}s")

                # Progress update
                progress_pct = (total_chunks_indexed / len(all_chunks)) * 100
                print(
                    f"Progress: {total_chunks_indexed}/{len(all_chunks)} chunks indexed ({progress_pct:.1f}%)\n"
                )

            except Exception as e:
                print(f"Error generating embeddings for batch: {e}")
                continue

        # Process remaining chunks in the last batch
        if batch_points:
            print(
                f"\n=== Upserting final batch of {len(batch_points)} chunks to Qdrant ==="
            )
            start_time = time.time()
            client.upsert(collection_name=args.collection, points=batch_points)
            batch_time = time.time() - start_time
            print(f"✓ Final batch completed in {batch_time:.2f}s")

        print(
            f"✓ Successfully indexed {total_articles_processed} articles as {len(all_chunks)} chunks into collection '{args.collection}'"
        )

        # --- basic search test ---
        test_query = "apa hukum makmum bersuara keras ketika shalat?"
        print(f"\nTesting search with query: '{test_query}'")
        qvec = embed_one_ollama(test_query, args.model, args.ollama_url)
        t0 = time.time()
        res = client.search(
            collection_name=args.collection,
            query_vector=qvec,
            limit=3,
            with_payload=True,
        )
        dt = (time.time() - t0) * 1000
        print(f"✓ Found {len(res)} chunk results in {dt:.1f} ms")
        for i, r in enumerate(res, 1):
            title = (r.payload or {}).get("title", "")
            article_id = (r.payload or {}).get("article_id", "")
            chunk_index = (r.payload or {}).get("chunk_index", 0)
            content = (r.payload or {}).get("content", "")[:150]
            print(f"  {i}. {title} (Article ID: {article_id}, Chunk: {chunk_index})")
            print(f"     Score: {r.score:.4f} | Content: {content}...")

    except Exception as e:
        print("ERROR:", e, file=sys.stderr)
        sys.exit(1)
    finally:
        if client:
            client.close()


if __name__ == "__main__":
    main()
