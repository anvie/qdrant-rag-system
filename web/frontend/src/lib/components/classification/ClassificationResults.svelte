<script lang="ts">
  import { classificationResults } from '../../stores/classification';

  // Helper function to get confidence color
  function getConfidenceColor(confidence: number): string {
    if (confidence >= 0.8) return 'text-green-600 bg-green-100';
    if (confidence >= 0.6) return 'text-yellow-600 bg-yellow-100';
    if (confidence >= 0.4) return 'text-orange-600 bg-orange-100';
    return 'text-red-600 bg-red-100';
  }

  // Helper function to get confidence width for progress bar
  function getConfidenceWidth(confidence: number): string {
    return `${Math.round(confidence * 100)}%`;
  }

  // Helper function to format confidence percentage
  function formatConfidence(confidence: number): string {
    return `${(confidence * 100).toFixed(1)}%`;
  }

  // Helper function to get rank emoji
  function getRankEmoji(index: number): string {
    const emojis = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣'];
    return emojis[index] || `${index + 1}️⃣`;
  }
</script>

{#if $classificationResults}
  <div class="bg-white rounded-lg shadow-md p-6">
    <div class="mb-4">
      <h2 class="text-xl font-semibold text-gray-900 mb-2">Classification Results</h2>
      <div class="bg-gray-50 p-3 rounded-md">
        <p class="text-sm text-gray-600 mb-1">
          <span class="font-medium">Text:</span> "{$classificationResults.text}"
        </p>
        <p class="text-xs text-gray-500">
          <span class="font-medium">Model:</span> {$classificationResults.model}
        </p>
      </div>
    </div>

    {#if $classificationResults.results.length === 0}
      <div class="text-center py-8">
        <div class="text-gray-400 mb-2">
          <svg class="w-12 h-12 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.172 16.172a4 4 0 015.656 0M9 12h6m-6-4h6m2 5.291A7.962 7.962 0 0112 15c-2.34 0-4.47.881-6.072 2.327M12 15.5a8.5 8.5 0 00-8.5 8.5h17a8.5 8.5 0 00-8.5-8.5z"></path>
          </svg>
        </div>
        <p class="text-gray-500">No classification results found</p>
        <p class="text-sm text-gray-400">The text doesn't match any categories well enough</p>
      </div>
    {:else}
      <div class="space-y-3">
        {#each $classificationResults.results as result, index}
          <div class="border border-gray-200 rounded-lg p-4 transition-all hover:shadow-md">
            <div class="flex items-center justify-between mb-2">
              <div class="flex items-center gap-2">
                <span class="text-lg">{getRankEmoji(index)}</span>
                <h3 class="font-medium text-gray-900">{result.category_name}</h3>
              </div>
              <span class="text-sm font-medium {getConfidenceColor(result.confidence)} px-2 py-1 rounded-full">
                {formatConfidence(result.confidence)}
              </span>
            </div>

            <!-- Progress Bar -->
            <div class="w-full bg-gray-200 rounded-full h-2 mb-2">
              <div
                class="h-2 rounded-full transition-all duration-300 {
                  result.confidence >= 0.8 ? 'bg-green-500' :
                  result.confidence >= 0.6 ? 'bg-yellow-500' :
                  result.confidence >= 0.4 ? 'bg-orange-500' : 'bg-red-500'
                }"
                style="width: {getConfidenceWidth(result.confidence)}"
              ></div>
            </div>

            <!-- Additional Info -->
            <div class="flex justify-between items-center text-sm text-gray-500">
              <span>Confidence: {formatConfidence(result.confidence)}</span>
              <span>{result.sample_count} sample{result.sample_count !== 1 ? 's' : ''}</span>
            </div>

            <!-- Confidence Level Indicator -->
            <div class="mt-2 text-xs">
              {#if result.confidence >= 0.8}
                <span class="text-green-600 font-medium">🎯 High confidence match</span>
              {:else if result.confidence >= 0.6}
                <span class="text-yellow-600 font-medium">⚡ Good match</span>
              {:else if result.confidence >= 0.4}
                <span class="text-orange-600 font-medium">⚠️ Moderate match</span>
              {:else}
                <span class="text-red-600 font-medium">❌ Low confidence</span>
              {/if}
            </div>
          </div>
        {/each}
      </div>

      <!-- Summary Statistics -->
      <div class="mt-6 pt-4 border-t border-gray-200">
        <h3 class="text-sm font-medium text-gray-700 mb-2">Summary</h3>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
          <div class="bg-gray-50 p-3 rounded-md">
            <p class="text-lg font-bold text-gray-900">
              {$classificationResults.results.length}
            </p>
            <p class="text-xs text-gray-600">Categories</p>
          </div>

          <div class="bg-gray-50 p-3 rounded-md">
            <p class="text-lg font-bold text-green-600">
              {formatConfidence($classificationResults.results[0]?.confidence || 0)}
            </p>
            <p class="text-xs text-gray-600">Best Match</p>
          </div>

          <div class="bg-gray-50 p-3 rounded-md">
            <p class="text-lg font-bold text-blue-600">
              {formatConfidence(
                $classificationResults.results.reduce((sum, r) => sum + r.confidence, 0) /
                $classificationResults.results.length
              )}
            </p>
            <p class="text-xs text-gray-600">Average</p>
          </div>

          <div class="bg-gray-50 p-3 rounded-md">
            <p class="text-lg font-bold text-purple-600">
              {$classificationResults.results.filter(r => r.confidence >= 0.6).length}
            </p>
            <p class="text-xs text-gray-600">Good Matches</p>
          </div>
        </div>
      </div>

      <!-- Interpretation Guide -->
      <div class="mt-4 p-3 bg-blue-50 border border-blue-200 rounded-md">
        <h4 class="text-sm font-medium text-blue-900 mb-1">🔍 How to interpret results:</h4>
        <ul class="text-xs text-blue-800 space-y-1">
          <li>• <span class="font-medium text-green-600">80%+:</span> Very likely to belong to this category</li>
          <li>• <span class="font-medium text-yellow-600">60-80%:</span> Good match, probably belongs here</li>
          <li>• <span class="font-medium text-orange-600">40-60%:</span> Moderate similarity, could be related</li>
          <li>• <span class="font-medium text-red-600">Below 40%:</span> Low similarity, likely different category</li>
        </ul>
      </div>
    {/if}
  </div>
{/if}