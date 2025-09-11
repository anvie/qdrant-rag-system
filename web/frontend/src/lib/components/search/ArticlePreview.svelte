<script lang="ts">
  import Icon from "@iconify/svelte";
  
  // Components
  import Button from "../common/Button.svelte";
  import Modal from "../common/Modal.svelte";
  import LoadingSpinner from "../common/LoadingSpinner.svelte";
  
  // Stores
  import { currentArticle, articleLoading, searchActions } from "../../stores/search";

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
</script>

<svelte:window on:keydown={handleKeydown} />

<Modal 
  {isOpen} 
  onClose={handleClose}
  size="xl"
  showCloseButton={true}
>
  <div slot="header" class="flex items-center justify-between">
    <div class="flex items-center gap-3">
      <Icon icon="material-symbols:article" class="w-6 h-6 text-blue-600" />
      <div>
        <h2 class="text-xl font-semibold text-gray-900">
          {$currentArticle?.title || 'Article Preview'}
        </h2>
        {#if $currentArticle}
          <p class="text-sm text-gray-600">
            Article {$currentArticle.article_id} • {totalChunks} chunks
          </p>
        {/if}
      </div>
    </div>

    {#if $currentArticle && !$articleLoading}
      <div class="flex items-center gap-2">
        <Button
          variant="ghost"
          size="sm"
          onClick={copyArticle}
          title="Copy full article"
        >
          <Icon icon="material-symbols:content-copy" class="w-4 h-4" />
        </Button>
      </div>
    {/if}
  </div>

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

          <div class="mt-4 text-gray-800 leading-relaxed">
            {currentChunk.content}
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
</style>