import weaviate
import json
import os
from typing import List, Dict
from weaviate.classes.init import AdditionalConfig, Timeout


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


def create_chunk_objects(article: Dict, max_chunks_per_article: int = 10) -> List[Dict]:
    """
    Create chunk objects from an article.

    Args:
        article: Article dictionary with title and content
        max_chunks_per_article: Maximum number of chunks per article (to avoid very long articles)

    Returns:
        List of chunk objects ready for indexing
    """
    chunks = chunk_text(article.get("content", ""))

    # Limit chunks per article to avoid overwhelming the index
    chunks = chunks[:max_chunks_per_article]

    chunk_objects = []
    for i, chunk in enumerate(chunks):
        # Include title in each chunk for better context
        # Format: "Title: [article title]\n\n[chunk content]"
        chunk_with_title = f"Title: {article['title']}\n\n{chunk}"

        chunk_objects.append({"title": article["title"], "body": chunk_with_title})

    return chunk_objects


# Check if cleaned file exists, otherwise use regular articles
if os.path.exists("articles_clean.json"):
    articles_file = "articles_clean.json"
    print(f"Using cleaned articles from {articles_file}")
elif os.path.exists("articles.json"):
    articles_file = "articles.json"
    print(f"Using articles from {articles_file}")
else:
    print("Error: No articles file found. Please run extract_articles.py first.")
    exit(1)

print(f"Loading articles from {articles_file}...")
with open(articles_file, "r", encoding="utf-8") as f:
    articles = json.load(f)

print(f"Loaded {len(articles)} articles")

# Filter articles with content
articles_with_content = [a for a in articles if a.get("content")]
print(f"Found {len(articles_with_content)} articles with content")

# Limit for testing (remove or increase for production)
articles_to_index = articles_with_content[:10]  # Index first 100 articles for testing
print(f"Will index {len(articles_to_index)} articles (limited for testing)")

client = weaviate.connect_to_local(
    additional_config=AdditionalConfig(
        timeout=Timeout(init=60, query=180, insert=600)  # seconds
    )
)

coll = client.collections.get("Docs")

# Insert data in batches
print("Indexing articles to Weaviate (with chunking)...")
indexed_chunks = 0
indexed_articles = 0
batch_size = 200

with coll.batch.fixed_size(batch_size, concurrent_requests=4) as batch:
    # with coll.batch.rate_limit(requests_per_minute=600) as batch:
    for article in articles_to_index:
        # Create chunks for this article
        chunk_objects = create_chunk_objects(article)

        # Add each chunk to the batch
        for chunk_obj in chunk_objects:
            batch.add_object(chunk_obj)
            indexed_chunks += 1

        indexed_articles += 1
        print(f"  Indexed {indexed_articles} articles ({indexed_chunks} chunks)...")
        # if indexed_articles % 10 == 0:
        #     print(f"  Indexed {indexed_articles} articles ({indexed_chunks} chunks)...")

print(f"Successfully indexed {indexed_articles} articles as {indexed_chunks} chunks")

# Test with vector search
print("\nTesting vector search...")
test_queries = [
    "apa hukum makmum bersuara keras ketika shalat?",
    "apa hukum makan kepiting?",
    "jelaskan tentang haji atau umrah",
    "tata cara sholat jum'at",
]

for query in test_queries:
    print(f"\nSearching for: '{query}'")
    res = coll.query.near_text(query, limit=3)

    for i, obj in enumerate(res.objects, 1):
        title = obj.properties.get("title", "No title")
        body = obj.properties.get("body", "")
        # Extract just the chunk content (after the title line)
        if "\n\n" in body:
            chunk_preview = body.split("\n\n", 1)[1][:150] + "..."
        else:
            chunk_preview = body[:150] + "..."

        print(f"  {i}. {title}")
        print(f"     Chunk: {chunk_preview}")

client.close()
print("\nIndexing complete!")
