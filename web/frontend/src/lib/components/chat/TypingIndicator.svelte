<script lang="ts">
  import Icon from "@iconify/svelte";
  
  // Props
  export let message = "Assistant is typing...";
  export let showAvatar = true;
</script>

<div class="flex gap-3 items-start">
  <!-- Avatar -->
  {#if showAvatar}
    <div class="flex-shrink-0">
      <div class="w-8 h-8 rounded-full bg-green-500 flex items-center justify-center text-white text-sm font-medium">
        <Icon icon="material-symbols:smart_toy" class="w-5 h-5" />
      </div>
    </div>
  {/if}

  <!-- Typing Indicator -->
  <div class="flex-1">
    <div class="inline-block bg-white border border-gray-200 rounded-lg px-4 py-2 shadow-sm">
      <div class="flex items-center gap-2">
        <!-- Animated dots -->
        <div class="flex space-x-1">
          <div class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 0ms;"></div>
          <div class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 150ms;"></div>
          <div class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 300ms;"></div>
        </div>
        
        <!-- Message -->
        <span class="text-sm text-gray-600 ml-1">{message}</span>
      </div>
    </div>
  </div>
</div>

<style>
  @keyframes bounce {
    0%, 80%, 100% {
      transform: scale(0.8);
      opacity: 0.5;
    }
    40% {
      transform: scale(1);
      opacity: 1;
    }
  }
  
  .animate-bounce {
    animation: bounce 1.4s infinite ease-in-out;
  }
</style>