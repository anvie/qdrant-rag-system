<script lang="ts">
  import { marked } from "marked";
  import { onMount } from "svelte";
  import Icon from "@iconify/svelte";
  
  import Button from "../common/Button.svelte";
  import SourceCitation from "./SourceCitation.svelte";
  
  export let message: {
    id: string;
    role: string;
    content: string;
    created_at: string;
    sources?: any[];
    response_time_ms?: number;
  };
  
  let showSources = false;
  let formattedContent = "";
  let copySuccess = false;
  
  onMount(() => {
    // Process markdown content
    if (message.content) {
      try {
        formattedContent = marked(message.content, {
          breaks: true,
          gfm: true,
        });
      } catch (error) {
        console.error("Markdown parsing error:", error);
        formattedContent = message.content;
      }
    }
  });
  
  function formatTime(timestamp: string): string {
    try {
      const date = new Date(timestamp);
      return date.toLocaleTimeString([], { 
        hour: '2-digit', 
        minute: '2-digit' 
      });
    } catch {
      return "";
    }
  }
  
  async function copyToClipboard() {
    try {
      await navigator.clipboard.writeText(message.content);
      copySuccess = true;
      setTimeout(() => {
        copySuccess = false;
      }, 2000);
    } catch (error) {
      console.error("Failed to copy:", error);
    }
  }
  
  function toggleSources() {
    showSources = !showSources;
  }
</script>

<div class="flex gap-3 {message.role === 'user' ? 'flex-row-reverse' : 'flex-row'}">
  <!-- Avatar -->
  <div class="flex-shrink-0">
    <div class="
      w-8 h-8 rounded-full flex items-center justify-center text-white text-sm font-medium
      {message.role === 'user' ? 'bg-blue-500' : 'bg-green-500'}
    ">
      {#if message.role === 'user'}
        <Icon icon="material-symbols:person" class="w-5 h-5" />
      {:else}
        <Icon icon="material-symbols:smart_toy" class="w-5 h-5" />
      {/if}
    </div>
  </div>

  <!-- Message Content -->
  <div class="flex-1 min-w-0 {message.role === 'user' ? 'text-right' : 'text-left'}">
    <!-- Message Bubble -->
    <div class="
      inline-block max-w-[80%] rounded-lg px-4 py-2 text-sm
      {message.role === 'user' 
        ? 'bg-blue-500 text-white' 
        : 'bg-white border border-gray-200 text-gray-900'
      }
    ">
      {#if message.role === 'user'}
        <!-- User message - plain text -->
        <p class="whitespace-pre-wrap">{message.content}</p>
      {:else}
        <!-- Assistant message - rendered markdown -->
        <div class="prose prose-sm max-w-none prose-gray">
          {@html formattedContent}
        </div>
      {/if}
    </div>

    <!-- Message Metadata -->
    <div class="flex items-center gap-2 mt-1 text-xs text-gray-500 {message.role === 'user' ? 'justify-end' : 'justify-start'}">
      <span>{formatTime(message.created_at)}</span>
      
      {#if message.response_time_ms && message.role === 'assistant'}
        <span>•</span>
        <span>{message.response_time_ms}ms</span>
      {/if}
      
      {#if message.sources && message.sources.length > 0}
        <span>•</span>
        <button 
          class="hover:text-blue-500 underline"
          on:click={toggleSources}
        >
          {message.sources.length} source{message.sources.length !== 1 ? 's' : ''}
        </button>
      {/if}

      <!-- Copy button for assistant messages -->
      {#if message.role === 'assistant'}
        <Button
          variant="ghost"
          size="sm"
          onClick={copyToClipboard}
          class="ml-2 opacity-0 hover:opacity-100 transition-opacity"
          ariaLabel="Copy message"
        >
          <Icon 
            icon={copySuccess ? "material-symbols:check" : "material-symbols:content-copy"} 
            class="w-3 h-3" 
          />
        </Button>
      {/if}
    </div>

    <!-- Sources Section -->
    {#if showSources && message.sources && message.sources.length > 0}
      <div class="mt-3 {message.role === 'user' ? 'mr-8' : 'ml-8'}">
        <SourceCitation sources={message.sources} />
      </div>
    {/if}
  </div>
</div>

<style>
  /* Prose styling for markdown content */
  :global(.prose) {
    color: inherit;
  }
  
  :global(.prose h1, .prose h2, .prose h3, .prose h4, .prose h5, .prose h6) {
    color: inherit;
    margin-top: 1em;
    margin-bottom: 0.5em;
  }
  
  :global(.prose h1) {
    font-size: 1.25em;
    font-weight: 600;
  }
  
  :global(.prose h2) {
    font-size: 1.125em;
    font-weight: 600;
  }
  
  :global(.prose h3) {
    font-size: 1em;
    font-weight: 600;
  }
  
  :global(.prose p) {
    margin-top: 0;
    margin-bottom: 1em;
  }
  
  :global(.prose p:last-child) {
    margin-bottom: 0;
  }
  
  :global(.prose ul, .prose ol) {
    margin-top: 0.5em;
    margin-bottom: 1em;
    padding-left: 1.5em;
  }
  
  :global(.prose li) {
    margin-bottom: 0.25em;
  }
  
  :global(.prose blockquote) {
    border-left: 3px solid #d1d5db;
    margin: 1em 0;
    padding-left: 1em;
    color: #6b7280;
  }
  
  :global(.prose code) {
    background-color: #f3f4f6;
    color: #1f2937;
    font-size: 0.875em;
    padding: 0.125em 0.25em;
    border-radius: 0.25rem;
  }
  
  :global(.prose pre) {
    background-color: #1f2937;
    color: #f9fafb;
    padding: 1em;
    border-radius: 0.5rem;
    overflow-x: auto;
    margin: 1em 0;
  }
  
  :global(.prose pre code) {
    background-color: transparent;
    color: inherit;
    padding: 0;
  }
  
  :global(.prose a) {
    color: #3b82f6;
    text-decoration: underline;
  }
  
  :global(.prose a:hover) {
    color: #1d4ed8;
  }
  
  :global(.prose strong) {
    font-weight: 600;
  }
  
  :global(.prose em) {
    font-style: italic;
  }

  /* Group hover for copy button */
  :global(.group) {
    /* Group utility class definition */
  }
  
  .flex:hover .opacity-0 {
    opacity: 1;
  }
</style>