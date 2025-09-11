<script lang="ts">
  import Modal from '../common/Modal.svelte';
  import FormInput from '../common/FormInput.svelte';
  import FormSelect from '../common/FormSelect.svelte';
  import Button from '../common/Button.svelte';
  import Icon from '@iconify/svelte';
  import { collectionsActions, operationInProgress, type CreateCollectionData } from '../../stores/collections';
  import { notificationActions } from '../../stores/notifications';
  import type { SelectOption } from '../common/FormSelect.svelte';
  import { onMount } from 'svelte';
  import type { EmbeddingModel } from '../../services/api';

  // Modal props
  export let show: boolean = false;
  export let onClose: (() => void) | undefined = undefined;

  // Form data
  let formData: CreateCollectionData = {
    name: '',
    vector_size: undefined,
    distance_metric: 'cosine',
    embedding_model: '',
    description: ''
  };
  
  // Embedding models
  let availableModels: EmbeddingModel[] = [];
  let loadingModels = true;
  let selectedModelInfo: EmbeddingModel | null = null;

  // Form validation
  let errors: Record<string, string> = {};
  let isValid = false;
  let serverError: string = '';

  // Distance metric options
  const distanceMetricOptions: SelectOption[] = [
    {
      value: 'cosine',
      label: 'Cosine',
      description: 'Cosine similarity - Good for normalized vectors and text embeddings. Measures the angle between vectors.'
    },
    {
      value: 'euclidean',
      label: 'Euclidean (L2)',
      description: 'Euclidean distance - Good for continuous data. Measures the straight-line distance between vectors.'
    },
    {
      value: 'manhattan',
      label: 'Manhattan (L1)',
      description: 'Manhattan distance - Sum of absolute differences. Good for discrete data and outlier robustness.'
    },
    {
      value: 'dot',
      label: 'Dot Product',
      description: 'Dot product similarity - Good for non-normalized vectors. Measures both angle and magnitude.'
    }
  ];
  
  // Load embedding models on mount
  onMount(async () => {
    try {
      loadingModels = true;
      const modelsArray = await collectionsActions.getAvailableEmbeddingModels();
      availableModels = modelsArray.filter(m => m.is_available !== 'false');
      
      // Set default model if available
      if (availableModels.length > 0) {
        const defaultModel = availableModels.find(m => m.name === 'embeddinggemma:latest') || availableModels[0];
        formData.embedding_model = defaultModel.name;
        selectedModelInfo = defaultModel;
        formData.vector_size = defaultModel.vector_size;
      }
    } catch (error) {
      console.error('Failed to load embedding models:', error);
      notificationActions.error('Failed to load embedding models', 'Please check your Ollama connection');
    } finally {
      loadingModels = false;
    }
  });
  
  // Update vector size when model changes
  const handleModelChange = async (value: string | number) => {
    formData.embedding_model = String(value);
    const model = availableModels.find(m => m.name === value);
    if (model) {
      selectedModelInfo = model;
      formData.vector_size = model.vector_size;
    }
    serverError = '';
    validateForm();
  };

  // Validation rules
  const validateForm = () => {
    const newErrors: Record<string, string> = {};

    // Collection name validation
    if (!formData.name.trim()) {
      newErrors.name = 'Collection name is required';
    } else if (formData.name.length < 3) {
      newErrors.name = 'Collection name must be at least 3 characters';
    } else if (!/^[a-zA-Z0-9_-]+$/.test(formData.name)) {
      newErrors.name = 'Collection name can only contain letters, numbers, underscores, and hyphens';
    } else if (collectionsActions.collectionExists(formData.name)) {
      newErrors.name = 'Collection name already exists';
    }

    // Embedding model validation
    if (!formData.embedding_model) {
      newErrors.embedding_model = 'Embedding model is required';
    }

    // Distance metric validation
    if (!formData.distance_metric) {
      newErrors.distance_metric = 'Distance metric is required';
    }

    errors = newErrors;
    isValid = Object.keys(newErrors).length === 0;
    return isValid;
  };

  // Handle input changes with validation
  const handleNameInput = (value: string | number) => {
    formData.name = String(value);
    serverError = ''; // Clear server error when user types
    validateForm();
  };

  const handleDescriptionInput = (value: string | number) => {
    formData.description = String(value);
    serverError = '';
    validateForm();
  };

  const handleDistanceMetricChange = (value: string | number) => {
    formData.distance_metric = String(value);
    serverError = ''; // Clear server error when user types
    validateForm();
  };

  // Extract error message from server response
  const extractErrorMessage = (error: any): string => {
    if (typeof error === 'string') {
      return error;
    }
    
    if (error?.message) {
      // Check if it's our API error format
      if (error.message.includes('Raw response content:')) {
        try {
          const jsonMatch = error.message.match(/b'({.*})'/);
          if (jsonMatch) {
            const errorData = JSON.parse(jsonMatch[1]);
            if (errorData.status?.error) {
              return errorData.status.error.replace('Wrong input: ', '');
            }
          }
        } catch (parseError) {
          console.error('Failed to parse error response:', parseError);
        }
      }
      return error.message;
    }
    
    return 'An unexpected error occurred. Please try again.';
  };

  // Handle form submission
  const handleSubmit = async (event: Event) => {
    event.preventDefault();
    
    // Clear previous server error
    serverError = '';
    
    if (!validateForm()) {
      return;
    }

    try {
      const collection = await collectionsActions.createCollection(formData);
      
      if (collection) {
        notificationActions.success(
          'Collection Created',
          `Collection "${collection.name}" has been successfully created.`
        );
        handleClose();
      } else {
        // Handle case where creation failed but no exception was thrown
        serverError = 'Failed to create collection. Please check the collection name and try again.';
      }
    } catch (error) {
      console.error('Failed to create collection:', error);
      const errorMessage = extractErrorMessage(error);
      serverError = errorMessage;
      
      // Only show notification for unexpected server errors, not validation errors
      if (!errorMessage.includes('already exists') && !errorMessage.includes('Wrong input')) {
        notificationActions.error(
          'Creation Failed',
          errorMessage
        );
      }
    }
  };

  // Handle modal close
  const handleClose = () => {
    // Reset form
    formData = {
      name: '',
      vector_size: selectedModelInfo?.vector_size,
      distance_metric: 'cosine',
      embedding_model: selectedModelInfo?.name || '',
      description: ''
    };
    errors = {};
    serverError = '';
    isValid = false;
    
    // Close modal
    show = false;
    onClose?.();
  };

  // Handle cancel
  const handleCancel = () => {
    handleClose();
  };

  // Reactive validation on form changes
  $: if (formData) {
    validateForm();
  }
</script>

<Modal 
  bind:show 
  title="Create New Collection" 
  size="md"
  showFooter={true}
  onClose={handleClose}
>
  <form on:submit={handleSubmit} class="space-y-6">
    <!-- Server Error Display -->
    {#if serverError}
      <div class="bg-red-50 border border-red-200 rounded-lg p-4">
        <div class="flex items-start gap-3">
          <Icon icon="material-symbols:error" class="w-5 h-5 text-red-600 mt-0.5" />
          <div class="text-sm text-red-800">
            <p class="font-medium mb-1">Creation Failed</p>
            <p>{serverError}</p>
          </div>
        </div>
      </div>
    {/if}

    <!-- Collection Name -->
    <FormInput
      label="Collection Name"
      type="text"
      bind:value={formData.name}
      placeholder="Enter collection name"
      required={true}
      error={errors.name || ''}
      helperText="Use only letters, numbers, underscores, and hyphens"
      icon="material-symbols:database"
      onInput={handleNameInput}
    />
    
    <!-- Embedding Model -->
    <FormSelect
      label="Embedding Model"
      bind:value={formData.embedding_model}
      options={availableModels.map(model => ({
        value: model.name,
        label: model.display_name || model.name,
        description: `${model.description || ''} (${model.vector_size} dimensions)`
      }))}
      required={true}
      disabled={loadingModels}
      error={errors.embedding_model || ''}
      helperText={loadingModels ? 'Loading models...' : selectedModelInfo?.description || 'Select the embedding model for this collection'}
      icon="material-symbols:model-training"
      onChange={handleModelChange}
    />

    <!-- Vector Size (Read-only) -->
    <FormInput
      label="Vector Size"
      type="number"
      bind:value={formData.vector_size}
      placeholder="Auto-detected from model"
      disabled={true}
      helperText={selectedModelInfo ? `Automatically set by ${selectedModelInfo.name}` : 'Select an embedding model first'}
      icon="material-symbols:bar-chart"
    />

    <!-- Distance Metric -->
    <FormSelect
      label="Distance Metric"
      bind:value={formData.distance_metric}
      options={distanceMetricOptions}
      required={true}
      error={errors.distance_metric || ''}
      helperText="Choose the similarity metric for vector comparison"
      icon="material-symbols:functions"
      onChange={handleDistanceMetricChange}
    />
    
    <!-- Description (Optional) -->
    <FormInput
      label="Description (Optional)"
      type="text"
      bind:value={formData.description}
      placeholder="Brief description of this collection"
      required={false}
      helperText="Add a description to help identify this collection's purpose"
      icon="material-symbols:description"
      onInput={handleDescriptionInput}
    />

    <!-- Information Box -->
    <div class="bg-blue-50 border border-blue-200 rounded-lg p-4">
      <div class="flex items-start gap-3">
        <Icon icon="material-symbols:info" class="w-5 h-5 text-blue-600 mt-0.5" />
        <div class="text-sm text-blue-800">
          <p class="font-medium mb-1">Collection Settings</p>
          <p>The embedding model and distance metric cannot be changed after creation. Each collection can use a different embedding model.</p>
          {#if selectedModelInfo?.use_cases && selectedModelInfo.use_cases.length > 0}
            <p class="mt-1"><span class="font-medium">Best for:</span> {selectedModelInfo.use_cases.join(', ')}</p>
          {/if}
        </div>
      </div>
    </div>
  </form>

  <!-- Modal Footer -->
  <div slot="footer" class="flex items-center justify-end gap-3">
    <Button 
      variant="secondary" 
      onClick={handleCancel}
      disabled={$operationInProgress === 'create'}
    >
      Cancel
    </Button>
    <Button 
      variant="primary" 
      type="submit"
      loading={$operationInProgress === 'create'}
      disabled={!isValid || $operationInProgress === 'create'}
      onClick={handleSubmit}
    >
      Create Collection
    </Button>
  </div>
</Modal>