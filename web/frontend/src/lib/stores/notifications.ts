/**
 * Notifications store for managing toast messages and user feedback
 */

import { writable, derived, get } from "svelte/store";

// Notification interfaces
export interface Notification {
  id: string;
  type: NotificationType;
  title: string;
  message?: string;
  duration?: number;
  dismissible?: boolean;
  actions?: NotificationAction[];
  timestamp: Date;
  dismissed: boolean;
}

export type NotificationType = "success" | "error" | "warning" | "info";

export interface NotificationAction {
  label: string;
  action: () => void;
  style?: "primary" | "secondary";
}

export interface NotificationOptions {
  type?: NotificationType;
  message?: string;
  duration?: number;
  dismissible?: boolean;
  actions?: NotificationAction[];
}

// Store state
interface NotificationsState {
  notifications: Notification[];
  maxNotifications: number;
  defaultDuration: number;
}

// Initial state
const initialState: NotificationsState = {
  notifications: [],
  maxNotifications: 5,
  defaultDuration: 5000, // 5 seconds
};

// Main notifications store
export const notificationsStore = writable<NotificationsState>(initialState);

// Derived stores
export const notifications = derived(notificationsStore, ($state) =>
  $state.notifications.filter((n) => !n.dismissed),
);

export const hasNotifications = derived(
  notifications,
  ($notifications) => $notifications.length > 0,
);

export const notificationCount = derived(
  notifications,
  ($notifications) => $notifications.length,
);

// Utility functions
const generateId = (): string => {
  return `notification-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
};

const createNotification = (
  title: string,
  options: NotificationOptions = {},
): Notification => {
  const {
    type = "info",
    message,
    duration,
    dismissible = true,
    actions = [],
  } = options;

  return {
    id: generateId(),
    type,
    title,
    message,
    duration: duration !== undefined ? duration : initialState.defaultDuration,
    dismissible,
    actions,
    timestamp: new Date(),
    dismissed: false,
  };
};

// Auto-dismiss timeout handlers
const timeoutHandlers = new Map<string, NodeJS.Timeout>();

const setAutoDismiss = (notification: Notification) => {
  if (notification.duration && notification.duration > 0) {
    const timeout = setTimeout(() => {
      notificationActions.dismiss(notification.id);
      timeoutHandlers.delete(notification.id);
    }, notification.duration);

    timeoutHandlers.set(notification.id, timeout);
  }
};

const clearAutoDismiss = (notificationId: string) => {
  const timeout = timeoutHandlers.get(notificationId);
  if (timeout) {
    clearTimeout(timeout);
    timeoutHandlers.delete(notificationId);
  }
};

// Notification actions
export const notificationActions = {
  /**
   * Add a notification to the store
   */
  add(title: string, options: NotificationOptions = {}): string {
    const notification = createNotification(title, options);

    notificationsStore.update((state) => {
      const newNotifications = [...state.notifications, notification];

      // Limit the number of notifications
      if (newNotifications.length > state.maxNotifications) {
        const excess = newNotifications.slice(
          0,
          newNotifications.length - state.maxNotifications,
        );
        excess.forEach((n) => clearAutoDismiss(n.id));
        return {
          ...state,
          notifications: newNotifications.slice(-state.maxNotifications),
        };
      }

      return {
        ...state,
        notifications: newNotifications,
      };
    });

    // Set auto-dismiss if duration is specified
    setAutoDismiss(notification);

    return notification.id;
  },

  /**
   * Add success notification
   */
  success(title: string, message?: string, duration?: number): string {
    return this.add(title, {
      type: "success",
      message,
      duration: duration !== undefined ? duration : 4000,
    });
  },

  /**
   * Add error notification
   */
  error(title: string, message?: string, duration?: number): string {
    return this.add(title, {
      type: "error",
      message,
      duration: duration !== undefined ? duration : 8000,
    });
  },

  /**
   * Add warning notification
   */
  warning(title: string, message?: string, duration?: number): string {
    return this.add(title, {
      type: "warning",
      message,
      duration: duration !== undefined ? duration : 6000,
    });
  },

  /**
   * Add info notification
   */
  info(title: string, message?: string, duration?: number): string {
    return this.add(title, {
      type: "info",
      message,
      duration: duration !== undefined ? duration : 5000,
    });
  },

  /**
   * Add persistent notification (no auto-dismiss)
   */
  persistent(
    title: string,
    options: Omit<NotificationOptions, "duration"> = {},
  ): string {
    return this.add(title, { ...options, duration: 0 });
  },

  /**
   * Dismiss a notification
   */
  dismiss(notificationId: string): void {
    clearAutoDismiss(notificationId);

    notificationsStore.update((state) => ({
      ...state,
      notifications: state.notifications.map((n) =>
        n.id === notificationId ? { ...n, dismissed: true } : n,
      ),
    }));

    // Remove dismissed notification after animation time
    setTimeout(() => {
      notificationsStore.update((state) => ({
        ...state,
        notifications: state.notifications.filter(
          (n) => n.id !== notificationId,
        ),
      }));
    }, 300); // Match CSS transition duration
  },

  /**
   * Dismiss all notifications
   */
  dismissAll(): void {
    notificationsStore.update((state) => {
      // Clear all timeouts
      state.notifications.forEach((n) => clearAutoDismiss(n.id));

      return {
        ...state,
        notifications: state.notifications.map((n) => ({
          ...n,
          dismissed: true,
        })),
      };
    });

    // Remove all after animation
    setTimeout(() => {
      notificationsStore.update((state) => ({
        ...state,
        notifications: [],
      }));
    }, 300);
  },

  /**
   * Remove a notification immediately (no animation)
   */
  remove(notificationId: string): void {
    clearAutoDismiss(notificationId);

    notificationsStore.update((state) => ({
      ...state,
      notifications: state.notifications.filter((n) => n.id !== notificationId),
    }));
  },

  /**
   * Clear all notifications immediately
   */
  clear(): void {
    notificationsStore.update((state) => {
      // Clear all timeouts
      state.notifications.forEach((n) => clearAutoDismiss(n.id));

      return {
        ...state,
        notifications: [],
      };
    });
  },

  /**
   * Update notification settings
   */
  updateSettings(
    settings: Partial<
      Pick<NotificationsState, "maxNotifications" | "defaultDuration">
    >,
  ): void {
    notificationsStore.update((state) => ({
      ...state,
      ...settings,
    }));
  },

  /**
   * Get notification by ID
   */
  getById(notificationId: string): Notification | null {
    let currentState: NotificationsState = get(notificationsStore);
    
    return (
      currentState.notifications.find((n) => n.id === notificationId) || null
    );
  },

  /**
   * Check if a notification exists
   */
  exists(notificationId: string): boolean {
    return this.getById(notificationId) !== null;
  },

  /**
   * Pause auto-dismiss for a notification (useful for hover states)
   */
  pauseAutoDismiss(notificationId: string): void {
    clearAutoDismiss(notificationId);
  },

  /**
   * Resume auto-dismiss for a notification
   */
  resumeAutoDismiss(notificationId: string, remainingTime?: number): void {
    const notification = this.getById(notificationId);
    if (!notification || !notification.duration) return;

    const timeout = setTimeout(() => {
      this.dismiss(notificationId);
    }, remainingTime || notification.duration);

    timeoutHandlers.set(notificationId, timeout);
  },
};

// Preset notification messages for common scenarios
export const presetNotifications = {
  // API related
  apiError: (operation: string, error?: string) =>
    notificationActions.error(
      "API Error",
      error || `Failed to ${operation}. Please try again.`,
    ),

  apiSuccess: (operation: string) =>
    notificationActions.success(
      "Success",
      `${operation} completed successfully.`,
    ),

  // Connection related
  connectionLost: () =>
    notificationActions.warning("Connection Lost", "Trying to reconnect..."),

  connectionRestored: () =>
    notificationActions.success("Connection Restored", "You are back online."),

  // Collection related
  collectionCreated: (name: string) =>
    notificationActions.success(
      "Collection Created",
      `Collection "${name}" has been created successfully.`,
    ),

  collectionDeleted: (name: string) =>
    notificationActions.info(
      "Collection Deleted",
      `Collection "${name}" has been removed.`,
    ),

  collectionError: (operation: string, name: string, error?: string) =>
    notificationActions.error(
      "Collection Error",
      error || `Failed to ${operation} collection "${name}".`,
    ),

  // System related
  systemError: (error?: string) =>
    notificationActions.error(
      "System Error",
      error || "A system error occurred. Please check the system status.",
    ),

  systemHealthy: () =>
    notificationActions.success(
      "System Healthy",
      "All services are running normally.",
    ),
};

// Auto-cleanup on page unload
if (typeof window !== "undefined") {
  window.addEventListener("beforeunload", () => {
    // Clear all timeouts
    timeoutHandlers.forEach((timeout) => clearTimeout(timeout));
    timeoutHandlers.clear();
  });
}

export default notificationsStore;
