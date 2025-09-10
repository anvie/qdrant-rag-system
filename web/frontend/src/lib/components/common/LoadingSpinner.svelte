<script lang="ts">
  // LoadingSpinner component with multiple sizes and colors
  import Icon from '@iconify/svelte';
  
  export let size: 'xs' | 'sm' | 'md' | 'lg' | 'xl' = 'md';
  export let color: 'primary' | 'secondary' | 'white' | 'gray' = 'primary';
  export let centered: boolean = false;
  export let label: string = 'Loading...';
  export let showLabel: boolean = false;
  export let inline: boolean = false;

  // Size classes
  $: sizeClasses = {
    xs: 'h-3 w-3',
    sm: 'h-4 w-4', 
    md: 'h-6 w-6',
    lg: 'h-8 w-8',
    xl: 'h-12 w-12'
  };

  // Color classes
  $: colorClasses = {
    primary: 'text-blue-600',
    secondary: 'text-gray-600', 
    white: 'text-white',
    gray: 'text-gray-400'
  };

  // Container classes
  $: containerClasses = centered ? 'flex items-center justify-center' : '';
  $: displayClass = inline ? 'inline-flex' : 'flex';
  $: gapClass = showLabel ? 'gap-3' : '';
  
  // Label text size based on spinner size
  $: labelSizeClass = {
    xs: 'text-xs',
    sm: 'text-sm',
    md: 'text-sm',
    lg: 'text-base', 
    xl: 'text-lg'
  };
</script>

<div class="{displayClass} items-center {containerClasses} {gapClass}">
  <!-- Spinner Icon -->
  <Icon 
    icon="material-symbols:progress-activity"
    class="{sizeClasses[size]} {colorClasses[color]}"
    aria-label={label}
    role="status"
  />
  
  <!-- Optional label -->
  {#if showLabel}
    <span class="{labelSizeClass[size]} {colorClasses[color]} font-medium">
      {label}
    </span>
  {/if}
</div>

<!-- Screen reader only text -->
<span class="sr-only">{label}</span>