<script lang="ts">
  import { onMount } from "svelte";
  import { api } from "../../services/api";
  import { chatStore, chatActions } from "../../stores/chat";
  import { notificationActions } from "../../stores/notifications";
  
  import Button from "../common/Button.svelte";
  import LoadingSpinner from "../common/LoadingSpinner.svelte";
  import Icon from "@iconify/svelte";
  import type { CollectionStats } from "../../services/api";

  export let session: any;
  export let onClose: () => void = () => {};

  // Local state
  let isLoading = false;
  let isSaving = false;
  let collections: any[] = [];
  let availableModels: any = null;
  let selectedCollectionDetails: CollectionStats | null = null;
  let loadingCollectionDetails = false;
  let previousCollectionName = "";

  // Form data - initialize with session values
  let formData = {
    title: session?.title || "",
    collection_name: session?.collection_name || "articles",
    llm_model: session?.llm_model || "llama2",
    embedding_model: session?.embedding_model || "embeddinggemma:latest",
    temperature: session?.temperature || 0.7,
    top_k: session?.top_k || 5,
    min_score: session?.min_score || 0.5,
    max_context_length: session?.max_context_length || 3000,
    max_tokens: session?.max_tokens || 2000,
    system_prompt: session?.system_prompt || "",
    show_sources: session?.show_sources !== false,
  };

  onMount(async () => {
    await loadData();
  });

  async function loadData() {
    isLoading = true;
    try {
      // Load collections and models in parallel
      const [collectionsResult, modelsResult] = await Promise.allSettled([
        api.getCollections(),
        api.getModels(),
      ]);

      if (collectionsResult.status === "fulfilled") {
        collections = collectionsResult.value || [];
        console.log("Loaded collections:", collections);
      } else {
        console.error("Failed to load collections:", collectionsResult.reason);
        notificationActions.error("Failed to load collections");
        // Fallback to empty array
        collections = [];
      }

      if (modelsResult.status === "fulfilled") {
        availableModels = modelsResult.value;
        console.log("Loaded models:", availableModels);
      } else {
        console.error("Failed to load models:", modelsResult.reason);
        notificationActions.error("Failed to load available models");
        // Fallback to empty models
        availableModels = { llm_models: [], embedding_models: [] };
      }
    } catch (error) {
      console.error("Error loading data:", error);
      notificationActions.error("Failed to load settings data");
      // Set fallback data
      collections = [];
      availableModels = { llm_models: [], embedding_models: [] };
    } finally {
      isLoading = false;
    }
  }

  async function handleSave() {
    if (!session?.id) {
      notificationActions.error("No session selected");
      return;
    }

    isSaving = true;
    try {
      // Update session settings
      await api.updateChatSession(session.id, formData);
      
      // Refresh the session in the store
      await chatActions.loadSession(session.id);
      
      notificationActions.success("Chat settings updated successfully");
      onClose();
    } catch (error: any) {
      console.error("Error updating chat settings:", error);
      notificationActions.error(
        `Failed to update settings: ${error.message || "Unknown error"}`
      );
    } finally {
      isSaving = false;
    }
  }

  function handleCancel() {
    // Reset form data to original values
    formData = {
      title: session?.title || "",
      collection_name: session?.collection_name || "articles",
      llm_model: session?.llm_model || "llama2",
      embedding_model: session?.embedding_model || "embeddinggemma:latest",
      temperature: session?.temperature || 0.7,
      top_k: session?.top_k || 5,
      min_score: session?.min_score || 0.5,
      max_context_length: session?.max_context_length || 3000,
      max_tokens: session?.max_tokens || 2000,
      system_prompt: session?.system_prompt || "",
      show_sources: session?.show_sources !== false,
    };
    onClose();
  }

  // Reactive updates
  $: isValid = formData.title.trim().length > 0 && 
               formData.collection_name.trim().length > 0 &&
               formData.llm_model.trim().length > 0;

  // Load collection details when collection changes
  $: if (formData.collection_name && collections.length > 0 && formData.collection_name !== previousCollectionName) {
    previousCollectionName = formData.collection_name;
    loadCollectionDetails(formData.collection_name);
  }

  async function loadCollectionDetails(collectionName: string) {
    loadingCollectionDetails = true;
    try {
      const details = await api.getCollectionStats(collectionName);
      selectedCollectionDetails = details;
      // Update the form data with the detected embedding model
      if (details.embedding_model) {
        formData.embedding_model = details.embedding_model;
      }
    } catch (error) {
      console.error("Failed to load collection details:", error);
      selectedCollectionDetails = null;
      // Don't update embedding_model on error
      formData.embedding_model = "";
    } finally {
      loadingCollectionDetails = false;
    }
  }
</script>

<div class="chat-settings">
  <div class="settings-header">
    <h2 class="text-xl font-semibold text-gray-900">Chat Settings</h2>
    <Button 
      variant="ghost" 
      size="small" 
      on:click={onClose}
      class="text-gray-500 hover:text-gray-700"
    >
      <Icon icon="mdi:close" />
    </Button>
  </div>

  {#if isLoading}
    <div class="loading-state">
      <LoadingSpinner />
      <p class="text-gray-600 mt-2">Loading settings...</p>
    </div>
  {:else}
    <div class="settings-content">
      <form on:submit|preventDefault={handleSave} class="space-y-6">
        
        <!-- Basic Settings -->
        <div class="settings-section">
          <h3 class="text-lg font-medium text-gray-900 mb-4">Basic Settings</h3>
          
          <div class="form-group">
            <label for="title" class="form-label">Chat Title</label>
            <input
              id="title"
              type="text"
              bind:value={formData.title}
              class="form-input"
              placeholder="Enter chat title"
              required
            />
          </div>

          <div class="form-group">
            <label for="collection" class="form-label">Collection</label>
            <select
              id="collection"
              bind:value={formData.collection_name}
              class="form-select"
              required
            >
              <option value="">Select a collection...</option>
              {#each collections as collection}
                <option value={collection.name}>{collection.name}</option>
              {/each}
              <!-- Fallback options if no collections loaded -->
              {#if collections.length === 0}
                <option value="articles">articles</option>
                <option value="documents">documents</option>
                <option value="knowledge">knowledge</option>
              {/if}
            </select>
          </div>
        </div>

        <!-- Model Settings -->
        <div class="settings-section">
          <h3 class="text-lg font-medium text-gray-900 mb-4">Model Settings</h3>
          
          <div class="form-group">
            <label for="llm-model" class="form-label">LLM Model</label>
            <select
              id="llm-model"
              bind:value={formData.llm_model}
              class="form-select"
              required
            >
              <option value="">Select LLM model...</option>
              {#if availableModels?.llm_models}
                {#each availableModels.llm_models as model}
                  <option value={model.name}>{model.name}</option>
                {/each}
              {/if}
              <!-- Fallback options if no models loaded -->
              {#if !availableModels?.llm_models || availableModels.llm_models.length === 0}
                <option value="llama2">llama2</option>
                <option value="mistral">mistral</option>
                <option value="codellama">codellama</option>
              {/if}
            </select>
          </div>

          <div class="form-group">
            <label class="form-label">Embedding Model</label>
            <div class="embedding-model-display">
              {#if loadingCollectionDetails}
                <div class="loading-model">
                  <LoadingSpinner size="small" />
                  <span>Loading model info...</span>
                </div>
              {:else if selectedCollectionDetails?.embedding_model}
                <div class="model-info">
                  <Icon icon="mdi:vector-square" class="model-icon" />
                  <span class="model-name">{selectedCollectionDetails.embedding_model}</span>
                  <span class="model-badge">Auto-detected</span>
                </div>
              {:else if formData.collection_name}
                <div class="model-info warning">
                  <Icon icon="mdi:alert-circle-outline" class="model-icon" />
                  <span class="model-name">Model information not available</span>
                </div>
              {:else}
                <div class="model-info placeholder">
                  <span class="model-name">Select a collection first</span>
                </div>
              {/if}
            </div>
          </div>
        </div>

        <!-- Advanced Settings -->
        <div class="settings-section">
          <h3 class="text-lg font-medium text-gray-900 mb-4">Advanced Settings</h3>
          
          <div class="form-row">
            <div class="form-group">
              <label for="temperature" class="form-label">Temperature</label>
              <input
                id="temperature"
                type="range"
                min="0"
                max="2"
                step="0.1"
                bind:value={formData.temperature}
                class="form-range"
              />
              <div class="range-value">{formData.temperature}</div>
            </div>

            <div class="form-group">
              <label for="top-k" class="form-label">Top-K Context</label>
              <input
                id="top-k"
                type="range"
                min="1"
                max="20"
                step="1"
                bind:value={formData.top_k}
                class="form-range"
              />
              <div class="range-value">{formData.top_k}</div>
            </div>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label for="min-score" class="form-label">Min Score</label>
              <input
                id="min-score"
                type="range"
                min="0"
                max="1"
                step="0.05"
                bind:value={formData.min_score}
                class="form-range"
              />
              <div class="range-value">{formData.min_score}</div>
            </div>

            <div class="form-group">
              <label for="max-tokens" class="form-label">Max Tokens</label>
              <input
                id="max-tokens"
                type="range"
                min="100"
                max="4000"
                step="100"
                bind:value={formData.max_tokens}
                class="form-range"
              />
              <div class="range-value">{formData.max_tokens}</div>
            </div>
          </div>

          <div class="form-group">
            <label for="max-context" class="form-label">Max Context Length</label>
            <input
              id="max-context"
              type="range"
              min="500"
              max="8000"
              step="500"
              bind:value={formData.max_context_length}
              class="form-range"
            />
            <div class="range-value">{formData.max_context_length}</div>
          </div>

          <div class="form-group">
            <label for="system-prompt" class="form-label">System Prompt</label>
            <textarea
              id="system-prompt"
              bind:value={formData.system_prompt}
              class="form-textarea"
              placeholder="Enter system prompt (optional)"
              rows="3"
            ></textarea>
          </div>

          <div class="form-group">
            <label class="form-checkbox">
              <input
                type="checkbox"
                bind:checked={formData.show_sources}
              />
              <span>Show sources in responses</span>
            </label>
          </div>
        </div>

        <!-- Actions -->
        <div class="settings-actions">
          <Button
            type="button"
            variant="outline"
            on:click={handleCancel}
            disabled={isSaving}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            variant="primary"
            disabled={!isValid || isSaving}
          >
            {#if isSaving}
              <LoadingSpinner size="small" />
              Saving...
            {:else}
              Save Settings
            {/if}
          </Button>
        </div>
      </form>
    </div>
  {/if}
</div>

<style>
  .chat-settings {
    border-radius: 0.5rem;
    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
    max-width: 42rem;
    width: 100%;
    max-height: 80vh;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    position: relative;
    z-index: 10000;
    background-color: #ffffff !important;
  }

  .settings-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1.5rem;
    border-bottom: 1px solid #e5e7eb;
  }

  .loading-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 3rem;
  }

  .settings-content {
    flex: 1;
    overflow-y: auto;
    padding: 1.5rem;
  }

  .settings-section {
    border-bottom: 1px solid #f3f4f6;
    padding-bottom: 1.5rem;
    margin-bottom: 1.5rem;
  }

  .settings-section:last-child {
    border-bottom: none;
    padding-bottom: 0;
    margin-bottom: 0;
  }

  .form-group {
    margin-bottom: 1rem;
  }

  .form-row {
    display: grid;
    grid-template-columns: 1fr;
    gap: 1rem;
  }

  @media (min-width: 768px) {
    .form-row {
      grid-template-columns: 1fr 1fr;
    }
  }

  .form-label {
    display: block;
    font-size: 0.875rem;
    font-weight: 500;
    color: #374151;
    margin-bottom: 0.5rem;
  }

  .form-input, .form-select, .form-textarea {
    display: block;
    width: 100%;
    padding: 0.5rem 0.75rem;
    border: 1px solid #d1d5db;
    border-radius: 0.375rem;
    box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
    font-size: 0.875rem;
  }

  .form-input:focus, .form-select:focus, .form-textarea:focus {
    outline: none;
    border-color: #3b82f6;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
  }

  .form-input::placeholder, .form-textarea::placeholder {
    color: #9ca3af;
  }

  .form-textarea {
    resize: vertical;
  }

  .form-range {
    width: 100%;
    height: 0.5rem;
    background-color: #e5e7eb;
    border-radius: 0.5rem;
    appearance: none;
    cursor: pointer;
  }

  .range-value {
    font-size: 0.875rem;
    color: #6b7280;
    text-align: center;
    font-family: ui-monospace, SFMono-Regular, "SF Mono", Consolas, "Liberation Mono", Menlo, monospace;
    margin-top: 0.5rem;
  }

  .form-checkbox {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    cursor: pointer;
  }

  .form-checkbox input {
    height: 1rem;
    width: 1rem;
    accent-color: #3b82f6;
    border: 1px solid #d1d5db;
    border-radius: 0.25rem;
  }

  .settings-actions {
    display: flex;
    justify-content: flex-end;
    gap: 0.75rem;
    padding-top: 1.5rem;
    border-top: 1px solid #e5e7eb;
  }

  .embedding-model-display {
    padding: 0.75rem;
    background-color: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 0.375rem;
    font-size: 0.875rem;
  }

  .loading-model {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    color: #6b7280;
  }

  .model-info {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .model-info.warning {
    color: #f59e0b;
  }

  .model-info.placeholder {
    color: #9ca3af;
    font-style: italic;
  }

  .model-icon {
    font-size: 1.125rem;
    color: #3b82f6;
  }

  .model-info.warning .model-icon {
    color: #f59e0b;
  }

  .model-name {
    flex: 1;
    font-weight: 500;
  }

  .model-badge {
    font-size: 0.75rem;
    padding: 0.125rem 0.5rem;
    background-color: #dbeafe;
    color: #3b82f6;
    border-radius: 9999px;
    font-weight: 500;
  }
</style>