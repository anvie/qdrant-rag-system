<script lang="ts">
  import Card from '../common/Card.svelte';
  import LoadingSpinner from '../common/LoadingSpinner.svelte';
  import Icon from '@iconify/svelte';

  // Props
  export let title: string;
  export let value: string | number | null = null;
  export let subtitle: string | null = null;
  export let icon: string | null = null;
  export let color: 'blue' | 'green' | 'purple' | 'red' | 'yellow' | 'gray' = 'blue';
  export let trend: 'up' | 'down' | 'neutral' | null = null;
  export let trendValue: string | null = null;
  export let loading: boolean = false;
  export let clickable: boolean = false;
  export let href: string | null = null;
  export let compact: boolean = false;

  // Event handlers
  export let onClick: ((event: MouseEvent) => void) | undefined = undefined;

  // Color theme classes
  $: colorClasses = {
    blue: {
      bg: 'bg-blue-50',
      text: 'text-blue-600',
      icon: 'text-blue-500',
      border: 'border-blue-200'
    },
    green: {
      bg: 'bg-green-50',
      text: 'text-green-600', 
      icon: 'text-green-500',
      border: 'border-green-200'
    },
    purple: {
      bg: 'bg-purple-50',
      text: 'text-purple-600',
      icon: 'text-purple-500', 
      border: 'border-purple-200'
    },
    red: {
      bg: 'bg-red-50',
      text: 'text-red-600',
      icon: 'text-red-500',
      border: 'border-red-200'
    },
    yellow: {
      bg: 'bg-yellow-50',
      text: 'text-yellow-600',
      icon: 'text-yellow-500',
      border: 'border-yellow-200'
    },
    gray: {
      bg: 'bg-gray-50',
      text: 'text-gray-600',
      icon: 'text-gray-500',
      border: 'border-gray-200'
    }
  };

  // Trend icon
  const getTrendIcon = (trend: string) => {
    switch (trend) {
      case 'up':
        return 'material-symbols:trending-up';
      case 'down':
        return 'material-symbols:trending-down';
      default:
        return null;
    }
  };

  // Trend color
  $: trendColor = trend === 'up' ? 'text-green-600' : trend === 'down' ? 'text-red-600' : 'text-gray-500';

  // Format value for display
  const formatValue = (val: string | number | null): string => {
    if (val === null || val === undefined) return '—';
    if (typeof val === 'number') {
      // Format large numbers
      if (val >= 1000000) {
        return (val / 1000000).toFixed(1) + 'M';
      } else if (val >= 1000) {
        return (val / 1000).toFixed(1) + 'K';
      }
      return val.toLocaleString();
    }
    return String(val);
  };

  // Handle click
  const handleClick = (event: MouseEvent) => {
    if (onClick) {
      onClick(event);
    }
  };
</script>

{#if href && !onClick}
  <a {href} class="block">
    <Card 
      padding={compact ? 'sm' : 'md'}
      hoverable={true}
      bgColor={colorClasses[color].bg}
      border={true}
    >
      <div class="flex items-start justify-between">
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 mb-1">
            {#if icon}
              <div class="flex-shrink-0 {colorClasses[color].icon}">
                <Icon icon={icon} class="w-5 h-5" />
              </div>
            {/if}
            <h3 class="text-sm font-medium text-gray-900 truncate">
              {title}
            </h3>
          </div>

          <div class="mb-1">
            {#if loading}
              <div class="flex items-center gap-2">
                <LoadingSpinner size="sm" color="gray" />
                <span class="text-sm text-gray-500">Loading...</span>
              </div>
            {:else}
              <div class="text-2xl font-bold {colorClasses[color].text}">
                {formatValue(value)}
              </div>
            {/if}
          </div>

          <div class="flex items-center justify-between">
            {#if subtitle}
              <div class="text-sm text-gray-600 truncate">
                {subtitle}
              </div>
            {/if}

            {#if trend && trendValue && !loading}
              <div class="flex items-center gap-1 {trendColor}">
                {#if getTrendIcon(trend)}
                  <Icon icon={getTrendIcon(trend)} class="w-4 h-4" />
                {/if}
                <span class="text-xs font-medium">
                  {trendValue}
                </span>
              </div>
            {/if}
          </div>
        </div>

        <div class="flex-shrink-0 ml-4">
          <Icon icon="material-symbols:chevron-right" class="w-5 h-5 text-gray-400" />
        </div>
      </div>
    </Card>
  </a>
{:else}
  <Card 
    padding={compact ? 'sm' : 'md'}
    hoverable={clickable}
    clickable={clickable}
    onClick={handleClick}
    bgColor={colorClasses[color].bg}
    border={true}
  >
    <div class="flex items-start justify-between">
      <div class="flex-1 min-w-0">
        <!-- Title -->
        <div class="flex items-center gap-2 mb-1">
          {#if icon}
            <div class="flex-shrink-0 {colorClasses[color].icon}">
              <Icon icon={icon} class="w-5 h-5" />
            </div>
          {/if}
          <h3 class="text-sm font-medium text-gray-900 truncate">
            {title}
          </h3>
        </div>

        <!-- Value -->
        <div class="mb-1">
          {#if loading}
            <div class="flex items-center gap-2">
              <LoadingSpinner size="sm" color="gray" />
              <span class="text-sm text-gray-500">Loading...</span>
            </div>
          {:else}
            <div class="text-2xl font-bold {colorClasses[color].text}">
              {formatValue(value)}
            </div>
          {/if}
        </div>

        <!-- Subtitle and Trend -->
        <div class="flex items-center justify-between">
          {#if subtitle}
            <div class="text-sm text-gray-600 truncate">
              {subtitle}
            </div>
          {/if}

          {#if trend && trendValue && !loading}
            <div class="flex items-center gap-1 {trendColor}">
              <span class="text-xs">
                {@html getTrendIcon(trend)}
              </span>
              <span class="text-xs font-medium">
                {trendValue}
              </span>
            </div>
          {/if}
        </div>
      </div>

      <!-- Optional clickable indicator -->
      {#if clickable || href}
        <div class="flex-shrink-0 ml-4">
          <Icon icon="material-symbols:chevron-right" class="w-5 h-5 text-gray-400" />
        </div>
      {/if}
    </div>
  </Card>
{/if}