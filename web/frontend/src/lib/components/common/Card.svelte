<script lang="ts">
  // Card component with flexible layout options
  export let padding: 'none' | 'sm' | 'md' | 'lg' = 'md';
  export let shadow: 'none' | 'sm' | 'md' | 'lg' | 'xl' = 'md';
  export let border: boolean = true;
  export let rounded: 'none' | 'sm' | 'md' | 'lg' | 'xl' = 'lg';
  export let bgColor: string = 'bg-white';
  export let hoverable: boolean = false;
  export let clickable: boolean = false;
  export let fullHeight: boolean = false;
  
  // Event handlers
  export let onClick: ((event: MouseEvent) => void) | undefined = undefined;

  // Reactive classes
  $: paddingClasses = {
    none: '',
    sm: 'p-3',
    md: 'p-4 sm:p-6',
    lg: 'p-6 sm:p-8'
  };

  $: shadowClasses = {
    none: '',
    sm: 'shadow-sm',
    md: 'shadow-md',
    lg: 'shadow-lg',
    xl: 'shadow-xl'
  };

  $: roundedClasses = {
    none: '',
    sm: 'rounded-sm',
    md: 'rounded-md',
    lg: 'rounded-lg',
    xl: 'rounded-xl'
  };

  $: baseClasses = `${bgColor} ${shadowClasses[shadow]} ${roundedClasses[rounded]}`;
  $: borderClass = border ? 'border border-gray-200' : '';
  $: heightClass = fullHeight ? 'h-full' : '';
  $: hoverClass = hoverable ? 'hover:shadow-lg transition-shadow duration-200' : '';
  $: cursorClass = clickable || onClick ? 'cursor-pointer' : '';
  
  $: cardClasses = `${baseClasses} ${borderClass} ${heightClass} ${hoverClass} ${cursorClass}`;
  
  // Handle click events
  const handleClick = (event: MouseEvent) => {
    if (onClick) {
      onClick(event);
    }
  };
</script>

<div 
  class={cardClasses}
  class:flex={fullHeight}
  class:flex-col={fullHeight}
  on:click={handleClick}
  on:keydown={(e) => {
    if (clickable && (e.key === 'Enter' || e.key === ' ')) {
      handleClick(e);
    }
  }}
  role={clickable ? 'button' : undefined}
  tabindex={clickable ? 0 : undefined}
>
  {#if $$slots.header}
    <div class="card-header {paddingClasses[padding]} pb-0">
      <slot name="header" />
    </div>
  {/if}

  <div class="card-body {paddingClasses[padding]}" class:flex-1={fullHeight}>
    <slot />
  </div>

  {#if $$slots.footer}
    <div class="card-footer {paddingClasses[padding]} pt-0 border-t border-gray-200">
      <slot name="footer" />
    </div>
  {/if}
</div>

<style>
  .card-header {
    border-bottom: 1px solid #f3f4f6;
  }
  
  .card-footer {
    margin-top: auto;
  }
</style>