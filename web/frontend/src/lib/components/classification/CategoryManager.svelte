<script lang="ts">
  import { onMount } from 'svelte';
  import {
    categories,
    isLoadingCategories,
    isCreatingCategory,
    isUpdatingCategory,
    classificationStore,
    hasCategories
  } from '../../stores/classification';
  import type { CategoryResponse, CategoryCreate, CategoryUpdate } from '../../services/api';

  // Form data
  let showForm = false;
  let editingCategory: CategoryResponse | null = null;
  let formData = {
    name: '',
    sample_texts: [''],
    model: ''
  };

  // Add new sample text field
  function addSampleText() {
    formData.sample_texts = [...formData.sample_texts, ''];
  }

  // Remove sample text field
  function removeSampleText(index: number) {
    if (formData.sample_texts.length > 1) {
      formData.sample_texts = formData.sample_texts.filter((_, i) => i !== index);
    }
  }

  // Update sample text
  function updateSampleText(index: number, value: string) {
    formData.sample_texts[index] = value;
  }

  // Reset form
  function resetForm() {
    formData = {
      name: '',
      sample_texts: [''],
      model: ''
    };
    editingCategory = null;
    showForm = false;
  }

  // Start creating category
  function startCreate() {
    resetForm();
    showForm = true;
  }

  // Start editing category
  function startEdit(category: CategoryResponse) {
    editingCategory = category;
    formData = {
      name: category.name,
      sample_texts: [...category.sample_texts],
      model: category.model_name || ''
    };
    showForm = true;
  }

  // Submit form
  async function submitForm() {
    const cleanSampleTexts = formData.sample_texts
      .map(text => text.trim())
      .filter(text => text.length > 0);

    if (!formData.name.trim() || cleanSampleTexts.length === 0) {
      return;
    }

    const categoryData = {
      name: formData.name.trim(),
      sample_texts: cleanSampleTexts,
      model: formData.model.trim() || undefined
    };

    let success = false;
    if (editingCategory) {
      success = await classificationStore.updateCategory(editingCategory.id, categoryData);
    } else {
      success = await classificationStore.createCategory(categoryData);
    }

    if (success) {
      resetForm();
    }
  }

  // Delete category
  async function deleteCategory(category: CategoryResponse) {
    if (confirm(`Are you sure you want to delete the category "${category.name}"?`)) {
      await classificationStore.deleteCategory(category.id);
    }
  }

  // Load categories on mount
  onMount(() => {
    classificationStore.loadCategories();
  });
</script>

<div class="bg-white rounded-lg shadow-md p-6">
  <div class="flex justify-between items-center mb-6">
    <h2 class="text-xl font-semibold text-gray-900">Category Management</h2>
    <button
      on:click={startCreate}
      disabled={$isCreatingCategory || showForm}
      class="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
    >
      Add Category
    </button>
  </div>

  {#if showForm}
    <div class="mb-6 p-4 border border-gray-200 rounded-md bg-gray-50">
      <h3 class="text-lg font-medium mb-4">
        {editingCategory ? 'Edit Category' : 'Create New Category'}
      </h3>

      <form on:submit|preventDefault={submitForm} class="space-y-4">
        <!-- Category Name -->
        <div>
          <label for="name" class="block text-sm font-medium text-gray-700 mb-1">
            Category Name
          </label>
          <input
            id="name"
            type="text"
            bind:value={formData.name}
            required
            class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Enter category name"
          />
        </div>

        <!-- Model (Optional) -->
        <div>
          <label for="model" class="block text-sm font-medium text-gray-700 mb-1">
            Embedding Model (Optional)
          </label>
          <input
            id="model"
            type="text"
            bind:value={formData.model}
            class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="e.g., embeddinggemma:latest"
          />
          <p class="text-xs text-gray-500 mt-1">Leave empty to use default model</p>
        </div>

        <!-- Sample Texts -->
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">
            Sample Texts
          </label>
          {#each formData.sample_texts as text, index}
            <div class="flex gap-2 mb-2">
              <textarea
                bind:value={text}
                on:input={(e) => updateSampleText(index, e.target.value)}
                required
                rows="2"
                class="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Enter sample text for this category"
              ></textarea>
              {#if formData.sample_texts.length > 1}
                <button
                  type="button"
                  on:click={() => removeSampleText(index)}
                  class="px-3 py-2 text-red-600 hover:text-red-800 self-start"
                  title="Remove sample text"
                >
                  ✕
                </button>
              {/if}
            </div>
          {/each}

          <button
            type="button"
            on:click={addSampleText}
            class="mt-2 px-3 py-1 text-sm bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300"
          >
            + Add Sample Text
          </button>
        </div>

        <!-- Form Actions -->
        <div class="flex gap-2 pt-4">
          <button
            type="submit"
            disabled={$isCreatingCategory || $isUpdatingCategory}
            class="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {#if $isCreatingCategory || $isUpdatingCategory}
              Saving...
            {:else}
              {editingCategory ? 'Update' : 'Create'} Category
            {/if}
          </button>
          <button
            type="button"
            on:click={resetForm}
            class="px-4 py-2 bg-gray-300 text-gray-700 rounded-md hover:bg-gray-400"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  {/if}

  <!-- Categories List -->
  {#if $isLoadingCategories}
    <div class="flex justify-center py-8">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
    </div>
  {:else if $hasCategories}
    <div class="space-y-4">
      {#each $categories as category (category.id)}
        <div class="border border-gray-200 rounded-md p-4">
          <div class="flex justify-between items-start mb-2">
            <div>
              <h3 class="font-medium text-gray-900">{category.name}</h3>
              <p class="text-sm text-gray-500">
                {category.sample_count} sample{category.sample_count !== 1 ? 's' : ''}
                {#if category.model_name}
                  • Model: {category.model_name}
                {/if}
              </p>
            </div>
            <div class="flex gap-2">
              <button
                on:click={() => startEdit(category)}
                disabled={showForm}
                class="px-3 py-1 text-sm bg-blue-100 text-blue-700 rounded-md hover:bg-blue-200 disabled:opacity-50"
              >
                Edit
              </button>
              <button
                on:click={() => deleteCategory(category)}
                class="px-3 py-1 text-sm bg-red-100 text-red-700 rounded-md hover:bg-red-200"
              >
                Delete
              </button>
            </div>
          </div>

          <!-- Sample texts preview -->
          <div class="mt-3">
            <p class="text-xs font-medium text-gray-700 mb-1">Sample texts:</p>
            <div class="space-y-1">
              {#each category.sample_texts.slice(0, 3) as sample}
                <p class="text-xs text-gray-600 bg-gray-50 px-2 py-1 rounded">
                  {sample.length > 100 ? sample.substring(0, 100) + '...' : sample}
                </p>
              {/each}
              {#if category.sample_texts.length > 3}
                <p class="text-xs text-gray-500 italic">
                  +{category.sample_texts.length - 3} more sample{category.sample_texts.length - 3 !== 1 ? 's' : ''}
                </p>
              {/if}
            </div>
          </div>
        </div>
      {/each}
    </div>
  {:else}
    <div class="text-center py-8">
      <div class="text-gray-400 mb-2">
        <svg class="w-12 h-12 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"></path>
        </svg>
      </div>
      <p class="text-gray-500">No categories created yet</p>
      <p class="text-sm text-gray-400">Click "Add Category" to create your first classification category</p>
    </div>
  {/if}
</div>