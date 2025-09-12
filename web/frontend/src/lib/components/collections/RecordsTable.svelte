<script lang="ts">
  import { createEventDispatcher } from "svelte";
  import Icon from "@iconify/svelte";
  
  import Button from "../common/Button.svelte";
  import LoadingSpinner from "../common/LoadingSpinner.svelte";
  
  // Types
  interface CollectionRecord {
    id: string;
    title: string;
    content: string;
    metadata?: any;
    created_at?: string;
  }
  
  interface CollectionRecordsResponse {
    records: CollectionRecord[];
    total: number;
    page: number;
    page_size: number;
    total_pages: number;
  }

  // Props
  export let records: CollectionRecord[] = [];
  export let loading = false;
  export let total = 0;
  export let page = 1;
  export let pageSize = 20;
  export let totalPages = 1;
  export let selectedRecords: Set<string> = new Set();

  // Events
  const dispatch = createEventDispatcher<{
    delete: { recordId: string };
    bulkDelete: { recordIds: string[] };
    loadPage: { page: number };
    toggleSelect: { recordId: string };
    toggleSelectAll: {};
  }>();

  // Local state
  let selectAll = false;

  // Reactive statements
  $: allRecordsSelected = records.length > 0 && records.every(r => selectedRecords.has(r.id));
  $: someRecordsSelected = records.some(r => selectedRecords.has(r.id));

  // Functions
  function handleSelectAll() {
    dispatch('toggleSelectAll');
  }

  function handleSelectRecord(recordId: string) {
    dispatch('toggleSelect', { recordId });
  }

  function handleDeleteRecord(recordId: string) {
    if (confirm('Are you sure you want to delete this record?')) {
      dispatch('delete', { recordId });
    }
  }

  function handleBulkDelete() {
    const recordIds = Array.from(selectedRecords);
    if (recordIds.length === 0) return;
    
    if (confirm(`Are you sure you want to delete ${recordIds.length} record(s)?`)) {
      dispatch('bulkDelete', { recordIds });
    }
  }

  function handlePageChange(newPage: number) {
    dispatch('loadPage', { page: newPage });
  }

  function formatDate(dateString: string | undefined): string {
    if (!dateString) return 'N/A';
    try {
      return new Date(dateString).toLocaleString();
    } catch {
      return 'Invalid date';
    }
  }

  function truncateText(text: string, maxLength: number = 100): string {
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
  }
</script>

<div class="space-y-4">
  <!-- Bulk Actions Bar -->
  {#if selectedRecords.size > 0}
    <div class="bg-blue-50 border border-blue-200 rounded-lg p-3 flex items-center justify-between">
      <div class="flex items-center gap-2">
        <Icon icon="material-symbols:info" class="w-5 h-5 text-blue-600" />
        <span class="text-sm font-medium text-blue-900">
          {selectedRecords.size} record(s) selected
        </span>
      </div>
      
      <div class="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => selectedRecords.clear()}
          class="text-blue-700 border-blue-300 hover:bg-blue-100"
        >
          Clear Selection
        </Button>
        <Button
          variant="danger"
          size="sm"
          onClick={handleBulkDelete}
          class="flex items-center gap-1"
        >
          <Icon icon="material-symbols:delete" class="w-4 h-4" />
          Delete Selected
        </Button>
      </div>
    </div>
  {/if}

  <!-- Records Table -->
  <div class="bg-white border border-gray-200 rounded-lg overflow-hidden">
    {#if loading}
      <div class="p-8 text-center">
        <LoadingSpinner size="lg" />
        <p class="mt-2 text-sm text-gray-600">Loading records...</p>
      </div>
    {:else if records.length === 0}
      <div class="p-8 text-center">
        <Icon icon="material-symbols:description" class="w-12 h-12 mx-auto text-gray-400" />
        <h3 class="mt-2 text-sm font-medium text-gray-900">No records found</h3>
        <p class="mt-1 text-sm text-gray-500">
          This collection doesn't have any records yet.
        </p>
      </div>
    {:else}
      <div class="overflow-x-auto">
        <table class="min-w-full divide-y divide-gray-200">
          <thead class="bg-gray-50">
            <tr>
              <th class="w-12 px-4 py-3">
                <input
                  type="checkbox"
                  checked={allRecordsSelected}
                  indeterminate={someRecordsSelected && !allRecordsSelected}
                  on:change={handleSelectAll}
                  class="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
              </th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Title
              </th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Content
              </th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Created
              </th>
              <th class="w-24 px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                Actions
              </th>
            </tr>
          </thead>
          <tbody class="bg-white divide-y divide-gray-200">
            {#each records as record (record.id)}
              <tr class="hover:bg-gray-50 transition-colors">
                <td class="px-4 py-4">
                  <input
                    type="checkbox"
                    checked={selectedRecords.has(record.id)}
                    on:change={() => handleSelectRecord(record.id)}
                    class="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                </td>
                <td class="px-4 py-4">
                  <div class="text-sm font-medium text-gray-900 max-w-xs">
                    {truncateText(record.title, 80)}
                  </div>
                </td>
                <td class="px-4 py-4">
                  <div class="text-sm text-gray-700 max-w-md">
                    {truncateText(record.content, 150)}
                  </div>
                </td>
                <td class="px-4 py-4 text-sm text-gray-500">
                  {formatDate(record.created_at)}
                </td>
                <td class="px-4 py-4 text-right">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleDeleteRecord(record.id)}
                    class="text-red-600 hover:text-red-700 hover:bg-red-50"
                    ariaLabel={`Delete record: ${record.title}`}
                  >
                    <Icon icon="material-symbols:delete" class="w-4 h-4" />
                  </Button>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>

      <!-- Pagination -->
      {#if totalPages > 1}
        <div class="bg-gray-50 px-4 py-3 flex items-center justify-between border-t border-gray-200">
          <div class="text-sm text-gray-700">
            Showing page {page} of {totalPages} ({total} total records)
          </div>
          
          <div class="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => handlePageChange(page - 1)}
              disabled={page <= 1}
              class="flex items-center gap-1"
            >
              <Icon icon="material-symbols:chevron-left" class="w-4 h-4" />
              Previous
            </Button>
            
            <div class="flex items-center gap-1">
              {#each Array.from({length: Math.min(5, totalPages)}, (_, i) => {
                const startPage = Math.max(1, page - 2);
                return startPage + i;
              }).filter(p => p <= totalPages) as pageNum}
                <Button
                  variant={pageNum === page ? "primary" : "ghost"}
                  size="sm"
                  onClick={() => handlePageChange(pageNum)}
                  class="w-8 h-8 p-0 justify-center"
                >
                  {pageNum}
                </Button>
              {/each}
            </div>
            
            <Button
              variant="outline"
              size="sm"
              onClick={() => handlePageChange(page + 1)}
              disabled={page >= totalPages}
              class="flex items-center gap-1"
            >
              Next
              <Icon icon="material-symbols:chevron-right" class="w-4 h-4" />
            </Button>
          </div>
        </div>
      {/if}
    {/if}
  </div>
</div>