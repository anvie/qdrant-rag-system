<script lang="ts">
  import { onMount } from 'svelte';
  import {
    classificationModels,
    selectedModel,
    isLoadingClassification,
    isLoadingModels,
    classificationStore,
    hasCategories
  } from '../../stores/classification';

  // Form data
  let inputText = '';
  let topK = 5;
  let isTyping = false;
  let typingTimeout: number;

  // Auto-classify when user stops typing (debounced)
  function handleTextInput() {
    if (typingTimeout) {
      clearTimeout(typingTimeout);
    }

    isTyping = true;

    typingTimeout = setTimeout(() => {
      isTyping = false;
      if (inputText.trim() && $hasCategories) {
        classifyText();
      } else {
        classificationStore.clearResults();
      }
    }, 1000); // Wait 1 second after user stops typing
  }

  // Manual classification
  async function classifyText() {
    if (!inputText.trim()) {
      return;
    }

    await classificationStore.classifyText(inputText, $selectedModel, topK);
  }

  // Clear input and results
  function clearInput() {
    inputText = '';
    classificationStore.clearResults();
  }

  // Load models on mount
  onMount(() => {
    classificationStore.loadModels();
  });

  // Sample texts for quick testing
  const sampleTexts = [
    "The football match ended with a dramatic penalty shootout in the final minutes.",
    "Machine learning frameworks like TensorFlow simplify neural network implementation for developers.",
    "Central bank announces interest rate hike to combat rising inflation concerns.",
    "Hadith collections provide valuable guidance for daily Muslim life and spiritual practices.",
    "Bagaimana cara menghitung faktorial dengan Python menggunakan recursive function?",
    "Apa hukumnya makan makanan laut dalam perspektif Islam menurut ulama?"
  ];

  function useSampleText(text: string) {
    inputText = text;
    if ($hasCategories) {
      classifyText();
    }
  }
</script>

<div class="bg-white rounded-lg shadow-md p-6">
  <h2 class="text-xl font-semibold text-gray-900 mb-6">Text Classification Tester</h2>

  {#if !$hasCategories}
    <div class="text-center py-8">
      <div class="text-yellow-500 mb-2">
        <svg class="w-12 h-12 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z"></path>
        </svg>
      </div>
      <p class="text-gray-500 font-medium">No categories available</p>
      <p class="text-sm text-gray-400">Please create some categories first to test classification</p>
    </div>
  {:else}
    <!-- Model Selection -->
    <div class="mb-4">
      <label for="model-select" class="block text-sm font-medium text-gray-700 mb-2">
        Embedding Model
      </label>
      <div class="flex gap-4 items-center">
        <select
          id="model-select"
          bind:value={$selectedModel}
          disabled={$isLoadingModels}
          class="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
        >
          {#if $isLoadingModels}
            <option>Loading models...</option>
          {:else if $classificationModels.length === 0}
            <option>No models available</option>
          {:else}
            {#each $classificationModels as model}
              <option value={model.name}>{model.name}</option>
            {/each}
          {/if}
        </select>

        <div class="flex items-center gap-2">
          <label for="top-k" class="text-sm font-medium text-gray-700">Top</label>
          <input
            id="top-k"
            type="number"
            bind:value={topK}
            min="1"
            max="10"
            class="w-16 px-2 py-1 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <span class="text-sm text-gray-600">results</span>
        </div>
      </div>
    </div>

    <!-- Text Input -->
    <div class="mb-4">
      <label for="input-text" class="block text-sm font-medium text-gray-700 mb-2">
        Text to Classify
      </label>
      <div class="relative">
        <textarea
          id="input-text"
          bind:value={inputText}
          on:input={handleTextInput}
          rows="4"
          class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
          placeholder="Enter text to classify..."
        ></textarea>

        <!-- Loading indicator -->
        {#if isTyping || $isLoadingClassification}
          <div class="absolute top-2 right-2">
            <div class="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
          </div>
        {/if}

        <!-- Clear button -->
        {#if inputText}
          <button
            on:click={clearInput}
            class="absolute bottom-2 right-2 p-1 text-gray-400 hover:text-gray-600"
            title="Clear text"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
            </svg>
          </button>
        {/if}
      </div>

      <p class="text-xs text-gray-500 mt-1">
        {#if isTyping}
          Classification will start automatically when you stop typing...
        {:else}
          Type text above and it will be classified automatically
        {/if}
      </p>
    </div>

    <!-- Action Buttons -->
    <div class="flex gap-2 mb-6">
      <button
        on:click={classifyText}
        disabled={!inputText.trim() || $isLoadingClassification}
        class="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {#if $isLoadingClassification}
          Classifying...
        {:else}
          Classify Now
        {/if}
      </button>

      <button
        on:click={clearInput}
        disabled={!inputText}
        class="px-4 py-2 bg-gray-300 text-gray-700 rounded-md hover:bg-gray-400 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        Clear
      </button>
    </div>

    <!-- Sample Texts -->
    <div class="border-t pt-4">
      <h3 class="text-sm font-medium text-gray-700 mb-3">Quick Test Samples</h3>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-2">
        {#each sampleTexts as sample}
          <button
            on:click={() => useSampleText(sample)}
            class="text-left p-3 bg-gray-50 rounded-md hover:bg-gray-100 transition-colors text-sm text-gray-700"
          >
            {sample.length > 80 ? sample.substring(0, 80) + '...' : sample}
          </button>
        {/each}
      </div>
    </div>
  {/if}
</div>