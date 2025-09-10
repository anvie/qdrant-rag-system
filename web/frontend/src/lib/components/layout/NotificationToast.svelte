<script lang="ts">
  import { notifications, notificationActions } from '../../stores/notifications';
  import { slide } from 'svelte/transition';
  import Button from '../common/Button.svelte';
  import Icon from '@iconify/svelte';

  // Handle dismiss
  const dismissNotification = (id: string) => {
    notificationActions.dismiss(id);
  };

  // Handle dismiss all
  const dismissAll = () => {
    notificationActions.dismissAll();
  };

  // Get notification icon
  const getNotificationIcon = (type: string) => {
    switch (type) {
      case 'success':
        return 'material-symbols:check-circle';
      case 'error':
        return 'material-symbols:error';
      case 'warning':
        return 'material-symbols:warning';
      default:
        return 'material-symbols:info';
    }
  };

  // Get notification classes
  const getNotificationClasses = (type: string) => {
    const baseClasses = 'flex items-start gap-3 p-4 rounded-lg shadow-lg border-l-4';
    
    switch (type) {
      case 'success':
        return `${baseClasses} bg-green-50 border-green-500 text-green-800`;
      case 'error':
        return `${baseClasses} bg-red-50 border-red-500 text-red-800`;
      case 'warning':
        return `${baseClasses} bg-yellow-50 border-yellow-500 text-yellow-800`;
      default:
        return `${baseClasses} bg-blue-50 border-blue-500 text-blue-800`;
    }
  };

  // Get icon color classes
  const getIconColorClasses = (type: string) => {
    switch (type) {
      case 'success':
        return 'text-green-500';
      case 'error':
        return 'text-red-500';
      case 'warning':
        return 'text-yellow-500';
      default:
        return 'text-blue-500';
    }
  };

  // Handle action click
  const handleActionClick = (action: () => void, notificationId: string) => {
    action();
    dismissNotification(notificationId);
  };
</script>

<!-- Toast Container -->
{#if $notifications.length > 0}
  <div class="fixed top-4 right-4 z-50 space-y-3 w-full max-w-sm pointer-events-none">
    <!-- Dismiss All Button (when multiple notifications) -->
    {#if $notifications.length > 1}
      <div class="flex justify-end pointer-events-auto">
        <Button
          variant="ghost"
          size="sm"
          onClick={dismissAll}
          class="bg-white shadow-md border border-gray-200 hover:bg-gray-50"
        >
          <Icon icon="material-symbols:close" class="w-4 h-4" />
          Dismiss All
        </Button>
      </div>
    {/if}

    <!-- Notifications -->
    {#each $notifications as notification (notification.id)}
      <div
        transition:slide={{ duration: 300 }}
        class="{getNotificationClasses(notification.type)} pointer-events-auto"
        role="alert"
        aria-live="polite"
      >
        <!-- Icon -->
        <div class="flex-shrink-0 {getIconColorClasses(notification.type)}">
          <Icon icon={getNotificationIcon(notification.type)} class="w-5 h-5" />
        </div>

        <!-- Content -->
        <div class="flex-1 min-w-0">
          <h4 class="text-sm font-medium">
            {notification.title}
          </h4>
          
          {#if notification.message}
            <p class="text-sm opacity-90 mt-1">
              {notification.message}
            </p>
          {/if}

          <!-- Actions -->
          {#if notification.actions && notification.actions.length > 0}
            <div class="flex items-center gap-2 mt-3">
              {#each notification.actions as action}
                <Button
                  variant={action.style || 'ghost'}
                  size="sm"
                  onClick={() => handleActionClick(action.action, notification.id)}
                  class="text-xs"
                >
                  {action.label}
                </Button>
              {/each}
            </div>
          {/if}
        </div>

        <!-- Dismiss button -->
        {#if notification.dismissible}
          <div class="flex-shrink-0">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => dismissNotification(notification.id)}
              ariaLabel="Dismiss notification"
              class="opacity-60 hover:opacity-100 p-1"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
              </svg>
            </Button>
          </div>
        {/if}
      </div>
    {/each}
  </div>
{/if}