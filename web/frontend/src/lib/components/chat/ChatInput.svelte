<script lang="ts">
  import { createEventDispatcher, onMount } from "svelte";
  import Icon from "@iconify/svelte";
  
  import Button from "../common/Button.svelte";
  
  const dispatch = createEventDispatcher();
  
  // Props
  export let placeholder = "Type your message...";
  export let disabled = false;
  export let autoFocus = false;
  export let maxLength = 2000;
  export let multiline = true;
  
  // Local state
  let inputElement: HTMLTextAreaElement;
  let message = "";
  let isComposing = false;
  
  onMount(() => {
    if (autoFocus && inputElement) {
      inputElement.focus();
    }
    
    // Auto-resize textarea
    if (inputElement) {
      adjustHeight();
    }
  });
  
  function adjustHeight() {
    if (inputElement) {
      inputElement.style.height = 'auto';
      inputElement.style.height = Math.min(inputElement.scrollHeight, 120) + 'px';
    }
  }
  
  function handleInput() {
    adjustHeight();
  }
  
  function handleKeyDown(event: KeyboardEvent) {
    // Handle composition (e.g., Asian input methods)
    if (isComposing) return;
    
    if (event.key === 'Enter') {
      if (event.shiftKey || event.ctrlKey) {
        // Shift+Enter or Ctrl+Enter: new line
        return;
      } else {
        // Enter: send message
        event.preventDefault();
        handleSend();
      }
    }
  }
  
  function handleCompositionStart() {
    isComposing = true;
  }
  
  function handleCompositionEnd() {
    isComposing = false;
  }
  
  function handleSend() {
    const trimmedMessage = message.trim();
    if (!trimmedMessage || disabled) return;
    
    dispatch('send', {
      message: trimmedMessage
    });
    
    // Clear input
    message = "";
    if (inputElement) {
      inputElement.style.height = 'auto';
      inputElement.focus();
    }
  }
  
  function handlePaste(event: ClipboardEvent) {
    // Allow default paste behavior, but check length after
    setTimeout(() => {
      if (message.length > maxLength) {
        message = message.substring(0, maxLength);
        adjustHeight();
      }
    }, 0);
  }
  
  // Reactive statement for character count
  $: charactersRemaining = maxLength - message.length;
  $: isNearLimit = charactersRemaining < 100;
  $: canSend = message.trim().length > 0 && !disabled;
</script>

<div class="relative">
  <div class="flex items-end gap-2 p-3 bg-gray-50 rounded-lg border border-gray-200 focus-within:border-blue-500 transition-colors">
    <!-- Message Input -->
    <div class="flex-1 min-h-[2.5rem] relative">
      <textarea
        bind:this={inputElement}
        bind:value={message}
        {placeholder}
        {disabled}
        maxlength={maxLength}
        class="
          w-full resize-none border-none bg-transparent text-gray-900 
          placeholder-gray-500 focus:outline-none focus:ring-0
          text-sm leading-6
        "
        style="height: 2.5rem; min-height: 2.5rem; max-height: 120px;"
        rows="1"
        on:input={handleInput}
        on:keydown={handleKeyDown}
        on:compositionstart={handleCompositionStart}
        on:compositionend={handleCompositionEnd}
        on:paste={handlePaste}
      ></textarea>
    </div>
    
    <!-- Send Button -->
    <div class="flex-shrink-0 pb-1">
      <Button
        variant={canSend ? "primary" : "ghost"}
        size="sm"
        onClick={handleSend}
        {disabled}
        class="!p-2 !min-w-0"
        ariaLabel="Send message"
      >
        <Icon 
          icon={canSend ? "material-symbols:send" : "material-symbols:send-outline"} 
          class="w-4 h-4" 
        />
      </Button>
    </div>
  </div>
  
  <!-- Character Counter -->
  {#if isNearLimit}
    <div class="absolute -top-6 right-0 text-xs {charactersRemaining < 0 ? 'text-red-500' : 'text-gray-500'}">
      {charactersRemaining} characters remaining
    </div>
  {/if}
  
  <!-- Keyboard Shortcuts Hint -->
  <div class="flex justify-between items-center mt-2 text-xs text-gray-500">
    <div>
      <span class="font-medium">Enter</span> to send
      <span class="mx-2">•</span>
      <span class="font-medium">Shift + Enter</span> for new line
    </div>
    
    {#if disabled}
      <div class="flex items-center gap-1 text-orange-500">
        <Icon icon="material-symbols:warning" class="w-3 h-3" />
        <span>Disconnected</span>
      </div>
    {/if}
  </div>
</div>

<style>
  /* Remove default textarea styling */
  textarea {
    font-family: inherit;
    line-height: 1.5;
  }
  
  /* Custom scrollbar for textarea */
  textarea::-webkit-scrollbar {
    width: 4px;
  }
  
  textarea::-webkit-scrollbar-track {
    background: transparent;
  }
  
  textarea::-webkit-scrollbar-thumb {
    background-color: #cbd5e0;
    border-radius: 2px;
  }
  
  textarea::-webkit-scrollbar-thumb:hover {
    background-color: #a0aec0;
  }
</style>