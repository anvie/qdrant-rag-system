/**
 * System status store for managing real-time system monitoring
 */

import { writable, derived } from 'svelte/store';
import type { SystemStatus, HealthResponse, ServiceHealth, ModelsResponse } from '../services/api';
import { api } from '../services/api';
import { websocketService } from '../services/websocket';

// Store interfaces
export interface SystemState {
  status: SystemStatus | null;
  health: HealthResponse | null;
  models: ModelsResponse | null;
  connectionStatus: ConnectionStatus;
  loading: boolean;
  error: string | null;
  lastUpdated: Date | null;
}

export interface ConnectionStatus {
  websocket: boolean;
  api: boolean;
  qdrant: boolean;
  ollama: boolean;
}

// Initial state
const initialSystemState: SystemState = {
  status: null,
  health: null,
  models: null,
  connectionStatus: {
    websocket: false,
    api: false,
    qdrant: false,
    ollama: false,
  },
  loading: false,
  error: null,
  lastUpdated: null,
};

// Main system store
export const systemStore = writable<SystemState>(initialSystemState);

// Derived stores for easy access to specific data
export const systemStatus = derived(systemStore, ($system) => $system.status);
export const healthStatus = derived(systemStore, ($system) => $system.health);
export const modelsInfo = derived(systemStore, ($system) => $system.models);
export const connectionStatus = derived(systemStore, ($system) => $system.connectionStatus);
export const isLoading = derived(systemStore, ($system) => $system.loading);
export const systemError = derived(systemStore, ($system) => $system.error);

// Derived store for overall system health
export const overallHealth = derived(systemStore, ($system) => {
  if (!$system.health) return 'unknown';
  
  const services = $system.health.services;
  const healthyServices = services.filter(s => s.status === 'healthy');
  
  if (healthyServices.length === services.length) return 'healthy';
  if (healthyServices.length === 0) return 'unhealthy';
  return 'partial';
});

// Derived store for service status summary
export const servicesSummary = derived(systemStore, ($system) => {
  if (!$system.health) return { total: 0, healthy: 0, unhealthy: 0 };
  
  const services = $system.health.services;
  return {
    total: services.length,
    healthy: services.filter(s => s.status === 'healthy').length,
    unhealthy: services.filter(s => s.status !== 'healthy').length,
  };
});

// WebSocket message handler
let wsConnected = false;
const handleWebSocketMessage = (message: any) => {
  systemStore.update(state => {
    switch (message.type) {
      case 'system_status':
        return {
          ...state,
          status: message.data,
          lastUpdated: new Date(),
          connectionStatus: { ...state.connectionStatus, websocket: true }
        };
      
      case 'health_update':
        return {
          ...state,
          health: message.data,
          lastUpdated: new Date(),
          connectionStatus: {
            ...state.connectionStatus,
            websocket: true,
            qdrant: message.data.services.find((s: ServiceHealth) => s.service === 'qdrant')?.status === 'healthy',
            ollama: message.data.services.find((s: ServiceHealth) => s.service === 'ollama')?.status === 'healthy',
          }
        };
      
      case 'connection_status':
        return {
          ...state,
          connectionStatus: { ...state.connectionStatus, ...message.data },
          lastUpdated: new Date(),
        };
      
      default:
        return state;
    }
  });
};

// System store actions
export const systemActions = {
  /**
   * Initialize system monitoring with WebSocket connection
   */
  async initialize(): Promise<void> {
    systemStore.update(state => ({ ...state, loading: true, error: null }));
    
    try {
      // Load initial data
      await this.loadSystemData();
      
      // Connect to WebSocket for real-time updates
      if (!wsConnected) {
        await websocketService.connect('/system', handleWebSocketMessage);
        wsConnected = true;
        
        systemStore.update(state => ({
          ...state,
          connectionStatus: { ...state.connectionStatus, websocket: true }
        }));
      }
      
    } catch (error) {
      console.error('Failed to initialize system monitoring:', error);
      systemStore.update(state => ({
        ...state,
        error: error instanceof Error ? error.message : 'Failed to initialize system monitoring',
        connectionStatus: { ...state.connectionStatus, api: false }
      }));
    } finally {
      systemStore.update(state => ({ ...state, loading: false }));
    }
  },

  /**
   * Load system data from API
   */
  async loadSystemData(): Promise<void> {
    systemStore.update(state => ({ ...state, loading: true, error: null }));
    
    try {
      // Load all system data in parallel
      const [status, health, models] = await Promise.all([
        api.getSystemStatus(),
        api.getHealth(),
        api.getModels(),
      ]);

      systemStore.update(state => ({
        ...state,
        status,
        health,
        models,
        lastUpdated: new Date(),
        connectionStatus: {
          ...state.connectionStatus,
          api: true,
          qdrant: health.services.find(s => s.service === 'qdrant')?.status === 'healthy' || false,
          ollama: health.services.find(s => s.service === 'ollama')?.status === 'healthy' || false,
        }
      }));
      
    } catch (error) {
      console.error('Failed to load system data:', error);
      systemStore.update(state => ({
        ...state,
        error: error instanceof Error ? error.message : 'Failed to load system data',
        connectionStatus: { ...state.connectionStatus, api: false }
      }));
    } finally {
      systemStore.update(state => ({ ...state, loading: false }));
    }
  },

  /**
   * Refresh system status manually
   */
  async refresh(): Promise<void> {
    await this.loadSystemData();
  },

  /**
   * Clear error state
   */
  clearError(): void {
    systemStore.update(state => ({ ...state, error: null }));
  },

  /**
   * Reset store to initial state
   */
  reset(): void {
    systemStore.set(initialSystemState);
    if (wsConnected) {
      websocketService.disconnect('/system');
      wsConnected = false;
    }
  },

  /**
   * Check specific service health
   */
  isServiceHealthy(serviceName: string): boolean {
    let currentState: SystemState;
    systemStore.subscribe(state => currentState = state)();
    
    if (!currentState.health) return false;
    
    const service = currentState.health.services.find(s => s.service === serviceName);
    return service?.status === 'healthy';
  },

  /**
   * Get service response time
   */
  getServiceResponseTime(serviceName: string): number | null {
    let currentState: SystemState;
    systemStore.subscribe(state => currentState = state)();
    
    if (!currentState.health) return null;
    
    const service = currentState.health.services.find(s => s.service === serviceName);
    return service?.response_time_ms || null;
  },
};

// Auto-cleanup on page unload
if (typeof window !== 'undefined') {
  window.addEventListener('beforeunload', () => {
    systemActions.reset();
  });
}

export default systemStore;