<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import Icon from '@iconify/svelte';
  
  // Components
  import Card from '../common/Card.svelte';
  import Button from '../common/Button.svelte';
  import LoadingSpinner from '../common/LoadingSpinner.svelte';
  import SearchInterface from '../search/SearchInterface.svelte';
  import SearchResults from '../search/SearchResults.svelte';
  import RecordsTable from './RecordsTable.svelte';
  import AddRecordsModal from './AddRecordsModal.svelte';
  
  // Stores and services
  import { 
    collectionsActions,
    collectionStatsMap
  } from '../../stores/collections';
  import { 
    searchActions, 
    searchFilters,
    searchResults,
    searchLoading,
    currentSearchResponse
  } from '../../stores/search';
  import { notificationActions } from '../../stores/notifications';
  import api, { type CollectionRecord, type CollectionRecordsResponse } from '../../services/api';
  
  // Props
  export let collectionName: string;
  
  // Local state
  let collectionStats: any = null;
  let showAddRecordsModal = false;
  let selectedRecords = new Set<string>();
  let showDeleteConfirm = false;
  let recordsToDelete: string[] = [];
  let isDeleting = false;
  let viewMode: 'detailed' | 'compact' | 'cards' = 'detailed';
  let activeTab: 'search' | 'browse' = 'browse';

  // Records state
  let records: CollectionRecord[] = [];
  let recordsLoading = false;
  let recordsError = '';
  let currentPage = 1;
  let pageSize = 20;
  let totalRecords = 0;
  let totalPages = 1;
  
  // Stats loading
  let statsLoading = true;
  let statsError = '';
  
  // Get collection stats from store
  $: collectionStats = $collectionStatsMap.get(collectionName);
  
  // Load records for browsing
  const loadRecords = async (page: number = currentPage) => {
    recordsLoading = true;
    recordsError = '';
    
    try {
      const response = await api.getCollectionRecords(collectionName, page, pageSize);
      records = response.records;
      totalRecords = response.total;
      totalPages = response.total_pages;
      currentPage = response.page;
    } catch (error) {
      console.error('Failed to load records:', error);
      recordsError = error instanceof Error ? error.message : 'Failed to load records';
    } finally {
      recordsLoading = false;
    }
  };

  // Load collection stats on mount
  onMount(async () => {
    statsLoading = true;
    statsError = '';
    
    try {
      // Load collection stats if not already in store
      if (!collectionStats) {
        await collectionsActions.loadCollectionStats(collectionName);
      }
      
      // Load records for browse mode
      await loadRecords();
      
      // Set search filter to this collection
      searchActions.updateFilters({ collection: collectionName });
      
      // Clear any existing search results
      searchActions.clearResults();
    } catch (error) {
      console.error('Failed to load collection stats:', error);
      statsError = error instanceof Error ? error.message : 'Failed to load collection stats';
    } finally {
      statsLoading = false;
    }
  });
  
  // Clean up on destroy
  onDestroy(() => {
    // Reset search filters
    searchActions.updateFilters({ collection: 'articles' });
    searchActions.clearResults();
  });
  
  // Format numbers
  const formatNumber = (num: number): string => {
    if (num >= 1000000) {
      return (num / 1000000).toFixed(1) + 'M';
    } else if (num >= 1000) {
      return (num / 1000).toFixed(1) + 'K';
    }
    return num.toLocaleString();
  };
  
  // Handle search
  const handleSearch = () => {
    // SearchInterface will handle the actual search
    // We just ensure the collection filter is set
    searchActions.updateFilters({ collection: collectionName });
  };
  
  // Handle record selection from search results
  const handleRecordSelection = (event: CustomEvent<{ selectedIds: Set<string> }>) => {
    selectedRecords = event.detail.selectedIds;
  };

  // Records table event handlers
  const handleRecordsTableDelete = async (event: CustomEvent<{ recordId: string }>) => {
    const { recordId } = event.detail;
    
    try {
      await api.deleteRecord(collectionName, recordId);
      
      notificationActions.success('Success', 'Record deleted successfully');
      
      // Reload records
      await loadRecords(currentPage);
      
      // Refresh collection stats
      await collectionsActions.loadCollectionStats(collectionName);
    } catch (error) {
      console.error('Failed to delete record:', error);
      notificationActions.error(
        'Delete Failed',
        error instanceof Error ? error.message : 'Failed to delete record'
      );
    }
  };

  const handleRecordsTableBulkDelete = async (event: CustomEvent<{ recordIds: string[] }>) => {
    const { recordIds } = event.detail;
    
    try {
      // Delete records one by one (could be optimized with bulk delete endpoint)
      for (const recordId of recordIds) {
        await api.deleteRecord(collectionName, recordId);
      }
      
      notificationActions.success(
        'Success', 
        `Deleted ${recordIds.length} record${recordIds.length === 1 ? '' : 's'} successfully`
      );
      
      // Clear selection and reload
      selectedRecords.clear();
      selectedRecords = selectedRecords;
      await loadRecords(currentPage);
      
      // Refresh collection stats
      await collectionsActions.loadCollectionStats(collectionName);
    } catch (error) {
      console.error('Failed to delete records:', error);
      notificationActions.error(
        'Delete Failed',
        error instanceof Error ? error.message : 'Failed to delete records'
      );
    }
  };

  const handleRecordsTablePageChange = async (event: CustomEvent<{ page: number }>) => {
    const { page } = event.detail;
    await loadRecords(page);
  };

  const handleRecordsTableToggleSelect = (event: CustomEvent<{ recordId: string }>) => {
    const { recordId } = event.detail;
    if (selectedRecords.has(recordId)) {
      selectedRecords.delete(recordId);
    } else {
      selectedRecords.add(recordId);
    }
    selectedRecords = selectedRecords;
  };

  const handleRecordsTableToggleSelectAll = () => {
    if (selectedRecords.size === records.length) {
      // Unselect all
      selectedRecords.clear();
    } else {
      // Select all visible records
      selectedRecords = new Set(records.map(r => r.id));
    }
    selectedRecords = selectedRecords;
  };
  
  // Delete selected records
  const confirmDeleteSelected = () => {
    if (selectedRecords.size === 0) return;
    recordsToDelete = Array.from(selectedRecords);
    showDeleteConfirm = true;
  };
  
  const cancelDelete = () => {
    recordsToDelete = [];
    showDeleteConfirm = false;
  };
  
  const executeDelete = async () => {
    isDeleting = true;
    
    try {
      // TODO: Implement bulk delete API endpoint
      // For now, we'll show a notification that this feature is pending
      notificationActions.info(
        'Feature Pending',
        'Bulk delete functionality will be implemented with the backend API updates.'
      );
      
      // Clear selection
      selectedRecords.clear();
      selectedRecords = selectedRecords;
    } catch (error) {
      console.error('Failed to delete records:', error);
      notificationActions.error(
        'Delete Failed',
        error instanceof Error ? error.message : 'Failed to delete records'
      );
    } finally {
      isDeleting = false;
      cancelDelete();
    }
  };
  
  // Add records handlers
  const openAddRecordsModal = () => {
    showAddRecordsModal = true;
  };
  
  const handleRecordsAdded = async (event: CustomEvent<{ count: number }>) => {
    const { count } = event.detail;
    notificationActions.success(
      'Records Added',
      `Successfully added ${count} record${count === 1 ? '' : 's'} to ${collectionName}`
    );
    
    // Refresh collection stats
    await collectionsActions.loadCollectionStats(collectionName);
    
    // Refresh records if in browse mode
    if (activeTab === 'browse') {
      await loadRecords(currentPage);
    }
    
    // Refresh search results if in search mode and has results
    if (activeTab === 'search' && $searchResults.length > 0) {
      await searchActions.executeSearch();
    }
  };
  
  // Refresh collection data
  const refreshCollection = async () => {
    statsLoading = true;
    try {
      await collectionsActions.loadCollectionStats(collectionName);
      
      if (activeTab === 'browse') {
        await loadRecords(currentPage);
      } else if ($currentSearchResponse) {
        await searchActions.executeSearch();
      }
    } catch (error) {
      notificationActions.error(
        'Refresh Failed',
        error instanceof Error ? error.message : 'Failed to refresh collection'
      );
    } finally {
      statsLoading = false;
    }
  };
</script>

<div class="space-y-6">
  <!-- Collection Header -->
  <Card>
    <div class="space-y-4">
      <!-- Title and Actions -->
      <div class="flex items-center justify-between">
        <div>
          <h2 class="text-2xl font-bold text-gray-900">{collectionName}</h2>
          {#if collectionStats?.description}
            <p class="text-gray-600 mt-1">{collectionStats.description}</p>
          {/if}
        </div>
        
        <div class="flex items-center gap-3">
          <Button
            variant="primary"
            onClick={openAddRecordsModal}
            disabled={statsLoading}
          >
            <Icon icon="material-symbols:add" class="w-4 h-4 mr-1" />
            Add Records
          </Button>
          
          <Button
            variant="ghost"
            onClick={refreshCollection}
            loading={statsLoading}
            ariaLabel="Refresh collection"
          >
            <Icon icon="material-symbols:refresh" class="w-4 h-4" />
          </Button>
        </div>
      </div>
      
      <!-- Stats -->
      {#if statsLoading && !collectionStats}
        <div class="flex items-center justify-center py-8">
          <LoadingSpinner size="lg" />
        </div>
      {:else if statsError}
        <div class="text-center py-8">
          <div class="text-red-500 mb-4">
            <Icon icon="material-symbols:error" class="w-12 h-12 mx-auto" />
          </div>
          <p class="text-gray-800 font-medium">{statsError}</p>
        </div>
      {:else if collectionStats}
        <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
          <!-- Vectors Count -->
          <div class="bg-purple-50 border border-purple-200 rounded-lg p-4">
            <div class="flex items-center justify-between">
              <div>
                <p class="text-sm text-purple-600 font-medium">Total Vectors</p>
                <p class="text-2xl font-bold text-purple-700">
                  {formatNumber(collectionStats.points_count)}
                </p>
              </div>
              <Icon icon="material-symbols:bar-chart" class="w-8 h-8 text-purple-400" />
            </div>
          </div>
          
          <!-- Embedding Model -->
          <div class="bg-green-50 border border-green-200 rounded-lg p-4">
            <div class="flex items-center justify-between">
              <div>
                <p class="text-sm text-green-600 font-medium">Embedding Model</p>
                <p class="text-lg font-semibold text-green-700 truncate">
                  {collectionStats.embedding_model || 'Not specified'}
                </p>
              </div>
              <Icon icon="material-symbols:model-training" class="w-8 h-8 text-green-400" />
            </div>
          </div>
          
          <!-- Vector Config -->
          <div class="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
            <div class="flex items-center justify-between">
              <div>
                <p class="text-sm text-yellow-600 font-medium">Vector Config</p>
                <p class="text-lg font-semibold text-yellow-700">
                  {collectionStats.config?.vector_size || 0}D • {collectionStats.config?.distance || 'Unknown'}
                </p>
              </div>
              <Icon icon="material-symbols:functions" class="w-8 h-8 text-yellow-400" />
            </div>
          </div>
        </div>
        
        <!-- Status -->
        <div class="flex items-center gap-2 text-sm">
          <span class="text-gray-600">Status:</span>
          <span class="px-2 py-1 rounded-full text-xs font-medium
            {collectionStats.status === 'ready' || collectionStats.status === 'green' 
              ? 'bg-green-100 text-green-700' 
              : 'bg-yellow-100 text-yellow-700'}">
            {collectionStats.status}
          </span>
          {#if collectionStats.created_at}
            <span class="text-gray-500">
              Created {new Date(collectionStats.created_at).toLocaleDateString()}
            </span>
          {/if}
        </div>
      {/if}
    </div>
  </Card>
  
  <!-- Records Interface -->
  <Card>
    <div slot="header" class="flex items-center justify-between">
      <div class="flex items-center gap-6">
        <h3 class="text-lg font-semibold text-gray-900">Collection Records</h3>
        
        <!-- Tab Navigation -->
        <div class="flex items-center bg-gray-100 rounded-lg p-1">
          <button
            class="px-3 py-1 text-sm font-medium rounded-md transition-colors {activeTab === 'browse' 
              ? 'bg-white text-blue-600 shadow-sm' 
              : 'text-gray-600 hover:text-gray-900'}"
            on:click={() => activeTab = 'browse'}
          >
            <Icon icon="material-symbols:table-rows" class="w-4 h-4 mr-1 inline" />
            Browse ({totalRecords})
          </button>
          <button
            class="px-3 py-1 text-sm font-medium rounded-md transition-colors {activeTab === 'search' 
              ? 'bg-white text-blue-600 shadow-sm' 
              : 'text-gray-600 hover:text-gray-900'}"
            on:click={() => activeTab = 'search'}
          >
            <Icon icon="material-symbols:search" class="w-4 h-4 mr-1 inline" />
            Search
          </button>
        </div>
      </div>
      
      {#if selectedRecords.size > 0}
        <div class="flex items-center gap-3">
          <span class="text-sm text-gray-600">
            {selectedRecords.size} selected
          </span>
          <Button
            variant="danger"
            size="sm"
            onClick={confirmDeleteSelected}
          >
            <Icon icon="material-symbols:delete" class="w-4 h-4 mr-1" />
            Delete Selected
          </Button>
        </div>
      {/if}
    </div>
    
    <div class="space-y-4">
      {#if activeTab === 'browse'}
        <!-- Browse Mode - Records Table -->
        <RecordsTable
          {records}
          loading={recordsLoading}
          total={totalRecords}
          page={currentPage}
          pageSize={pageSize}
          totalPages={totalPages}
          selectedRecords={selectedRecords}
          collectionName={collectionName}
          on:delete={handleRecordsTableDelete}
          on:bulkDelete={handleRecordsTableBulkDelete}
          on:loadPage={handleRecordsTablePageChange}
          on:toggleSelect={handleRecordsTableToggleSelect}
          on:toggleSelectAll={handleRecordsTableToggleSelectAll}
        />
      {:else}
        <!-- Search Mode -->
        <!-- Search Bar -->
        <SearchInterface 
          compact={true}
          showFilters={false}
          hideCollectionSelector={true}
          placeholder={`Search in ${collectionName}...`}
          on:search={handleSearch}
        />
        
        <!-- Results -->
        {#if $searchLoading || $searchResults.length > 0 || $currentSearchResponse}
          <SearchResults
            viewMode={viewMode}
            showArticleGrouping={false}
            enableActions={true}
            on:selectionChange={handleRecordSelection}
          />
        {:else}
          <!-- Empty state -->
          <div class="text-center py-12">
            <div class="text-gray-400 mb-4">
              <Icon icon="material-symbols:search" class="w-12 h-12 mx-auto" />
            </div>
            <h3 class="text-lg font-medium text-gray-900 mb-2">Search Collection</h3>
            <p class="text-gray-600 max-w-md mx-auto">
              Enter a search query above to find records in this collection.
            </p>
          </div>
        {/if}
      {/if}
    </div>
  </Card>
</div>

<!-- Add Records Modal -->
<AddRecordsModal
  bind:show={showAddRecordsModal}
  collectionName={collectionName}
  on:recordsAdded={handleRecordsAdded}
/>

<!-- Delete Confirmation Modal -->
{#if showDeleteConfirm}
  <div class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
    <div class="bg-white rounded-lg max-w-md w-full p-6">
      <div class="flex items-center gap-3 mb-4">
        <div class="text-red-600">
          <Icon icon="material-symbols:warning" class="w-8 h-8" />
        </div>
        <h3 class="text-lg font-semibold text-gray-900">Delete Records</h3>
      </div>
      
      <p class="text-gray-600 mb-6">
        Are you sure you want to delete {recordsToDelete.length} record{recordsToDelete.length === 1 ? '' : 's'}? 
        This action cannot be undone.
      </p>
      
      <div class="flex justify-end gap-3">
        <Button variant="secondary" onClick={cancelDelete}>
          Cancel
        </Button>
        <Button 
          variant="danger" 
          onClick={executeDelete}
          loading={isDeleting}
        >
          Delete Records
        </Button>
      </div>
    </div>
  </div>
{/if}