<script lang="ts">
  import Icon from "@iconify/svelte";
  import { marked } from "marked";
  
  // Components
  import Button from "../common/Button.svelte";
  import Modal from "../common/Modal.svelte";
  import LoadingSpinner from "../common/LoadingSpinner.svelte";
  
  // Stores
  import { currentArticle, articleLoading, searchActions } from "../../stores/search";

  // Configure marked for better security and styling
  marked.setOptions({
    breaks: true, // Convert line breaks to <br>
    gfm: true,    // GitHub Flavored Markdown
  });

  // Local state
  let currentChunkIndex = 0;

  // Reactive statements
  $: isOpen = $currentArticle !== null || $articleLoading;
  $: chunks = $currentArticle?.chunks || [];
  $: totalChunks = chunks.length;
  $: currentChunk = chunks[currentChunkIndex];

  // Navigation
  const nextChunk = () => {
    if (currentChunkIndex < totalChunks - 1) {
      currentChunkIndex++;
    }
  };

  const prevChunk = () => {
    if (currentChunkIndex > 0) {
      currentChunkIndex--;
    }
  };

  const goToChunk = (index: number) => {
    currentChunkIndex = Math.max(0, Math.min(index, totalChunks - 1));
  };

  // Handle close
  const handleClose = () => {
    searchActions.closeArticle();
    currentChunkIndex = 0;
  };

  // Copy article content
  const copyArticle = () => {
    if (!$currentArticle) return;
    
    const fullText = $currentArticle.chunks
      .sort((a, b) => a.chunk_index - b.chunk_index)
      .map(chunk => chunk.content)
      .join('\n\n');
    
    navigator.clipboard.writeText(fullText);
  };

  // Copy current chunk
  const copyChunk = () => {
    if (currentChunk) {
      navigator.clipboard.writeText(currentChunk.content);
    }
  };

  // Keyboard navigation
  const handleKeydown = (e: KeyboardEvent) => {
    if (!isOpen) return;
    
    // Don't handle shortcuts if user is typing in an input/textarea
    const target = e.target as HTMLElement;
    if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable) {
      return;
    }
    
    switch (e.key) {
      case 'ArrowRight':
      case 'j':
        e.preventDefault();
        nextChunk();
        break;
      case 'ArrowLeft':
      case 'k':
        e.preventDefault();
        prevChunk();
        break;
      case 'Escape':
        e.preventDefault();
        handleClose();
        break;
    }
  };

  // Reset chunk index when article changes
  $: if ($currentArticle) {
    currentChunkIndex = 0;
  }

  // Render markdown content safely
  const renderMarkdown = (content: string): string => {
    if (!content) return '';
    try {
      return marked(content);
    } catch (error) {
      console.error('Failed to parse markdown:', error);
      // Fallback to plain text with basic HTML escaping
      return content
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/\n/g, '<br>');
    }
  };
</script>

<svelte:window on:keydown={handleKeydown} />

<Modal 
  show={isOpen} 
  onClose={handleClose}
  size="xl"
  title=""
  showHeader={false}
>
  <!-- Article Header -->
  {#if $currentArticle && !$articleLoading}
    <div class="flex items-center justify-between mb-6 pb-4 border-b">
      <div class="flex items-center gap-3">
        <Icon icon="material-symbols:article" class="w-6 h-6 text-blue-600" />
        <div>
          <h2 class="text-xl font-semibold text-gray-900">
            {$currentArticle?.title || 'Article Preview'}
          </h2>
          <p class="text-sm text-gray-600">
            Article {$currentArticle.article_id} • {totalChunks} chunks
          </p>
        </div>
      </div>

      <div class="flex items-center gap-2">
        <Button
          variant="ghost"
          size="sm"
          onClick={copyArticle}
          title="Copy full article"
        >
          <Icon icon="material-symbols:content-copy" class="w-4 h-4" />
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleClose}
          title="Close"
        >
          <Icon icon="material-symbols:close" class="w-4 h-4" />
        </Button>
      </div>
    </div>
  {/if}

  <!-- Loading State -->
  {#if $articleLoading}
    <div class="flex items-center justify-center py-12">
      <LoadingSpinner size="lg" />
      <span class="ml-3 text-gray-600">Loading article...</span>
    </div>

  <!-- Article Content -->
  {:else if $currentArticle && chunks.length > 0}
    <div class="space-y-6">
      <!-- Chunk Navigation -->
      {#if totalChunks > 1}
        <div class="flex items-center justify-between py-3 border-b">
          <div class="flex items-center gap-3">
            <Button
              variant="ghost"
              size="sm"
              onClick={prevChunk}
              disabled={currentChunkIndex === 0}
              title="Previous chunk (←)"
            >
              <Icon icon="material-symbols:chevron-left" class="w-4 h-4" />
            </Button>

            <div class="flex items-center gap-2 text-sm">
              <span class="text-gray-600">Chunk</span>
              <select
                bind:value={currentChunkIndex}
                on:change={(e) => goToChunk(parseInt(e.currentTarget.value))}
                class="border border-gray-300 rounded px-2 py-1 text-sm focus:ring-blue-500 focus:border-blue-500"
              >
                {#each chunks as _, index}
                  <option value={index}>{index + 1}</option>
                {/each}
              </select>
              <span class="text-gray-600">of {totalChunks}</span>
            </div>

            <Button
              variant="ghost"
              size="sm"
              onClick={nextChunk}
              disabled={currentChunkIndex === totalChunks - 1}
              title="Next chunk (→)"
            >
              <Icon icon="material-symbols:chevron-right" class="w-4 h-4" />
            </Button>
          </div>

          <Button
            variant="ghost"
            size="sm"
            onClick={copyChunk}
            title="Copy current chunk"
          >
            <Icon icon="material-symbols:content-copy" class="w-4 h-4 mr-1" />
            Copy Chunk
          </Button>
        </div>
      {/if}

      <!-- Current Chunk Content -->
      {#if currentChunk}
        <div class="prose prose-sm max-w-none">
          <div class="bg-gray-50 px-4 py-3 rounded-lg border">
            <div class="flex items-center justify-between mb-2">
              <div class="text-xs text-gray-600">
                Chunk {currentChunk.chunk_index + 1}
                {#if currentChunk.score < 1}
                  • Score: {(currentChunk.score * 100).toFixed(1)}%
                {/if}
              </div>
              <div class="text-xs text-gray-500">
                ID: {currentChunk.id}
              </div>
            </div>
          </div>

          <div class="mt-4 text-gray-800 leading-relaxed markdown-content">
            {@html renderMarkdown(currentChunk.content)}
          </div>
        </div>

        <!-- Chunk Navigation Hints -->
        {#if totalChunks > 1}
          <div class="text-xs text-gray-500 text-center py-2 bg-gray-50 rounded-lg">
            Use arrow keys (← →) or J/K to navigate between chunks
          </div>
        {/if}
      {/if}

      <!-- Quick Overview (if multiple chunks) -->
      {#if totalChunks > 1}
        <div class="border-t pt-4">
          <h3 class="text-sm font-medium text-gray-900 mb-3">All Chunks</h3>
          <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
            {#each chunks as chunk, index}
              <button
                class="text-left p-3 text-xs border rounded {currentChunkIndex === index 
                  ? 'border-blue-500 bg-blue-50' 
                  : 'border-gray-200 hover:border-gray-300 bg-white'} 
                  transition-colors"
                on:click={() => goToChunk(index)}
              >
                <div class="font-medium text-gray-900 mb-1">
                  Chunk {chunk.chunk_index + 1}
                </div>
                <div class="text-gray-600 line-clamp-2">
                  {chunk.content.slice(0, 100)}...
                </div>
              </button>
            {/each}
          </div>
        </div>
      {/if}
    </div>

  <!-- Error State -->
  {:else}
    <div class="text-center py-12">
      <div class="text-red-500 mb-4">
        <Icon icon="material-symbols:error" class="w-16 h-16 mx-auto" />
      </div>
      <h3 class="text-lg font-medium text-gray-900 mb-2">Failed to Load Article</h3>
      <p class="text-gray-600 mb-4">
        The article could not be loaded. It may have been deleted or moved.
      </p>
      <Button
        variant="primary"
        onClick={handleClose}
      >
        Close
      </Button>
    </div>
  {/if}
</Modal>

<style>
  .line-clamp-2 {
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  /* Markdown content styling */
  :global(.markdown-content h1) {
    font-size: 1.875rem;
    font-weight: bold;
    margin-bottom: 1rem;
    margin-top: 1.5rem;
    color: #1f2937;
  }

  :global(.markdown-content h2) {
    font-size: 1.5rem;
    font-weight: 600;
    margin-bottom: 0.75rem;
    margin-top: 1.25rem;
    color: #1f2937;
  }

  :global(.markdown-content h3) {
    font-size: 1.25rem;
    font-weight: 600;
    margin-bottom: 0.5rem;
    margin-top: 1rem;
    color: #1f2937;
  }

  :global(.markdown-content h4),
  :global(.markdown-content h5),
  :global(.markdown-content h6) {
    font-size: 1.125rem;
    font-weight: 600;
    margin-bottom: 0.5rem;
    margin-top: 0.75rem;
    color: #1f2937;
  }

  :global(.markdown-content p) {
    margin-bottom: 1rem;
    line-height: 1.7;
  }

  :global(.markdown-content ul),
  :global(.markdown-content ol) {
    margin-bottom: 1rem;
    padding-left: 1.5rem;
  }

  :global(.markdown-content li) {
    margin-bottom: 0.25rem;
  }

  :global(.markdown-content blockquote) {
    border-left: 4px solid #e5e7eb;
    padding-left: 1rem;
    margin: 1rem 0;
    font-style: italic;
    color: #6b7280;
  }

  :global(.markdown-content code) {
    background-color: #f3f4f6;
    padding: 0.125rem 0.25rem;
    border-radius: 0.25rem;
    font-family: ui-monospace, SFMono-Regular, "SF Mono", Consolas, "Liberation Mono", Menlo, monospace;
    font-size: 0.875em;
    color: #ef4444;
  }

  :global(.markdown-content pre) {
    background-color: #f3f4f6;
    padding: 1rem;
    border-radius: 0.5rem;
    overflow-x: auto;
    margin: 1rem 0;
  }

  :global(.markdown-content pre code) {
    background-color: transparent;
    padding: 0;
    color: #1f2937;
    font-size: 0.875rem;
  }

  :global(.markdown-content a) {
    color: #2563eb;
    text-decoration: underline;
  }

  :global(.markdown-content a:hover) {
    color: #1d4ed8;
  }

  :global(.markdown-content strong) {
    font-weight: 600;
  }

  :global(.markdown-content em) {
    font-style: italic;
  }

  :global(.markdown-content table) {
    width: 100%;
    border-collapse: collapse;
    margin: 1rem 0;
  }

  :global(.markdown-content th),
  :global(.markdown-content td) {
    border: 1px solid #e5e7eb;
    padding: 0.5rem;
    text-align: left;
  }

  :global(.markdown-content th) {
    background-color: #f9fafb;
    font-weight: 600;
  }

  :global(.markdown-content hr) {
    border: 0;
    border-top: 1px solid #e5e7eb;
    margin: 1.5rem 0;
  }
</style>