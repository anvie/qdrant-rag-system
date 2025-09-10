<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import Card from '../common/Card.svelte';
  import Button from '../common/Button.svelte';
  import LoadingSpinner from '../common/LoadingSpinner.svelte';
  import Icon from '@iconify/svelte';
  import { 
    systemStore, 
    systemActions, 
    overallHealth, 
    servicesSummary,
    connectionStatus,
    isLoading,
    systemError
  } from '../../stores/system';

  // Component state
  let refreshInterval: NodeJS.Timeout | null = null;
  let autoRefresh = true;
  const refreshIntervalMs = 30000; // 30 seconds

  // Reactive values from stores
  $: health = $systemStore.health;
  $: status = $systemStore.status;
  $: lastUpdated = $systemStore.lastUpdated;
  
  // Format uptime
  const formatUptime = (uptime: string | undefined): string => {
    if (!uptime) return 'Unknown';
    // Parse uptime format and make it human readable
    return uptime;
  };

  // Format timestamp
  const formatTimestamp = (date: Date | null): string => {
    if (!date) return 'Never';
    return new Intl.DateTimeFormat('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    }).format(date);
  };

  // Get status badge classes
  const getStatusBadgeClass = (status: string): string => {
    switch (status) {
      case 'healthy':
      case 'ready':
      case 'active':
        return 'status-healthy';
      case 'unhealthy':
      case 'error':
      case 'failed':
        return 'status-unhealthy';
      default:
        return 'status-unknown';
    }
  };

  // Get connection indicator color
  const getConnectionColor = (connected: boolean): string => {
    return connected ? 'bg-green-500' : 'bg-red-500';
  };

  // Handle manual refresh
  const handleRefresh = async () => {
    await systemActions.refresh();
  };

  // Toggle auto-refresh
  const toggleAutoRefresh = () => {
    autoRefresh = !autoRefresh;
    if (autoRefresh) {
      startAutoRefresh();
    } else {
      stopAutoRefresh();
    }
  };

  // Start auto-refresh interval
  const startAutoRefresh = () => {
    if (refreshInterval) clearInterval(refreshInterval);
    refreshInterval = setInterval(async () => {
      if (autoRefresh) {
        await systemActions.refresh();
      }
    }, refreshIntervalMs);
  };

  // Stop auto-refresh interval
  const stopAutoRefresh = () => {
    if (refreshInterval) {
      clearInterval(refreshInterval);
      refreshInterval = null;
    }
  };

  // Lifecycle hooks
  onMount(async () => {
    await systemActions.initialize();
    if (autoRefresh) {
      startAutoRefresh();
    }
  });

  onDestroy(() => {
    stopAutoRefresh();
    systemActions.reset();
  });
</script>

<Card>
  <div slot="header" class="flex items-center justify-between">
    <div class="flex items-center gap-3">
      <h2 class="text-lg font-semibold text-gray-900">System Status</h2>
      <!-- Overall health indicator -->
      <div class="flex items-center gap-2">
        <div class="w-3 h-3 rounded-full {getConnectionColor($connectionStatus.api)}"></div>
        <span class="{getStatusBadgeClass($overallHealth)}">
          {$overallHealth.charAt(0).toUpperCase() + $overallHealth.slice(1)}
        </span>
      </div>
    </div>

    <div class="flex items-center gap-2">
      <!-- Auto-refresh toggle -->
      <Button 
        variant="ghost" 
        size="sm"
        onClick={toggleAutoRefresh}
        ariaLabel={autoRefresh ? 'Disable auto-refresh' : 'Enable auto-refresh'}
      >
        <Icon icon="material-symbols:refresh" class="w-4 h-4 {!autoRefresh ? 'opacity-50' : ''}" />
      </Button>
      
      <!-- Manual refresh -->
      <Button 
        variant="ghost" 
        size="sm" 
        loading={$isLoading}
        onClick={handleRefresh}
        ariaLabel="Refresh status"
      >
        <Icon icon="material-symbols:refresh" class="w-4 h-4" />
      </Button>
    </div>
  </div>

  <!-- Loading state -->
  {#if $isLoading && !health}
    <div class="flex items-center justify-center py-12">
      <LoadingSpinner size="lg" showLabel={true} label="Loading system status..." />
    </div>

  <!-- Error state -->
  {:else if $systemError}
    <div class="text-center py-8">
      <div class="text-red-600 mb-4">
        <Icon icon="material-symbols:warning" class="w-12 h-12 mx-auto mb-2" />
      </div>
      <h3 class="text-lg font-medium text-gray-900 mb-2">System Status Error</h3>
      <p class="text-gray-600 mb-4">{$systemError}</p>
      <Button onClick={handleRefresh} variant="primary">
        Try Again
      </Button>
    </div>

  <!-- Main content -->
  {:else}
    <div class="space-y-6">
      <!-- Connection Status -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div class="text-center p-3 bg-gray-50 rounded-lg">
          <div class="flex items-center justify-center mb-2">
            <div class="w-3 h-3 rounded-full {getConnectionColor($connectionStatus.api)}"></div>
            <span class="ml-2 text-sm font-medium">API</span>
          </div>
          <span class="text-xs text-gray-600">{$connectionStatus.api ? 'Connected' : 'Disconnected'}</span>
        </div>

        <div class="text-center p-3 bg-gray-50 rounded-lg">
          <div class="flex items-center justify-center mb-2">
            <div class="w-3 h-3 rounded-full {getConnectionColor($connectionStatus.qdrant)}"></div>
            <span class="ml-2 text-sm font-medium">Qdrant</span>
          </div>
          <span class="text-xs text-gray-600">{$connectionStatus.qdrant ? 'Connected' : 'Disconnected'}</span>
        </div>

        <div class="text-center p-3 bg-gray-50 rounded-lg">
          <div class="flex items-center justify-center mb-2">
            <div class="w-3 h-3 rounded-full {getConnectionColor($connectionStatus.ollama)}"></div>
            <span class="ml-2 text-sm font-medium">Ollama</span>
          </div>
          <span class="text-xs text-gray-600">{$connectionStatus.ollama ? 'Connected' : 'Disconnected'}</span>
        </div>

        <div class="text-center p-3 bg-gray-50 rounded-lg">
          <div class="flex items-center justify-center mb-2">
            <div class="w-3 h-3 rounded-full {getConnectionColor($connectionStatus.websocket)}"></div>
            <span class="ml-2 text-sm font-medium">WebSocket</span>
          </div>
          <span class="text-xs text-gray-600">{$connectionStatus.websocket ? 'Connected' : 'Disconnected'}</span>
        </div>
      </div>

      <!-- Services Status -->
      {#if health?.services}
        <div>
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-md font-medium text-gray-900">Services</h3>
            <div class="text-sm text-gray-600">
              {$servicesSummary.healthy}/{$servicesSummary.total} healthy
            </div>
          </div>
          
          <div class="space-y-3">
            {#each health.services as service}
              <div class="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                <div class="flex items-center gap-3">
                  <div class="flex items-center gap-2">
                    <div class="w-2 h-2 rounded-full {service.status === 'healthy' ? 'bg-green-500' : 'bg-red-500'}"></div>
                    <span class="font-medium text-gray-900 capitalize">{service.service}</span>
                  </div>
                  <span class="{getStatusBadgeClass(service.status)}">
                    {service.status.charAt(0).toUpperCase() + service.status.slice(1)}
                  </span>
                </div>

                <div class="text-right text-sm text-gray-600">
                  {#if service.response_time_ms}
                    <div>{service.response_time_ms}ms</div>
                  {/if}
                  {#if service.url}
                    <div class="text-xs opacity-75">{service.url}</div>
                  {/if}
                  {#if service.error}
                    <div class="text-xs text-red-600 max-w-xs truncate">{service.error}</div>
                  {/if}
                </div>
              </div>
            {/each}
          </div>
        </div>
      {/if}

      <!-- System Information -->
      {#if status}
        <div>
          <h3 class="text-md font-medium text-gray-900 mb-4">System Information</h3>
          <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div class="text-center p-4 bg-blue-50 rounded-lg">
              <div class="text-2xl font-bold text-blue-600 mb-1">
                {status.active_connections || 0}
              </div>
              <div class="text-sm text-blue-800">Active Connections</div>
            </div>
            
            <div class="text-center p-4 bg-green-50 rounded-lg">
              <div class="text-2xl font-bold text-green-600 mb-1">
                {formatUptime(status.uptime)}
              </div>
              <div class="text-sm text-green-800">System Uptime</div>
            </div>

            <div class="text-center p-4 bg-purple-50 rounded-lg">
              <div class="text-2xl font-bold text-purple-600 mb-1">
                {formatTimestamp(lastUpdated)}
              </div>
              <div class="text-sm text-purple-800">Last Updated</div>
            </div>
          </div>
        </div>
      {/if}
    </div>
  {/if}
</Card>