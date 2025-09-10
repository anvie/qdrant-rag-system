<script lang="ts">
  import Modal from '../common/Modal.svelte';
  import FormInput from '../common/FormInput.svelte';
  import FormSelect from '../common/FormSelect.svelte';
  import Button from '../common/Button.svelte';
  import Icon from '@iconify/svelte';
  import { collectionsActions, operationInProgress, type CreateCollectionData } from '../../stores/collections';
  import { notificationActions } from '../../stores/notifications';
  import type { SelectOption } from '../common/FormSelect.svelte';

  // Modal props
  export let show: boolean = false;
  export let onClose: (() => void) | undefined = undefined;

  // Form data
  let formData: CreateCollectionData = {
    name: '',
    vector_size: 384,
    distance_metric: 'cosine'
  };

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

    // Vector size validation
    if (!formData.vector_size || formData.vector_size <= 0) {
      newErrors.vector_size = 'Vector size must be a positive number';
    } else if (formData.vector_size > 4096) {
      newErrors.vector_size = 'Vector size cannot exceed 4096 dimensions';
    } else if (!Number.isInteger(formData.vector_size)) {
      newErrors.vector_size = 'Vector size must be a whole number';
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

  const handleVectorSizeInput = (value: string | number) => {
    formData.vector_size = Number(value);
    serverError = ''; // Clear server error when user types
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
      vector_size: 384,
      distance_metric: 'cosine'
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

    <!-- Vector Size -->
    <FormInput
      label="Vector Size"
      type="number"
      bind:value={formData.vector_size}
      placeholder="Enter vector dimensions"
      required={true}
      min={1}
      max={4096}
      step={1}
      error={errors.vector_size || ''}
      helperText="Number of dimensions in your vectors (e.g., 384 for sentence-transformers)"
      icon="material-symbols:bar-chart"
      onInput={handleVectorSizeInput}
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

    <!-- Information Box -->
    <div class="bg-blue-50 border border-blue-200 rounded-lg p-4">
      <div class="flex items-start gap-3">
        <Icon icon="material-symbols:info" class="w-5 h-5 text-blue-600 mt-0.5" />
        <div class="text-sm text-blue-800">
          <p class="font-medium mb-1">Collection Settings</p>
          <p>These settings cannot be changed after creation. Make sure your vector size matches your embedding model's output dimensions.</p>
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