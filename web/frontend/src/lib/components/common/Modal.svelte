<script lang="ts">
  import Icon from '@iconify/svelte';
  import Button from './Button.svelte';

  // Modal component props
  export let show: boolean = false;
  export let title: string = '';
  export let size: 'sm' | 'md' | 'lg' | 'xl' = 'md';
  export let closable: boolean = true;
  export let showHeader: boolean = true;
  export let showFooter: boolean = false;

  // Event handlers
  export let onClose: (() => void) | undefined = undefined;

  // Size classes
  const sizeClasses = {
    sm: 'max-w-sm',
    md: 'max-w-md', 
    lg: 'max-w-2xl',
    xl: 'max-w-4xl'
  };

  // Handle close
  const handleClose = () => {
    if (closable) {
      show = false;
      onClose?.();
    }
  };

  // Handle backdrop click
  const handleBackdropClick = (event: MouseEvent) => {
    if (event.target === event.currentTarget) {
      handleClose();
    }
  };

  // Handle escape key
  const handleKeydown = (event: KeyboardEvent) => {
    if (event.key === 'Escape' && closable) {
      handleClose();
    }
  };
</script>

<svelte:window on:keydown={handleKeydown} />

{#if show}
  <div 
    class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50"
    on:click={handleBackdropClick}
    on:keydown={handleKeydown}
    role="dialog"
    aria-modal="true"
    aria-labelledby={title ? 'modal-title' : undefined}
    tabindex="-1"
  >
    <div class="bg-white rounded-lg {sizeClasses[size]} w-full max-h-[90vh] flex flex-col shadow-xl">
      <!-- Header -->
      {#if showHeader}
        <div class="flex items-center justify-between p-6 border-b border-gray-200">
          <h2 id="modal-title" class="text-xl font-semibold text-gray-900">
            {title}
          </h2>
          {#if closable}
            <Button 
              variant="ghost" 
              size="sm" 
              onClick={handleClose}
              ariaLabel="Close modal"
            >
              <Icon icon="material-symbols:close" class="w-5 h-5" />
            </Button>
          {/if}
        </div>
      {/if}

      <!-- Body -->
      <div class="flex-1 overflow-y-auto p-6">
        <slot />
      </div>

      <!-- Footer -->
      {#if showFooter}
        <div class="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-200">
          <slot name="footer" />
        </div>
      {/if}
    </div>
  </div>
{/if}