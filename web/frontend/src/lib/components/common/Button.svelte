<script lang="ts">
  // Button component with multiple variants and states
  import Icon from '@iconify/svelte';
  
  export let variant: 'primary' | 'secondary' | 'danger' | 'success' | 'ghost' = 'primary';
  export let size: 'sm' | 'md' | 'lg' = 'md';
  export let loading: boolean = false;
  export let disabled: boolean = false;
  export let fullWidth: boolean = false;
  export let href: string | null = null;
  export let type: 'button' | 'submit' | 'reset' = 'button';
  export let icon: string | null = null;
  export let iconPosition: 'left' | 'right' = 'left';
  export let ariaLabel: string | undefined = undefined;

  // Event handlers
  export let onClick: ((event: MouseEvent) => void) | undefined = undefined;

  // Reactive class computation
  $: baseClasses = 'inline-flex items-center justify-center font-medium rounded-lg transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:cursor-not-allowed';
  
  $: variantClasses = {
    primary: 'bg-blue-600 hover:bg-blue-700 text-white focus:ring-blue-500 disabled:bg-blue-300',
    secondary: 'bg-gray-200 hover:bg-gray-300 text-gray-900 focus:ring-gray-500 disabled:bg-gray-100 disabled:text-gray-400',
    danger: 'bg-red-600 hover:bg-red-700 text-white focus:ring-red-500 disabled:bg-red-300',
    success: 'bg-green-600 hover:bg-green-700 text-white focus:ring-green-500 disabled:bg-green-300',
    ghost: 'bg-transparent hover:bg-gray-100 text-gray-700 focus:ring-gray-500 disabled:text-gray-400'
  };
  
  $: sizeClasses = {
    sm: 'px-3 py-1.5 text-sm gap-1.5',
    md: 'px-4 py-2 text-sm gap-2',
    lg: 'px-6 py-3 text-base gap-2.5'
  };

  $: widthClass = fullWidth ? 'w-full' : '';
  
  $: buttonClasses = `${baseClasses} ${variantClasses[variant]} ${sizeClasses[size]} ${widthClass}`;

  // Handle click events
  const handleClick = (event: MouseEvent) => {
    if (loading || disabled) {
      event.preventDefault();
      return;
    }
    onClick?.(event);
  };
</script>

<!-- Render as anchor if href is provided -->
{#if href}
  <a 
    {href}
    class={buttonClasses}
    class:opacity-50={loading || disabled}
    class:pointer-events-none={loading || disabled}
    aria-label={ariaLabel}
    role="button"
    tabindex={disabled ? -1 : 0}
    on:click={handleClick}
  >
    {#if loading}
      <Icon icon="material-symbols:progress-activity" class="h-4 w-4 text-current" />
    {:else if icon && iconPosition === 'left'}
      <Icon icon={icon} class="w-4 h-4" />
    {/if}
    
    <slot />
    
    {#if icon && iconPosition === 'right' && !loading}
      <Icon icon={icon} class="w-4 h-4" />
    {/if}
  </a>
{:else}
  <button
    {type}
    class={buttonClasses}
    disabled={loading || disabled}
    aria-label={ariaLabel}
    on:click={handleClick}
  >
    {#if loading}
      <Icon icon="material-symbols:progress-activity" class="h-4 w-4 text-current" />
    {:else if icon && iconPosition === 'left'}
      <Icon icon={icon} class="w-4 h-4" />
    {/if}
    
    <slot />
    
    {#if icon && iconPosition === 'right' && !loading}
      <Icon icon={icon} class="w-4 h-4" />
    {/if}
  </button>
{/if}

<style>
  :global(.icon svg) {
    width: 1rem;
    height: 1rem;
  }
  
  :global(.icon) {
    display: flex;
    align-items: center;
    justify-content: center;
  }
</style>