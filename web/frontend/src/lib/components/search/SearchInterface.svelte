<script lang="ts">
  import { onMount } from "svelte";
  import Icon from "@iconify/svelte";

  // Components
  import Button from "../common/Button.svelte";
  import Card from "../common/Card.svelte";
  import FormInput from "../common/FormInput.svelte";
  import FormSelect from "../common/FormSelect.svelte";
  import LoadingSpinner from "../common/LoadingSpinner.svelte";

  // Stores and services
  import {
    searchActions,
    searchQuery,
    searchFilters,
    searchLoading,
    searchHistory,
    searchStats,
  } from "../../stores/search";
  import { collectionsActions, collections } from "../../stores/collections";

  // Props
  export let autoFocus: boolean = false;
  export let showAdvancedOptions: boolean = false;
  export let showHistory: boolean = true;
  export let placeholder: string = "Search your documents...";

  // Local state
  let showAdvanced = showAdvancedOptions;
  let recentSearches = $searchHistory.slice(0, 5);

  // Reactive statements
  $: collectionsOptions = $collections.map((c) => ({
    value: c.name,
    label: c.name,
  }));
  $: fusionMethods = [
    { value: "rrf", label: "RRF (Reciprocal Rank Fusion)" },
    { value: "dbsf", label: "DBSF (Distribution-Based Score Fusion)" },
  ];

  // Update recent searches when history changes
  $: recentSearches = $searchHistory.slice(0, 5);

  // Handle form submission
  const handleSubmit = (e: Event) => {
    e.preventDefault();
    if ($searchQuery.trim()) {
      searchActions.executeSearch();
    }
  };

  // Handle input changes
  const handleQueryChange = (e: Event) => {
    const target = e.target as HTMLInputElement;
    searchActions.setQuery(target.value);
  };

  const handleFilterChange = (
    field: keyof typeof $searchFilters,
    value: any,
  ) => {
    searchActions.updateFilters({ [field]: value });
  };

  // Handle keyboard shortcuts
  const handleKeydown = (e: KeyboardEvent) => {
    // Don't handle shortcuts if user is typing in an input/textarea
    const target = e.target as HTMLElement;
    if (
      target.tagName === "INPUT" ||
      target.tagName === "TEXTAREA" ||
      target.isContentEditable
    ) {
      return;
    }

    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      handleSubmit(e);
    }
  };

  // Execute search from history
  const searchFromHistory = (historyItem: any) => {
    searchActions.searchFromHistory(historyItem);
  };

  // Toggle advanced options
  const toggleAdvanced = () => {
    showAdvanced = !showAdvanced;
  };

  // Reset filters
  const resetFilters = () => {
    searchActions.resetFilters();
  };

  // Initialize collections on mount
  onMount(async () => {
    await collectionsActions.initialize();
  });
</script>

<svelte:window on:keydown={handleKeydown} />

<Card>
  <div slot="header" class="flex items-center justify-between">
    <div class="flex items-center gap-2">
      <Icon icon="material-symbols:search" class="w-5 h-5 text-blue-600" />
      <h2 class="text-lg font-medium text-gray-900">Vector Search</h2>
    </div>

    {#if $searchStats.totalResults > 0}
      <div class="flex items-center gap-4 text-sm text-gray-600">
        <span>{$searchStats.totalResults} results</span>
        <span>{$searchStats.uniqueArticles} articles</span>
        <span>{($searchStats.queryTime * 1000).toFixed(0)}ms</span>
      </div>
    {/if}
  </div>

  <div class="space-y-6">
    <!-- Main Search Form -->
    <form on:submit={handleSubmit} class="space-y-4">
      <!-- Query Input -->
      <div class="relative">
        <FormInput
          type="text"
          {placeholder}
          value={$searchQuery}
          onInput={(value) => searchActions.setQuery(value.toString())}
          disabled={$searchLoading}
          class="pr-12"
        />

        <!-- Search Button -->
        <div class="absolute right-2 top-1/2 -translate-y-1/2">
          <Button
            type="submit"
            variant="primary"
            size="sm"
            disabled={!$searchQuery.trim() || $searchLoading}
            ariaLabel="Execute search"
          >
            {#if $searchLoading}
              <LoadingSpinner size="sm" />
            {:else}
              <Icon icon="material-symbols:search" class="w-4 h-4" />
            {/if}
          </Button>
        </div>
      </div>

      <!-- Quick Options Row -->
      <div class="flex items-center justify-between gap-4 flex-wrap">
        <div class="flex items-center gap-4 flex-1 min-w-0">
          <!-- Collection Selector -->
          <div class="flex-1 min-w-[200px]">
            <FormSelect
              options={collectionsOptions}
              value={$searchFilters.collection}
              onChange={(value) => handleFilterChange("collection", value)}
              disabled={$searchLoading}
              placeholder="Select collection"
            />
          </div>

          <!-- Hybrid Toggle -->
          <label class="flex items-center gap-2 text-sm whitespace-nowrap">
            <input
              type="checkbox"
              checked={$searchFilters.hybrid}
              on:change={(e) =>
                handleFilterChange("hybrid", e.currentTarget.checked)}
              disabled={$searchLoading}
              class="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <span class="text-gray-700">Hybrid Search</span>
          </label>
        </div>

        <!-- Advanced Options Toggle -->
        <Button
          variant="ghost"
          size="sm"
          onClick={toggleAdvanced}
          class="flex items-center gap-2 whitespace-nowrap"
        >
          <Icon icon="material-symbols:tune" class="w-4 h-4" />
          <span>Advanced</span>
          <Icon
            icon={showAdvanced
              ? "material-symbols:expand-less"
              : "material-symbols:expand-more"}
            class="w-4 h-4 transition-transform"
          />
        </Button>
      </div>

      <!-- Advanced Options Panel -->
      {#if showAdvanced}
        <div
          class="border-t pt-4 space-y-4 bg-gray-50 -mx-6 px-6 py-4 rounded-b-lg"
        >
          <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <!-- Limit -->
            <div class="space-y-1">
              <label
                for="search-limit"
                class="block text-sm font-medium text-gray-700"
              >
                Result Limit
              </label>
              <FormInput
                id="search-limit"
                type="number"
                min="1"
                max="100"
                value={$searchFilters.limit.toString()}
                onInput={(value) =>
                  handleFilterChange("limit", parseInt(value.toString()) || 10)}
                disabled={$searchLoading}
                class="w-full"
              />
            </div>

            <!-- Min Score -->
            <div class="space-y-1">
              <label
                for="search-min-score"
                class="block text-sm font-medium text-gray-700"
              >
                Min Score
              </label>
              <FormInput
                id="search-min-score"
                type="number"
                min="0"
                max="1"
                step="0.1"
                value={$searchFilters.min_score.toString()}
                onInput={(value) =>
                  handleFilterChange(
                    "min_score",
                    parseFloat(value.toString()) || 0,
                  )}
                disabled={$searchLoading}
                class="w-full"
              />
            </div>

            <!-- Fusion Method (only for hybrid) -->
            <div class="space-y-1">
              <label
                for="search-fusion-method"
                class="block text-sm font-medium text-gray-700"
              >
                Fusion Method
              </label>
              <FormSelect
                id="search-fusion-method"
                options={fusionMethods}
                value={$searchFilters.fusion_method}
                onChange={(value) => handleFilterChange("fusion_method", value)}
                disabled={$searchLoading || !$searchFilters.hybrid}
                class="w-full"
              />
            </div>

            <!-- Group by Article -->
            <div class="flex items-end pb-2">
              <label class="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={$searchFilters.group_by_article}
                  on:change={(e) =>
                    handleFilterChange(
                      "group_by_article",
                      e.currentTarget.checked,
                    )}
                  disabled={$searchLoading}
                  class="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <span class="text-gray-700">Group by Article</span>
              </label>
            </div>
          </div>

          <!-- Advanced Options Actions -->
          <div class="flex justify-end gap-2 pt-2 border-t border-gray-200">
            <Button
              variant="ghost"
              size="sm"
              onClick={resetFilters}
              disabled={$searchLoading}
              class="flex items-center gap-1"
            >
              <Icon icon="material-symbols:refresh" class="w-4 h-4" />
              Reset
            </Button>
          </div>
        </div>
      {/if}
    </form>

    <!-- Search History -->
    {#if showHistory && recentSearches.length > 0}
      <div class="border-t pt-4">
        <div class="flex items-center justify-between mb-3">
          <h3 class="text-sm font-medium text-gray-900">Recent Searches</h3>
          <Button
            variant="ghost"
            size="xs"
            onClick={() => searchActions.clearHistory()}
            class="text-gray-500 hover:text-gray-700"
          >
            Clear
          </Button>
        </div>

        <div class="flex flex-wrap gap-2">
          {#each recentSearches as historyItem (historyItem.id)}
            <button
              class="inline-flex items-center gap-2 px-3 py-1.5 text-xs bg-white border border-gray-200 rounded-full hover:bg-gray-50 hover:border-gray-300 transition-colors"
              on:click={() => searchFromHistory(historyItem)}
              disabled={$searchLoading}
            >
              <Icon
                icon="material-symbols:history"
                class="w-3 h-3 text-gray-400"
              />
              <span class="max-w-32 truncate">{historyItem.query}</span>
              <span class="text-gray-400">({historyItem.results_count})</span>
            </button>
          {/each}
        </div>
      </div>
    {/if}

    <!-- <!-- Quick Search Tips --> -->
    <!-- <div class="text-xs text-gray-500 space-y-1 bg-blue-50 p-3 rounded-lg"> -->
    <!--   <div class="font-medium text-blue-900 mb-2">Search Tips:</div> -->
    <!--   <div>• Use <kbd class="px-1 py-0.5 bg-white rounded border text-xs">Ctrl+Enter</kbd> to search quickly</div> -->
    <!--   <div>• Enable "Hybrid Search" for better semantic + keyword matching</div> -->
    <!--   <div>• Group results by article to see related content together</div> -->
    <!-- </div> -->
  </div>
</Card>

<style>
  kbd {
    font-family: ui-monospace, SFMono-Regular, "SF Mono", Consolas,
      "Liberation Mono", Menlo, monospace;
  }
</style>
