<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import Card from '../common/Card.svelte';
  import Button from '../common/Button.svelte';
  import LoadingSpinner from '../common/LoadingSpinner.svelte';
  import StatsCard from './StatsCard.svelte';
  import Icon from '@iconify/svelte';
  import { 
    collectionsStore,
    collectionsActions,
    collections,
    collectionsLoading,
    collectionsError,
    operationInProgress,
    collectionsStats
  } from '../../stores/collections';
  import { notificationActions } from '../../stores/notifications';

  // Component state
  export let viewMode: 'grid' | 'list' = 'grid';
  export let showStats: boolean = true;
  export let compact: boolean = false;

  // Local state
  let searchQuery = '';
  let selectedCollections = new Set<string>();
  let showDeleteConfirm = false;
  let collectionToDelete: string | null = null;

  // Reactive filtering
  $: filteredCollections = searchQuery 
    ? $collections.filter(c => 
        c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        c.status.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : $collections;

  // Icons
  const databaseIcon = 'material-symbols:database';
  const vectorIcon = 'material-symbols:bar-chart';
  const pointsIcon = 'material-symbols:star';

  // Status badge classes
  const getStatusBadgeClass = (status: string): string => {
    switch (status.toLowerCase()) {
      case 'ready':
      case 'active':
      case 'green':
        return 'status-healthy';
      case 'error':
      case 'failed':
      case 'red':
        return 'status-unhealthy';
      default:
        return 'status-unknown';
    }
  };

  // Format numbers
  const formatNumber = (num: number): string => {
    if (num >= 1000000) {
      return (num / 1000000).toFixed(1) + 'M';
    } else if (num >= 1000) {
      return (num / 1000).toFixed(1) + 'K';
    }
    return num.toLocaleString();
  };

  // Handle collection selection
  const toggleSelection = (collectionName: string) => {
    if (selectedCollections.has(collectionName)) {
      selectedCollections.delete(collectionName);
    } else {
      selectedCollections.add(collectionName);
    }
    selectedCollections = selectedCollections; // Trigger reactivity
  };

  const selectAll = () => {
    selectedCollections = new Set(filteredCollections.map(c => c.name));
  };

  const clearSelection = () => {
    selectedCollections = new Set();
  };

  // Handle delete collection
  const confirmDelete = (collectionName: string) => {
    collectionToDelete = collectionName;
    showDeleteConfirm = true;
  };

  const cancelDelete = () => {
    collectionToDelete = null;
    showDeleteConfirm = false;
  };

  const executeDelete = async () => {
    if (!collectionToDelete) return;
    
    const success = await collectionsActions.deleteCollection(collectionToDelete);
    if (success) {
      notificationActions.success('Collection Deleted', `Collection "${collectionToDelete}" has been successfully deleted.`);
      selectedCollections.delete(collectionToDelete);
      selectedCollections = selectedCollections;
    } else {
      notificationActions.error('Delete Failed', `Failed to delete collection "${collectionToDelete}".`);
    }
    
    cancelDelete();
  };

  // Handle refresh
  const handleRefresh = async () => {
    await collectionsActions.refresh();
    if (showStats) {
      await collectionsActions.loadAllCollectionStats();
    }
  };

  // View collection details
  const viewCollection = (collectionName: string) => {
    collectionsActions.selectCollection(
      $collections.find(c => c.name === collectionName) || null
    );
  };

  // Lifecycle hooks
  onMount(async () => {
    await collectionsActions.initialize();
    if (showStats) {
      await collectionsActions.loadAllCollectionStats();
    }
  });

  onDestroy(() => {
    collectionsActions.reset();
  });
</script>

<div class="space-y-6">
  <!-- Stats Cards (if enabled) -->
  {#if showStats}
    <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
      <StatsCard
        title="Total Collections"
        value={$collectionsStats.total}
        icon={databaseIcon}
        color="blue"
        compact={compact}
      />
      <StatsCard
        title="Active Collections"
        value={$collectionsStats.activeCollections}
        subtitle="Ready to use"
        icon={vectorIcon}
        color="green"
        compact={compact}
      />
      <StatsCard
        title="Total Points"
        value={$collectionsStats.totalPoints}
        subtitle="All collections"
        icon={pointsIcon}
        color="purple"
        compact={compact}
      />
      <StatsCard
        title="Total Vectors"
        value={$collectionsStats.totalVectors}
        subtitle="Embedded data"
        icon={vectorIcon}
        color="yellow"
        compact={compact}
      />
    </div>
  {/if}

  <!-- Main Collections Card -->
  <Card>
    <div slot="header" class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div class="flex items-center gap-3">
        <h2 class="text-lg font-semibold text-gray-900">Collections</h2>
        {#if $collections.length > 0}
          <span class="text-sm text-gray-500">
            {filteredCollections.length} of {$collections.length}
          </span>
        {/if}
      </div>

      <div class="flex items-center gap-3">
        <!-- Search -->
        <div class="relative">
          <Icon icon="material-symbols:search" class="w-4 h-4 absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Search collections..."
            bind:value={searchQuery}
            class="pl-10 pr-4 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>

        <!-- View mode toggle -->
        <div class="flex border border-gray-300 rounded-lg">
          <Button
            variant={viewMode === 'grid' ? 'primary' : 'ghost'}
            size="sm"
            onClick={() => viewMode = 'grid'}
            ariaLabel="Grid view"
          >
            <Icon icon="material-symbols:grid-view" class="w-4 h-4" />
          </Button>
          <Button
            variant={viewMode === 'list' ? 'primary' : 'ghost'}
            size="sm"
            onClick={() => viewMode = 'list'}
            ariaLabel="List view"
          >
            <Icon icon="material-symbols:view-list" class="w-4 h-4" />
          </Button>
        </div>

        <!-- Refresh -->
        <Button
          variant="ghost"
          size="sm"
          loading={$collectionsLoading}
          onClick={handleRefresh}
          ariaLabel="Refresh collections"
        >
          <Icon icon="material-symbols:refresh" class="w-4 h-4" />
        </Button>
      </div>
    </div>

    <!-- Loading state -->
    {#if $collectionsLoading && $collections.length === 0}
      <div class="flex items-center justify-center py-12">
        <LoadingSpinner size="lg" showLabel={true} label="Loading collections..." />
      </div>

    <!-- Error state -->
    {:else if $collectionsError}
      <div class="text-center py-8">
        <div class="text-red-600 mb-4">
          <Icon icon="material-symbols:warning" class="w-12 h-12 mx-auto mb-2" />
        </div>
        <h3 class="text-lg font-medium text-gray-900 mb-2">Collections Error</h3>
        <p class="text-gray-600 mb-4">{$collectionsError}</p>
        <Button onClick={handleRefresh} variant="primary">
          Try Again
        </Button>
      </div>

    <!-- Empty state -->
    {:else if filteredCollections.length === 0 && $collections.length === 0}
      <div class="text-center py-12">
        <div class="text-gray-400 mb-4">
          <Icon icon={databaseIcon} class="w-12 h-12 mx-auto" />
        </div>
        <h3 class="text-lg font-medium text-gray-900 mb-2">No Collections</h3>
        <p class="text-gray-600 mb-4">No collections found. Create your first collection to get started.</p>
        <Button variant="primary">
          Create Collection
        </Button>
      </div>

    <!-- No search results -->
    {:else if filteredCollections.length === 0}
      <div class="text-center py-8">
        <div class="text-gray-400 mb-4">
          <Icon icon="material-symbols:search-off" class="w-12 h-12 mx-auto" />
        </div>
        <h3 class="text-lg font-medium text-gray-900 mb-2">No Results</h3>
        <p class="text-gray-600 mb-4">No collections match your search criteria.</p>
        <Button variant="secondary" onClick={() => searchQuery = ''}>
          Clear Search
        </Button>
      </div>

    <!-- Collections Grid/List -->
    {:else}
      {#if selectedCollections.size > 0}
        <div class="flex items-center justify-between p-4 bg-blue-50 border border-blue-200 rounded-lg mb-4">
          <span class="text-sm text-blue-800">
            {selectedCollections.size} collection{selectedCollections.size === 1 ? '' : 's'} selected
          </span>
          <div class="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={clearSelection}>
              Clear
            </Button>
            <Button variant="danger" size="sm" disabled={selectedCollections.size === 0}>
              Delete Selected
            </Button>
          </div>
        </div>
      {/if}

      <div class={viewMode === 'grid' ? 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4' : 'space-y-3'}>
        {#each filteredCollections as collection (collection.name)}
          <div class={viewMode === 'list' ? 'border border-gray-200 rounded-lg' : ''}>
            <Card
              padding="md"
              hoverable={true}
              clickable={true}
              onClick={() => viewCollection(collection.name)}
              fullHeight={viewMode === 'grid'}
            >
              <div class="flex items-start justify-between mb-3">
                <div class="flex items-center gap-3 min-w-0 flex-1">
                  <!-- Selection checkbox -->
                  <input
                    type="checkbox"
                    checked={selectedCollections.has(collection.name)}
                    on:change={() => toggleSelection(collection.name)}
                    on:click|stopPropagation
                    class="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  
                  <!-- Collection icon -->
                  <div class="flex-shrink-0 text-blue-500">
                    <Icon icon={databaseIcon} class="w-5 h-5" />
                  </div>
                  
                  <!-- Collection name -->
                  <div class="min-w-0 flex-1">
                    <h4 class="text-lg font-medium text-gray-900 truncate">
                      {collection.name}
                    </h4>
                  </div>
                </div>

                <!-- Status badge -->
                <span class="{getStatusBadgeClass(collection.status)}">
                  {collection.status}
                </span>
              </div>

              <!-- Collection stats -->
              <div class="grid grid-cols-2 gap-4 mb-4">
                <div class="text-center">
                  <div class="text-2xl font-bold text-purple-600">
                    {formatNumber(collection.points_count)}
                  </div>
                  <div class="text-sm text-gray-600">Points</div>
                </div>
                <div class="text-center">
                  <div class="text-2xl font-bold text-blue-600">
                    {formatNumber(collection.vectors_count)}
                  </div>
                  <div class="text-sm text-gray-600">Vectors</div>
                </div>
              </div>

              <!-- Actions -->
              <div class="flex items-center justify-between pt-3 border-t border-gray-200">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={(e) => { e.stopPropagation(); viewCollection(collection.name); }}
                >
                  View Details
                </Button>
                <Button
                  variant="danger"
                  size="sm"
                  onClick={(e) => { e.stopPropagation(); confirmDelete(collection.name); }}
                  disabled={$operationInProgress === 'delete'}
                >
                  Delete
                </Button>
              </div>
            </Card>
          </div>
        {/each}
      </div>
    {/if}
  </Card>
</div>

<!-- Delete Confirmation Modal -->
{#if showDeleteConfirm && collectionToDelete}
  <div class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
    <div class="bg-white rounded-lg max-w-md w-full p-6">
      <div class="flex items-center gap-3 mb-4">
        <div class="text-red-600">
          <Icon icon="material-symbols:warning" class="w-8 h-8" />
        </div>
        <h3 class="text-lg font-semibold text-gray-900">Delete Collection</h3>
      </div>
      
      <p class="text-gray-600 mb-6">
        Are you sure you want to delete the collection <strong>"{collectionToDelete}"</strong>? 
        This action cannot be undone and all data in this collection will be permanently lost.
      </p>
      
      <div class="flex justify-end gap-3">
        <Button variant="secondary" onClick={cancelDelete}>
          Cancel
        </Button>
        <Button 
          variant="danger" 
          onClick={executeDelete}
          loading={$operationInProgress === 'delete'}
        >
          Delete Collection
        </Button>
      </div>
    </div>
  </div>
{/if}