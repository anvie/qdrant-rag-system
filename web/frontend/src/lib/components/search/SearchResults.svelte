<script lang="ts">
  import { onMount } from "svelte";
  import Icon from "@iconify/svelte";

  // Components
  import Button from "../common/Button.svelte";
  import Card from "../common/Card.svelte";
  import LoadingSpinner from "../common/LoadingSpinner.svelte";

  // Stores and types
  import {
    searchResults,
    searchLoading,
    searchError,
    currentSearchResponse,
    searchActions,
    searchStats,
  } from "../../stores/search";
  import type { SearchResult } from "../../services/api";

  // Props
  export let viewMode: "detailed" | "compact" | "cards" = "detailed";
  export let showArticleGrouping: boolean = true;
  export let highlightTerms: boolean = true;
  export let enableActions: boolean = true;

  // Local state
  let selectedResults: Set<number> = new Set();
  let hoveredResult: number | null = null;

  // View mode options
  const viewModes = [
    {
      value: "detailed",
      label: "Detailed",
      icon: "material-symbols:view-list",
    },
    {
      value: "compact",
      label: "Compact",
      icon: "material-symbols:view-stream",
    },
    { value: "cards", label: "Cards", icon: "material-symbols:view-module" },
  ];

  // Handle result selection
  const toggleSelection = (resultId: number) => {
    if (selectedResults.has(resultId)) {
      selectedResults.delete(resultId);
    } else {
      selectedResults.add(resultId);
    }
    selectedResults = selectedResults; // Trigger reactivity
  };

  const selectAll = () => {
    selectedResults = new Set($searchResults.map((r) => r.id));
  };

  const clearSelection = () => {
    selectedResults = new Set();
  };

  // Result actions
  const viewArticle = (result: SearchResult) => {
    // Get the current collection from search filters
    const collection = $currentSearchResponse?.collection || 'articles';
    searchActions.loadArticle(result.article_id, collection);
  };

  const findSimilar = (result: SearchResult) => {
    // Get the current collection from search filters
    const collection = $currentSearchResponse?.collection || 'articles';
    searchActions.findSimilar(result.id, collection);
  };

  const copyContent = (result: SearchResult) => {
    navigator.clipboard.writeText(result.content);
    // Could add notification here
  };

  // Highlight search terms in content
  const highlightText = (text: string, query: string): string => {
    if (!highlightTerms || !query) return text;

    const terms = query.split(" ").filter((term) => term.length > 2);
    let highlighted = text;

    terms.forEach((term) => {
      const regex = new RegExp(`(${term})`, "gi");
      highlighted = highlighted.replace(
        regex,
        '<mark class="bg-yellow-200 px-0.5 rounded">$1</mark>',
      );
    });

    return highlighted;
  };

  // Format score for display
  const formatScore = (score: number): string => {
    return (score * 100).toFixed(1) + "%";
  };

  // Group results by article if needed
  $: groupedResults =
    showArticleGrouping && $currentSearchResponse?.grouped_by_article
      ? groupResultsByArticle($searchResults)
      : [{ article_id: null, title: "All Results", results: $searchResults }];

  const groupResultsByArticle = (results: SearchResult[]) => {
    const groups = new Map<
      number,
      { article_id: number; title: string; results: SearchResult[] }
    >();

    results.forEach((result) => {
      if (!groups.has(result.article_id)) {
        groups.set(result.article_id, {
          article_id: result.article_id,
          title: result.title || `Article ${result.article_id}`,
          results: [],
        });
      }
      groups.get(result.article_id)!.results.push(result);
    });

    return Array.from(groups.values()).sort(
      (a, b) => b.results[0].score - a.results[0].score,
    );
  };

  // Export selected results
  const exportSelected = () => {
    const selected = $searchResults.filter((r) => selectedResults.has(r.id));
    const exportData = {
      query: $currentSearchResponse?.query,
      timestamp: new Date().toISOString(),
      results: selected,
    };

    const blob = new Blob([JSON.stringify(exportData, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `search-results-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };
</script>

<!-- Results Container -->
<div class="space-y-4">
  <!-- Results Header -->
  {#if $searchResults.length > 0 || $searchLoading}
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-4">
        <!-- Results Count -->
        {#if $currentSearchResponse}
          <div class="text-sm text-gray-600">
            <span class="font-medium">{$searchStats.totalResults}</span> results
            {#if $searchStats.uniqueArticles > 1}
              from <span class="font-medium">{$searchStats.uniqueArticles}</span
              > articles
            {/if}
            in
            <span class="font-medium"
              >{($searchStats.queryTime * 1000).toFixed(0)}</span
            >ms
          </div>
        {/if}

        <!-- Selection Info -->
        {#if selectedResults.size > 0}
          <div class="text-sm text-blue-600">
            {selectedResults.size} selected
          </div>
        {/if}
      </div>

      <div class="flex items-center gap-2">
        <!-- Selection Actions -->
        {#if enableActions && $searchResults.length > 0}
          <div class="flex items-center gap-1 border-r pr-2">
            <Button
              variant="ghost"
              size="xs"
              onClick={selectAll}
              disabled={selectedResults.size === $searchResults.length}
            >
              Select All
            </Button>
            <Button
              variant="ghost"
              size="xs"
              onClick={clearSelection}
              disabled={selectedResults.size === 0}
            >
              Clear
            </Button>
            {#if selectedResults.size > 0}
              <Button
                variant="ghost"
                size="xs"
                onClick={exportSelected}
                class="text-blue-600"
              >
                <Icon icon="material-symbols:download" class="w-3 h-3 mr-1" />
                Export
              </Button>
            {/if}
          </div>
        {/if}

        <!-- View Mode Selector -->
        <div class="flex bg-gray-100 rounded-lg p-0.5">
          {#each viewModes as mode}
            <button
              class="px-2 py-1 text-xs rounded {viewMode === mode.value
                ? 'bg-white shadow-sm text-gray-900'
                : 'text-gray-600 hover:text-gray-900'}"
              on:click={() => (viewMode = mode.value)}
              title={mode.label}
            >
              <Icon icon={mode.icon} class="w-3 h-3" />
            </button>
          {/each}
        </div>
      </div>
    </div>
  {/if}

  <!-- Loading State -->
  {#if $searchLoading}
    <Card>
      <div class="flex items-center justify-center py-12">
        <LoadingSpinner size="lg" />
        <span class="ml-3 text-gray-600">Searching...</span>
      </div>
    </Card>

    <!-- Error State -->
  {:else if $searchError}
    <Card>
      <div class="text-center py-12">
        <div class="text-red-500 mb-4">
          <Icon icon="material-symbols:error" class="w-16 h-16 mx-auto" />
        </div>
        <h3 class="text-lg font-medium text-gray-900 mb-2">Search Error</h3>
        <div class="mb-6">
          <p class="text-gray-800 mb-2 max-w-md mx-auto font-medium">{$searchError}</p>
          {#if $searchError.includes("doesn't exist")}
            <p class="text-gray-600 text-sm max-w-md mx-auto">
              Please select a different collection or create the collection first.
            </p>
          {/if}
        </div>
        <div class="flex gap-3 justify-center">
          <Button variant="primary" onClick={() => searchActions.executeSearch()}>
            Try Again
          </Button>
          {#if $searchError.includes("doesn't exist")}
            <Button variant="ghost" onClick={() => searchActions.clearResults()}>
              Clear Search
            </Button>
          {/if}
        </div>
      </div>
    </Card>

    <!-- No Results -->
  {:else if $searchResults.length === 0}
    <Card>
      <div class="text-center py-12">
        <div class="text-gray-400 mb-4">
          <Icon icon="material-symbols:search-off" class="w-16 h-16 mx-auto" />
        </div>
        <h3 class="text-lg font-medium text-gray-900 mb-2">No Results Found</h3>
        <p class="text-gray-600 mb-4 max-w-md mx-auto">
          Try adjusting your search terms or filters to find more results.
        </p>
        <Button variant="ghost" onClick={() => searchActions.clearResults()}>
          Clear Search
        </Button>
      </div>
    </Card>

    <!-- Results -->
  {:else}
    <div class="space-y-4">
      {#each groupedResults as group}
        {#if groupedResults.length > 1}
          <!-- Article Group Header -->
          <div
            class="border-l-4 border-blue-500 pl-4 py-2 bg-blue-50 rounded-r-lg"
          >
            <h3 class="font-medium text-gray-900">{group.title}</h3>
            <p class="text-sm text-gray-600">{group.results.length} chunks</p>
          </div>
        {/if}

        <!-- Results Grid/List -->
        <div
          class={viewMode === "cards"
            ? "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
            : "space-y-2"}
        >
          {#each group.results as result (result.id)}
            <!-- Result Item -->
            <div
              class="group relative {viewMode === 'cards'
                ? ''
                : 'border rounded-lg'} 
                     {selectedResults.has(result.id)
                ? 'ring-2 ring-blue-500 bg-blue-50'
                : 'bg-white'}
                     hover:shadow-md transition-all duration-200"
              role="article"
              on:mouseenter={() => (hoveredResult = result.id)}
              on:mouseleave={() => (hoveredResult = null)}
            >
              {#if viewMode === "cards"}
                <Card>
                  <!-- Card Content -->
                  <div class="space-y-3">
                    <!-- Header -->
                    <div class="flex items-start justify-between">
                      <div class="flex-1 min-w-0">
                        <div
                          class="flex items-center gap-2 text-xs text-gray-500 mb-1"
                        >
                          <span class="bg-gray-100 px-2 py-0.5 rounded">
                            Article {result.article_id}
                          </span>
                          <span
                            class="bg-blue-100 text-blue-700 px-2 py-0.5 rounded"
                          >
                            {formatScore(result.score)}
                          </span>
                        </div>
                        <h4 class="font-medium text-sm text-gray-900 truncate">
                          {result.title || `Chunk ${result.chunk_index}`}
                        </h4>
                      </div>

                      {#if enableActions}
                        <input
                          type="checkbox"
                          checked={selectedResults.has(result.id)}
                          on:change={() => toggleSelection(result.id)}
                          class="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                        />
                      {/if}
                    </div>

                    <!-- Content -->
                    <div class="text-sm text-gray-700 line-clamp-4">
                      {@html highlightText(
                        result.content,
                        $currentSearchResponse?.query || "",
                      )}
                    </div>

                    <!-- Actions -->
                    {#if enableActions}
                      <div
                        class="flex items-center justify-between pt-2 border-t"
                      >
                        <div class="text-xs text-gray-500">
                          Chunk {result.chunk_index + 1}
                        </div>
                        <div
                          class="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity"
                        >
                          <Button
                            variant="ghost"
                            size="xs"
                            onClick={() => viewArticle(result)}
                            title="View full article"
                          >
                            <Icon
                              icon="material-symbols:article"
                              class="w-3 h-3"
                            />
                          </Button>
                          <Button
                            variant="ghost"
                            size="xs"
                            onClick={() => findSimilar(result)}
                            title="Find similar"
                          >
                            <Icon
                              icon="material-symbols:similarity"
                              class="w-3 h-3"
                            />
                          </Button>
                          <Button
                            variant="ghost"
                            size="xs"
                            onClick={() => copyContent(result)}
                            title="Copy content"
                          >
                            <Icon
                              icon="material-symbols:content-copy"
                              class="w-3 h-3"
                            />
                          </Button>
                        </div>
                      </div>
                    {/if}
                  </div>
                </Card>
              {:else}
                <!-- List/Detailed View -->
                <div class="p-4 {viewMode === 'compact' ? 'py-2' : ''}">
                  <div class="flex items-start gap-4">
                    <!-- Checkbox -->
                    {#if enableActions}
                      <input
                        type="checkbox"
                        checked={selectedResults.has(result.id)}
                        on:change={() => toggleSelection(result.id)}
                        class="mt-1 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                      />
                    {/if}

                    <!-- Content -->
                    <div class="flex-1 min-w-0">
                      <!-- Header -->
                      <div class="flex items-center gap-3 mb-2">
                        <div
                          class="flex items-center gap-2 text-xs text-gray-500"
                        >
                          <span class="bg-gray-100 px-2 py-0.5 rounded">
                            Article {result.article_id}
                          </span>
                          <span
                            class="bg-blue-100 text-blue-700 px-2 py-0.5 rounded"
                          >
                            {formatScore(result.score)}
                          </span>
                          <span>Chunk {result.chunk_index + 1}</span>
                        </div>
                      </div>

                      <!-- Title -->
                      {#if viewMode === "detailed" && result.title}
                        <h4 class="font-medium text-gray-900 mb-2 truncate">
                          {result.title}
                        </h4>
                      {/if}

                      <!-- Content -->
                      <div
                        class="text-sm text-gray-700 {viewMode === 'compact'
                          ? 'line-clamp-2'
                          : 'line-clamp-3'} mb-2"
                      >
                        {@html highlightText(
                          result.content,
                          $currentSearchResponse?.query || "",
                        )}
                      </div>

                      <!-- Actions -->
                      {#if enableActions && (viewMode === "detailed" || hoveredResult === result.id)}
                        <div class="flex items-center gap-2">
                          <Button
                            variant="ghost"
                            size="xs"
                            onClick={() => viewArticle(result)}
                          >
                            <Icon
                              icon="material-symbols:article"
                              class="w-3 h-3 mr-1"
                            />
                            View Article
                          </Button>
                          <Button
                            variant="ghost"
                            size="xs"
                            onClick={() => findSimilar(result)}
                          >
                            <Icon
                              icon="material-symbols:similarity"
                              class="w-3 h-3 mr-1"
                            />
                            Similar
                          </Button>
                          <Button
                            variant="ghost"
                            size="xs"
                            onClick={() => copyContent(result)}
                          >
                            <Icon
                              icon="material-symbols:content-copy"
                              class="w-3 h-3 mr-1"
                            />
                            Copy
                          </Button>
                        </div>
                      {/if}
                    </div>
                  </div>
                </div>
              {/if}
            </div>
          {/each}
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .line-clamp-2 {
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .line-clamp-3 {
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .line-clamp-4 {
    display: -webkit-box;
    -webkit-line-clamp: 4;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
</style>

