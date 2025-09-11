<script lang="ts">
  import Icon from "@iconify/svelte";
  import Button from "../common/Button.svelte";
  import Card from "../common/Card.svelte";

  // Props
  export let sources: Array<{
    index: number;
    title: string;
    snippet: string;
    article_id: number | string;
    chunk_index: number;
    score: number;
  }> = [];

  // Local state
  let expanded = false;

  function formatScore(score: number): string {
    return (score * 100).toFixed(1) + "%";
  }

  function toggleExpanded() {
    expanded = !expanded;
  }

  function handleSourceClick(source: any) {
    // Could implement navigation to source document
    console.log("Source clicked:", source);
  }

  // Reactive statements
  $: visibleSources = expanded ? sources : sources.slice(0, 3);
  $: hasMoreSources = sources.length > 3;
</script>

{#if sources.length > 0}
  <Card class="bg-blue-50 border-blue-200">
    <div class="space-y-3">
      <!-- Header -->
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2 text-blue-700">
          <Icon icon="material-symbols:source" class="w-4 h-4" />
          <span class="text-sm font-medium">
            {sources.length} Source{sources.length !== 1 ? "s" : ""}
          </span>
        </div>

        {#if hasMoreSources}
          <Button
            variant="ghost"
            size="xs"
            onClick={toggleExpanded}
            class="text-blue-600 hover:text-blue-700"
          >
            <Icon
              icon={expanded
                ? "material-symbols:expand-less"
                : "material-symbols:expand-more"}
              class="w-4 h-4"
            />
            <span class="ml-1 text-xs">
              {expanded ? "Show less" : `Show all (${sources.length})`}
            </span>
          </Button>
        {/if}
      </div>

      <!-- Sources List -->
      <div class="space-y-2">
        {#each visibleSources as source, index (source.index)}
          <button
            class="
              w-full text-left p-3 rounded-md border border-blue-200 bg-white
              hover:bg-blue-50 hover:border-blue-300 transition-colors
              focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-50
            "
            on:click={() => handleSourceClick(source)}
          >
            <div class="flex items-start justify-between gap-3">
              <div class="flex-1 min-w-0">
                <!-- Source Index Badge -->
                <div class="flex items-center gap-2 mb-1">
                  <span
                    class="
                    inline-flex items-center justify-center w-5 h-5 text-xs font-medium
                    bg-blue-100 text-blue-700 rounded-full
                  "
                  >
                    {source.index}
                  </span>
                  <span class="text-xs text-blue-600 font-medium">
                    Article {source.article_id} • Chunk {source.chunk_index}
                  </span>
                </div>

                <!-- Source Title -->
                <h4 class="text-sm font-medium text-gray-900 mb-1 line-clamp-2">
                  {source.title}
                </h4>
                <p class="text-sm text-cyan-600">{source.snippet}</p>

                <!-- Metadata -->
                <div class="flex items-center gap-3 text-xs text-gray-500">
                  <div class="flex items-center gap-1">
                    <Icon icon="material-symbols:trending-up" class="w-3 h-3" />
                    <span>Relevance: {formatScore(source.score)}</span>
                  </div>
                </div>
              </div>

              <!-- Action Icon -->
              <div class="flex-shrink-0 text-blue-500">
                <Icon icon="material-symbols:open-in-new" class="w-4 h-4" />
              </div>
            </div>
          </button>
        {/each}
      </div>

      <!-- <!-- Footer Info --> -->
      <!-- <div class="text-xs text-blue-600 bg-blue-100 rounded px-2 py-1"> -->
      <!--   <Icon icon="material-symbols:info" class="w-3 h-3 inline mr-1" /> -->
      <!--   These sources were used to generate the response above -->
      <!-- </div> -->
    </div>
  </Card>
{/if}

<style>
  /* Multi-line text truncation */
  .line-clamp-2 {
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
</style>

