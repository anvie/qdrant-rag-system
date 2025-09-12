<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import Icon from '@iconify/svelte';
  
  // Components
  import Modal from '../common/Modal.svelte';
  import Button from '../common/Button.svelte';
  import FormInput from '../common/FormInput.svelte';
  import LoadingSpinner from '../common/LoadingSpinner.svelte';
  
  // Services
  import api from '../../services/api';
  import { notificationActions } from '../../stores/notifications';
  
  // Props
  export let show: boolean = false;
  export let collectionName: string;
  
  const dispatch = createEventDispatcher();
  
  // Input modes
  type InputMode = 'manual' | 'json' | 'csv' | 'file';
  let inputMode: InputMode = 'manual';
  
  // Form state
  let manualTitle = '';
  let manualContent = '';
  let jsonInput = '';
  let csvInput = '';
  let fileInput: File | null = null;
  let fileInputElement: HTMLInputElement;
  
  // Processing state
  let isProcessing = false;
  let processingMessage = '';
  let validationError = '';
  
  // Preview state
  let previewRecords: any[] = [];
  let showPreview = false;
  
  // Input mode options
  const inputModes = [
    { value: 'manual', label: 'Manual Entry', icon: 'material-symbols:edit' },
    { value: 'json', label: 'JSON', icon: 'material-symbols:code' },
    { value: 'csv', label: 'CSV', icon: 'material-symbols:table' },
    { value: 'file', label: 'File Upload', icon: 'material-symbols:upload-file' }
  ];
  
  // Reset form
  const resetForm = () => {
    manualTitle = '';
    manualContent = '';
    jsonInput = '';
    csvInput = '';
    fileInput = null;
    previewRecords = [];
    showPreview = false;
    validationError = '';
    processingMessage = '';
  };
  
  // Close modal
  const handleClose = () => {
    if (!isProcessing) {
      show = false;
      resetForm();
    }
  };
  
  // Validate and parse input
  const validateInput = async () => {
    validationError = '';
    previewRecords = [];
    
    try {
      switch (inputMode) {
        case 'manual':
          if (!manualTitle.trim() || !manualContent.trim()) {
            validationError = 'Please provide both title and content';
            return false;
          }
          previewRecords = [{
            title: manualTitle.trim(),
            content: manualContent.trim()
          }];
          break;
          
        case 'json':
          if (!jsonInput.trim()) {
            validationError = 'Please provide JSON data';
            return false;
          }
          try {
            const parsed = JSON.parse(jsonInput);
            if (Array.isArray(parsed)) {
              previewRecords = parsed;
            } else {
              previewRecords = [parsed];
            }
            
            // Validate structure
            for (const record of previewRecords) {
              if (!record.title || !record.content) {
                validationError = 'Each record must have "title" and "content" fields';
                return false;
              }
            }
          } catch (e) {
            validationError = 'Invalid JSON format';
            return false;
          }
          break;
          
        case 'csv':
          if (!csvInput.trim()) {
            validationError = 'Please provide CSV data';
            return false;
          }
          
          // Simple CSV parsing (assumes title,content format)
          const lines = csvInput.trim().split('\n');
          const headers = lines[0].toLowerCase().split(',').map(h => h.trim());
          
          if (!headers.includes('title') || !headers.includes('content')) {
            validationError = 'CSV must have "title" and "content" columns';
            return false;
          }
          
          const titleIndex = headers.indexOf('title');
          const contentIndex = headers.indexOf('content');
          
          for (let i = 1; i < lines.length; i++) {
            const values = lines[i].split(',').map(v => v.trim());
            if (values.length >= 2) {
              previewRecords.push({
                title: values[titleIndex] || '',
                content: values[contentIndex] || ''
              });
            }
          }
          
          if (previewRecords.length === 0) {
            validationError = 'No valid records found in CSV';
            return false;
          }
          break;
          
        case 'file':
          if (!fileInput) {
            validationError = 'Please select a file';
            return false;
          }
          
          // For now, we'll just validate file type
          const fileName = fileInput.name.toLowerCase();
          if (!fileName.endsWith('.json') && !fileName.endsWith('.csv')) {
            validationError = 'Please upload a JSON or CSV file';
            return false;
          }
          
          // Read file content
          try {
            const content = await readFile(fileInput);
            if (fileName.endsWith('.json')) {
              jsonInput = content;
              inputMode = 'json';
              return validateInput(); // Recursive call with JSON mode
            } else if (fileName.endsWith('.csv')) {
              csvInput = content;
              inputMode = 'csv';
              return validateInput(); // Recursive call with CSV mode
            }
          } catch (e) {
            validationError = 'Failed to read file';
            return false;
          }
          break;
      }
      
      return previewRecords.length > 0;
    } catch (error) {
      validationError = error instanceof Error ? error.message : 'Validation failed';
      return false;
    }
  };
  
  // Read file helper
  const readFile = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (e) => resolve(e.target?.result as string);
      reader.onerror = reject;
      reader.readAsText(file);
    });
  };
  
  // Handle file selection
  const handleFileSelect = (event: Event) => {
    const target = event.target as HTMLInputElement;
    fileInput = target.files?.[0] || null;
  };
  
  // Preview records
  const handlePreview = async () => {
    const isValid = await validateInput();
    if (isValid) {
      showPreview = true;
    }
  };
  
  // Add records
  const handleAddRecords = async () => {
    if (previewRecords.length === 0) return;
    
    isProcessing = true;
    processingMessage = `Adding ${previewRecords.length} record${previewRecords.length > 1 ? 's' : ''}...`;
    
    try {
      // Call the API to add records
      await api.addRecords(collectionName, previewRecords);
      
      notificationActions.success(
        'Records Added',
        `Successfully added ${previewRecords.length} record${previewRecords.length > 1 ? 's' : ''} to ${collectionName}`
      );
      
      dispatch('recordsAdded', { count: previewRecords.length });
      handleClose();
    } catch (error) {
      console.error('Failed to add records:', error);
      notificationActions.error(
        'Failed to Add Records',
        error instanceof Error ? error.message : 'An error occurred while adding records'
      );
    } finally {
      isProcessing = false;
      processingMessage = '';
    }
  };
  
  // Example templates
  const loadExampleTemplate = () => {
    switch (inputMode) {
      case 'json':
        jsonInput = `[
  {
    "title": "Example Article 1",
    "content": "This is the content of the first article. It can contain multiple paragraphs and detailed information."
  },
  {
    "title": "Example Article 2", 
    "content": "This is the content of the second article. Each record should have a title and content field."
  }
]`;
        break;
      case 'csv':
        csvInput = `title,content
"Example Article 1","This is the content of the first article."
"Example Article 2","This is the content of the second article."
"Example Article 3","CSV format supports bulk import of records."`;
        break;
    }
  };
</script>

<Modal
  bind:show
  title="Add Records to {collectionName}"
  size="lg"
  showHeader={true}
  showFooter={true}
  closable={!isProcessing}
  onClose={handleClose}
>
  <div class="space-y-4">
    <!-- Input Mode Selector -->
    <div class="flex flex-wrap gap-2">
      {#each inputModes as mode}
        <button
          class="flex items-center gap-2 px-3 py-2 rounded-lg border transition-all
            {inputMode === mode.value 
              ? 'bg-blue-50 border-blue-300 text-blue-700' 
              : 'bg-white border-gray-300 text-gray-700 hover:bg-gray-50'}"
          on:click={() => { inputMode = mode.value; validationError = ''; }}
          disabled={isProcessing}
        >
          <Icon icon={mode.icon} class="w-4 h-4" />
          <span class="text-sm font-medium">{mode.label}</span>
        </button>
      {/each}
    </div>
    
    <!-- Input Forms -->
    {#if !showPreview}
      <div class="space-y-4">
        {#if inputMode === 'manual'}
          <!-- Manual Entry -->
          <div class="space-y-3">
            <FormInput
              label="Title"
              bind:value={manualTitle}
              placeholder="Enter record title"
              required={true}
              disabled={isProcessing}
            />
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">
                Content <span class="text-red-500">*</span>
              </label>
              <textarea
                bind:value={manualContent}
                placeholder="Enter record content"
                rows="6"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                disabled={isProcessing}
              />
            </div>
          </div>
          
        {:else if inputMode === 'json'}
          <!-- JSON Input -->
          <div class="space-y-2">
            <div class="flex items-center justify-between">
              <label class="block text-sm font-medium text-gray-700">
                JSON Data <span class="text-red-500">*</span>
              </label>
              <Button
                variant="ghost"
                size="xs"
                onClick={loadExampleTemplate}
                disabled={isProcessing}
              >
                Load Example
              </Button>
            </div>
            <textarea
              bind:value={jsonInput}
              placeholder="Enter JSON array of records..."
              rows="10"
              class="w-full px-3 py-2 font-mono text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              disabled={isProcessing}
            />
            <p class="text-xs text-gray-500">
              Paste JSON array of objects with "title" and "content" fields
            </p>
          </div>
          
        {:else if inputMode === 'csv'}
          <!-- CSV Input -->
          <div class="space-y-2">
            <div class="flex items-center justify-between">
              <label class="block text-sm font-medium text-gray-700">
                CSV Data <span class="text-red-500">*</span>
              </label>
              <Button
                variant="ghost"
                size="xs"
                onClick={loadExampleTemplate}
                disabled={isProcessing}
              >
                Load Example
              </Button>
            </div>
            <textarea
              bind:value={csvInput}
              placeholder="title,content&#10;..."
              rows="10"
              class="w-full px-3 py-2 font-mono text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              disabled={isProcessing}
            />
            <p class="text-xs text-gray-500">
              First row should contain column headers: title,content
            </p>
          </div>
          
        {:else if inputMode === 'file'}
          <!-- File Upload -->
          <div class="space-y-3">
            <label class="block text-sm font-medium text-gray-700">
              Upload File <span class="text-red-500">*</span>
            </label>
            <div class="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center">
              <Icon icon="material-symbols:cloud-upload" class="w-12 h-12 mx-auto text-gray-400 mb-3" />
              <input
                type="file"
                accept=".json,.csv"
                on:change={handleFileSelect}
                bind:this={fileInputElement}
                class="hidden"
                disabled={isProcessing}
              />
              <Button
                variant="secondary"
                onClick={() => fileInputElement.click()}
                disabled={isProcessing}
              >
                Choose File
              </Button>
              {#if fileInput}
                <p class="mt-2 text-sm text-gray-600">{fileInput.name}</p>
              {:else}
                <p class="mt-2 text-sm text-gray-500">JSON or CSV files only</p>
              {/if}
            </div>
          </div>
        {/if}
        
        <!-- Validation Error -->
        {#if validationError}
          <div class="p-3 bg-red-50 border border-red-200 rounded-lg">
            <p class="text-sm text-red-600">{validationError}</p>
          </div>
        {/if}
      </div>
      
    {:else}
      <!-- Preview Records -->
      <div class="space-y-3">
        <div class="flex items-center justify-between">
          <h4 class="font-medium text-gray-900">
            Preview ({previewRecords.length} record{previewRecords.length > 1 ? 's' : ''})
          </h4>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => showPreview = false}
            disabled={isProcessing}
          >
            Edit
          </Button>
        </div>
        
        <div class="max-h-96 overflow-y-auto space-y-2 border rounded-lg p-3">
          {#each previewRecords as record, index}
            <div class="p-3 bg-gray-50 rounded-lg">
              <div class="flex items-start justify-between mb-1">
                <h5 class="font-medium text-sm text-gray-900">{record.title}</h5>
                <span class="text-xs text-gray-500">#{index + 1}</span>
              </div>
              <p class="text-sm text-gray-600 line-clamp-2">{record.content}</p>
            </div>
          {/each}
        </div>
      </div>
    {/if}
    
    <!-- Processing Message -->
    {#if isProcessing}
      <div class="flex items-center gap-3 p-4 bg-blue-50 rounded-lg">
        <LoadingSpinner size="sm" />
        <span class="text-sm text-blue-700">{processingMessage}</span>
      </div>
    {/if}
  </div>
  
  <div slot="footer" class="flex justify-end gap-3">
    <Button
      variant="secondary"
      onClick={handleClose}
      disabled={isProcessing}
    >
      Cancel
    </Button>
    {#if !showPreview}
      <Button
        variant="primary"
        onClick={handlePreview}
        disabled={isProcessing}
      >
        Preview
      </Button>
    {:else}
      <Button
        variant="primary"
        onClick={handleAddRecords}
        loading={isProcessing}
      >
        Add {previewRecords.length} Record{previewRecords.length > 1 ? 's' : ''}
      </Button>
    {/if}
  </div>
</Modal>

<style>
  .line-clamp-2 {
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
</style>