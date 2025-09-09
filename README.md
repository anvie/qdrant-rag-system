# Qdrant RAG System

A powerful Retrieval-Augmented Generation (RAG) system that combines Qdrant vector database with LLMs for intelligent, context-aware chat and search capabilities.

## Features

- 🔍 **Semantic Vector Search**: Search documents using semantic similarity
- 🤖 **RAG Chat System**: Context-aware chat powered by LLMs with retrieved documents
- 📚 **Multiple Data Sources**: Index from JSON files or markdown directories
- 🔄 **Hybrid Search**: Combines vector similarity with keyword matching for better relevance
- 📖 **Article Reader**: Read complete articles by ID with all chunks
- 💬 **Interactive Modes**: Both search and chat interfaces with rich commands
- 🚀 **Streaming Responses**: Real-time streaming of LLM responses
- 📊 **Source Citations**: Track and display sources for generated responses

## Prerequisites

- Python 3.9+
- Docker (for Qdrant)
- Ollama installed locally or accessible remotely
- At least one embedding model and one LLM model in Ollama

## Installation

1. Clone the repository:

```bash
git clone https://github.com/anvie/qdrant-rag-system.git
cd ollama
```

2. Create and activate virtual environment:

```bash
python3 -m venv env
source env/bin/activate  # On Windows: env\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Start Qdrant using Docker:

```bash
docker run -p 6333:6333 -p 6334:6334 \
    -v $(pwd)/qdrant_storage:/qdrant/storage:z \
    qdrant/qdrant
```

5. Ensure Ollama is running:

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Or use a remote Ollama instance
# Update --ollama-url parameter in scripts
```

## Project Structure

```
ollama/
├── index_qdrant.py      # Index documents into Qdrant
├── query_qdrant.py      # Search and retrieve documents
├── chat_rag.py          # RAG chat system
├── docs_example/        # Example markdown documents
├── articles_clean.json  # Example JSON data
└── README.md           # This file
```

## Usage

### 1. Indexing Documents

#### Index from JSON file:

```bash
python index_qdrant.py \
    --json-file articles_clean.json \
    --ollama-url http://localhost:11434 \
    --model embeddinggemma:latest \
    --recreate
```

#### Index from markdown directory:

```bash
python index_qdrant.py \
    --scan-dir docs_example \
    --ollama-url http://localhost:11434 \
    --model bge-m3:567m \
    --recreate
```

#### Parameters:

- `--json-file`: Path to JSON file containing articles
- `--scan-dir`: Directory to scan for markdown files (overrides --json-file)
- `--collection`: Qdrant collection name (default: "articles")
- `--model`: Ollama embedding model to use
- `--recreate`: Recreate collection from scratch
- `--batch-size`: Number of chunks to process in batch
- `--chunk-size`: Words per chunk (default: 150)
- `--chunk-overlap`: Overlapping words between chunks (default: 30)
- `--max-chunks-per-article`: Maximum chunks per article (default: 10)

### 2. Searching Documents

#### Basic search:

```bash
python query_qdrant.py --query "What is a DocType?"
```

#### Hybrid search (recommended):

```bash
python query_qdrant.py \
    --query "database operations" \
    --hybrid \
    --limit 5
```

#### Interactive search mode:

```bash
python query_qdrant.py --interactive --hybrid
```

Interactive commands:

- `help` - Show available commands
- `history` - Show query history
- `stats` - Show collection statistics
- `settings` - Show current settings
- `read <id>` - Read full article by ID
- `quit/exit/q` - Exit

### 3. RAG Chat System

#### Start RAG chat:

```bash
python chat_rag.py \
    --llm-model llama2 \
    --embedding-model bge-m3:567m \
    --show-sources
```

#### With streaming responses:

```bash
python chat_rag.py \
    --llm-model mistral \
    --stream \
    --show-sources \
    --top-k 5
```

#### Chat commands:

- `help` - Show available commands
- `clear` - Clear conversation history
- `sources` - Show sources from last response
- `settings` - Show current settings
- `save` - Save conversation to file
- `quit/exit/q` - Exit chat

#### Parameters:

- `--llm-model`: Ollama LLM model for generation
- `--embedding-model`: Ollama model for embeddings
- `--top-k`: Number of context chunks to retrieve (default: 5)
- `--temperature`: LLM sampling temperature (0.0-1.0)
- `--max-tokens`: Maximum tokens in response
- `--stream`: Stream LLM responses
- `--show-sources`: Display source citations
- `--system-prompt`: Custom system prompt for LLM

## Configuration

### Ollama Configuration

Default Ollama URL: `http://localhost:11434`

To use a remote Ollama instance:

```bash
--ollama-url http://192.168.1.7:11434
```

### Qdrant Configuration

Default Qdrant URL: `http://localhost:6333`

To use a remote Qdrant instance:

```bash
--qdrant-url http://remote-server:6333
```

### Available Models

Check available models in Ollama:

```bash
curl http://localhost:11434/api/tags | python -m json.tool
```

Common embedding models:

- `embeddinggemma:latest` (768 dimensions)
- `bge-m3:567m` (1024 dimensions)
- `mxbai-embed-large` (1024 dimensions)

Common LLM models:

- `mistral`
- `gemma`
- `llama3`
- `sahabatai1`
- `sidrap-7b`

## Examples

### Complete Workflow Example

1. **Index documents:**

```bash
python index_qdrant.py \
    --scan-dir docs_example \
    --model bge-m3:567m \
    --recreate \
    --chunk-size 200 \
    --max-chunks-per-article 15
```

2. **Test search:**

```bash
python query_qdrant.py \
    --query "REST API authentication" \
    --hybrid \
    --limit 5 \
    --output-format compact
```

3. **Start RAG chat:**

```bash
python chat_rag.py \
    --llm-model llama2 \
    --embedding-model bge-m3:567m \
    --top-k 3 \
    --temperature 0.7 \
    --stream \
    --show-sources
```

### Custom System Prompt

```bash
python chat_rag.py \
    --llm-model llama2 \
    --system-prompt "You are a technical documentation assistant. Always provide code examples when relevant."
```

## Troubleshooting

### Vector Dimension Mismatch

If you get a "Vector dimension error", ensure the embedding model used for querying matches the one used for indexing:

```bash
# Check collection info
python query_qdrant.py --interactive
> stats

# Re-index with correct model if needed
python index_qdrant.py --recreate --model <correct-model>
```

### Connection Issues

**Ollama connection refused:**

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama if needed
ollama serve
```

**Qdrant connection refused:**

```bash
# Check if Qdrant is running
docker ps | grep qdrant

# Start Qdrant if needed
docker run -p 6333:6333 qdrant/qdrant
```

### Memory Issues

For large datasets, adjust batch sizes:

```bash
python index_qdrant.py \
    --batch-size 50 \
    --embedding-batch-size 10 \
    --workers 2
```

## Performance Tips

1. **Use hybrid search** for better relevance:

   ```bash
   --hybrid --fusion-method rrf
   ```

2. **Optimize chunk size** based on your content:

   - Shorter chunks (100-150 words) for precise retrieval
   - Longer chunks (200-300 words) for more context

3. **Adjust top-k** for RAG:

   - Lower k (3-5) for focused responses
   - Higher k (7-10) for comprehensive answers

4. **Use streaming** for better UX:
   ```bash
   --stream
   ```

## Development

### Adding New Features

The codebase is modular and extensible:

- `embed_one_ollama()`: Handles embedding generation
- `search_qdrant_hybrid()`: Implements hybrid search
- `chat_with_rag()`: Main RAG pipeline
- `interactive_chat()`: Interactive chat interface

### Testing

Run basic tests:

```bash
# Test indexing
python index_qdrant.py --scan-dir docs_example --max-docs 5 --recreate

# Test search
python query_qdrant.py --query "test query" --limit 3

# Test chat
echo "What is Frappe?" | python chat_rag.py --llm-model llama2
```

## License

[Add your license here]

## Contributing

[Add contribution guidelines]

## Acknowledgments

- [Qdrant](https://qdrant.tech/) - Vector database
- [Ollama](https://ollama.ai/) - Local LLM runtime

[] Robin Syihab

