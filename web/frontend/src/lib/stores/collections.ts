/**
 * Collections store for managing collection data and operations
 */

import { writable, derived } from "svelte/store";
import type { Collection, CollectionStats, CollectionRecord, CollectionRecordsResponse } from "../services/api";
import { api } from "../services/api";
import { websocketService } from "../services/websocket";

// Store interfaces
export interface CollectionState {
  collections: Collection[];
  selectedCollection: Collection | null;
  collectionStats: Map<string, CollectionStats>;
  collectionRecords: Map<string, CollectionRecordsResponse>;
  loading: boolean;
  error: string | null;
  lastUpdated: Date | null;
  operationInProgress: OperationType | null;
}

export type OperationType = "create" | "delete" | "refresh" | null;

export interface CreateCollectionData {
  name: string;
  vector_size?: number;
  distance_metric?: string;
  embedding_model?: string;
  description?: string;
}

// Initial state
const initialCollectionState: CollectionState = {
  collections: [],
  selectedCollection: null,
  collectionStats: new Map(),
  collectionRecords: new Map(),
  loading: false,
  error: null,
  lastUpdated: null,
  operationInProgress: null,
};

// Main collections store
export const collectionsStore = writable<CollectionState>(
  initialCollectionState,
);

// Derived stores for easy access
export const collections = derived(
  collectionsStore,
  ($collections) => $collections.collections,
);
export const selectedCollection = derived(
  collectionsStore,
  ($collections) => $collections.selectedCollection,
);
export const collectionsLoading = derived(
  collectionsStore,
  ($collections) => $collections.loading,
);
export const collectionsError = derived(
  collectionsStore,
  ($collections) => $collections.error,
);
export const operationInProgress = derived(
  collectionsStore,
  ($collections) => $collections.operationInProgress,
);

// Derived store for individual collection stats Map
export const collectionStatsMap = derived(
  collectionsStore,
  ($collections) => $collections.collectionStats,
);

// Derived store for collection statistics
export const collectionsStats = derived(collectionsStore, ($collections) => {
  const stats = {
    total: $collections.collections.length,
    totalPoints: 0,
    totalVectors: 0,
    activeCollections: 0,
  };

  $collections.collections.forEach((collection) => {
    stats.totalPoints += collection.points_count;
    stats.totalVectors += collection.vectors_count;
    if (collection.status === "ready" || collection.status === "active") {
      stats.activeCollections++;
    }
  });

  return stats;
});

// Derived store for sorted collections (by name)
export const sortedCollections = derived(collections, ($collections) => {
  return [...$collections].sort((a, b) => a.name.localeCompare(b.name));
});

// WebSocket message handler for collection updates
let wsConnected = false;
const handleWebSocketMessage = (message: any) => {
  collectionsStore.update((state) => {
    switch (message.type) {
      case "collection_created":
        return {
          ...state,
          collections: [...state.collections, message.data],
          lastUpdated: new Date(),
        };

      case "collection_deleted":
        return {
          ...state,
          collections: state.collections.filter(
            (c) => c.name !== message.data.name,
          ),
          selectedCollection:
            state.selectedCollection?.name === message.data.name
              ? null
              : state.selectedCollection,
          lastUpdated: new Date(),
        };

      case "collection_updated":
        return {
          ...state,
          collections: state.collections.map((c) =>
            c.name === message.data.name ? { ...c, ...message.data } : c,
          ),
          selectedCollection:
            state.selectedCollection?.name === message.data.name
              ? { ...state.selectedCollection, ...message.data }
              : state.selectedCollection,
          lastUpdated: new Date(),
        };

      case "collection_stats":
        const newStats = new Map(state.collectionStats);
        newStats.set(message.data.name, message.data);
        return {
          ...state,
          collectionStats: newStats,
          lastUpdated: new Date(),
        };

      default:
        return state;
    }
  });
};

// Collections store actions
export const collectionsActions = {
  /**
   * Initialize collections monitoring
   */
  async initialize(): Promise<void> {
    collectionsStore.update((state) => ({
      ...state,
      loading: true,
      error: null,
    }));

    try {
      // Load initial collections
      await this.loadCollections();

      // Connect to WebSocket for real-time updates
      if (!wsConnected) {
        await websocketService.connect("/collections", handleWebSocketMessage);
        wsConnected = true;
      }
    } catch (error) {
      console.error("Failed to initialize collections:", error);
      collectionsStore.update((state) => ({
        ...state,
        error:
          error instanceof Error
            ? error.message
            : "Failed to initialize collections",
      }));
    } finally {
      collectionsStore.update((state) => ({ ...state, loading: false }));
    }
  },

  /**
   * Load collections from API
   */
  async loadCollections(): Promise<void> {
    collectionsStore.update((state) => ({
      ...state,
      loading: true,
      error: null,
    }));

    try {
      const collections = await api.getCollections();

      collectionsStore.update((state) => ({
        ...state,
        collections,
        lastUpdated: new Date(),
      }));
    } catch (error) {
      console.error("Failed to load collections:", error);
      collectionsStore.update((state) => ({
        ...state,
        error:
          error instanceof Error ? error.message : "Failed to load collections",
      }));
    } finally {
      collectionsStore.update((state) => ({ ...state, loading: false }));
    }
  },

  /**
   * Load statistics for a specific collection
   */
  async loadCollectionStats(
    collectionName: string,
  ): Promise<CollectionStats | null> {
    try {
      const stats = await api.getCollectionStats(collectionName);

      collectionsStore.update((state) => {
        const newStats = new Map(state.collectionStats);
        newStats.set(collectionName, stats);
        return {
          ...state,
          collectionStats: newStats,
          lastUpdated: new Date(),
        };
      });

      return stats;
    } catch (error) {
      console.error(
        `Failed to load stats for collection ${collectionName}:`,
        error,
      );
      collectionsStore.update((state) => ({
        ...state,
        error:
          error instanceof Error
            ? error.message
            : `Failed to load stats for ${collectionName}`,
      }));
      return null;
    }
  },

  /**
   * Create a new collection
   */
  async createCollection(
    data: CreateCollectionData,
  ): Promise<Collection | null> {
    collectionsStore.update((state) => ({
      ...state,
      operationInProgress: "create",
      error: null,
    }));

    try {
      const collection = await api.createCollection(data);

      collectionsStore.update((state) => ({
        ...state,
        collections: [...state.collections, collection],
        lastUpdated: new Date(),
      }));

      return collection;
    } catch (error) {
      console.error("Failed to create collection:", error);
      collectionsStore.update((state) => ({
        ...state,
        error:
          error instanceof Error
            ? error.message
            : "Failed to create collection",
      }));
      return null;
    } finally {
      collectionsStore.update((state) => ({
        ...state,
        operationInProgress: null,
      }));
    }
  },

  /**
   * Delete a collection
   */
  async deleteCollection(collectionName: string): Promise<boolean> {
    collectionsStore.update((state) => ({
      ...state,
      operationInProgress: "delete",
      error: null,
    }));

    try {
      await api.deleteCollection(collectionName);

      collectionsStore.update((state) => ({
        ...state,
        collections: state.collections.filter((c) => c.name !== collectionName),
        selectedCollection:
          state.selectedCollection?.name === collectionName
            ? null
            : state.selectedCollection,
        lastUpdated: new Date(),
      }));

      // Remove stats from cache
      collectionsStore.update((state) => {
        const newStats = new Map(state.collectionStats);
        newStats.delete(collectionName);
        return {
          ...state,
          collectionStats: newStats,
        };
      });

      return true;
    } catch (error) {
      console.error(`Failed to delete collection ${collectionName}:`, error);
      collectionsStore.update((state) => ({
        ...state,
        error:
          error instanceof Error
            ? error.message
            : `Failed to delete collection ${collectionName}`,
      }));
      return false;
    } finally {
      collectionsStore.update((state) => ({
        ...state,
        operationInProgress: null,
      }));
    }
  },

  /**
   * Select a collection
   */
  selectCollection(collection: Collection | null): void {
    collectionsStore.update((state) => ({
      ...state,
      selectedCollection: collection,
    }));
  },

  /**
   * Refresh collections data
   */
  async refresh(): Promise<void> {
    collectionsStore.update((state) => ({
      ...state,
      operationInProgress: "refresh",
    }));

    await this.loadCollections();

    collectionsStore.update((state) => ({
      ...state,
      operationInProgress: null,
    }));
  },

  /**
   * Get collection statistics from cache
   */
  getCollectionStats(collectionName: string): CollectionStats | null {
    let currentState: CollectionState;
    collectionsStore.subscribe((state) => (currentState = state))();

    return currentState.collectionStats.get(collectionName) || null;
  },

  /**
   * Check if collection exists
   */
  collectionExists(collectionName: string): boolean {
    let currentState: CollectionState;
    collectionsStore.subscribe((state) => (currentState = state))();

    return currentState.collections.some((c) => c.name === collectionName);
  },

  /**
   * Clear error state
   */
  clearError(): void {
    collectionsStore.update((state) => ({ ...state, error: null }));
  },

  /**
   * Reset store to initial state
   */
  reset(): void {
    collectionsStore.set(initialCollectionState);
    if (wsConnected) {
      websocketService.disconnect("/collections");
      wsConnected = false;
    }
  },

  /**
   * Load statistics for all collections
   */
  async loadAllCollectionStats(): Promise<void> {
    let currentState: CollectionState;
    collectionsStore.subscribe((state) => (currentState = state))();

    const loadPromises = currentState.collections.map((collection) =>
      this.loadCollectionStats(collection.name),
    );

    await Promise.allSettled(loadPromises);
  },

  /**
   * Get available embedding models
   */
  async getAvailableEmbeddingModels() {
    try {
      return await api.getAvailableEmbeddingModels();
    } catch (error) {
      console.error("Failed to load embedding models:", error);
      throw error;
    }
  },

  /**
   * Get recommended embedding models
   */
  async getRecommendedEmbeddingModels(useCase?: string) {
    try {
      return await api.getRecommendedEmbeddingModels(useCase);
    } catch (error) {
      console.error("Failed to load recommended models:", error);
      throw error;
    }
  },

  /**
   * Validate an embedding model
   */
  async validateEmbeddingModel(modelName: string) {
    try {
      return await api.validateEmbeddingModel(modelName);
    } catch (error) {
      console.error(`Failed to validate model ${modelName}:`, error);
      throw error;
    }
  },

  /**
   * Get collection records
   */
  async getCollectionRecords(
    collectionName: string,
    page: number = 1,
    pageSize: number = 20
  ): Promise<CollectionRecordsResponse | null> {
    try {
      const response = await api.getCollectionRecords(collectionName, page, pageSize);
      
      collectionsStore.update((state) => {
        const newRecords = new Map(state.collectionRecords);
        newRecords.set(`${collectionName}_${page}_${pageSize}`, response);
        return {
          ...state,
          collectionRecords: newRecords,
        };
      });
      
      return response;
    } catch (error) {
      console.error(`Failed to get records for ${collectionName}:`, error);
      collectionsStore.update((state) => ({
        ...state,
        error:
          error instanceof Error
            ? error.message
            : `Failed to get records for ${collectionName}`,
      }));
      return null;
    }
  },

  /**
   * Add records to collection
   */
  async addRecords(
    collectionName: string,
    records: Array<{ title: string; content: string; metadata?: any }>
  ): Promise<boolean> {
    collectionsStore.update((state) => ({
      ...state,
      operationInProgress: "create",
      error: null,
    }));

    try {
      await api.addRecords(collectionName, records);
      
      // Clear cached records to force refresh
      collectionsStore.update((state) => {
        const newRecords = new Map(state.collectionRecords);
        // Remove all cached pages for this collection
        for (const key of newRecords.keys()) {
          if (key.startsWith(`${collectionName}_`)) {
            newRecords.delete(key);
          }
        }
        return {
          ...state,
          collectionRecords: newRecords,
        };
      });
      
      // Refresh collection stats
      await this.loadCollectionStats(collectionName);
      
      return true;
    } catch (error) {
      console.error(`Failed to add records to ${collectionName}:`, error);
      collectionsStore.update((state) => ({
        ...state,
        error:
          error instanceof Error
            ? error.message
            : `Failed to add records to ${collectionName}`,
      }));
      return false;
    } finally {
      collectionsStore.update((state) => ({
        ...state,
        operationInProgress: null,
      }));
    }
  },

  /**
   * Delete a single record
   */
  async deleteRecord(
    collectionName: string,
    recordId: number
  ): Promise<boolean> {
    try {
      await api.deleteRecord(collectionName, recordId);
      
      // Clear cached records
      collectionsStore.update((state) => {
        const newRecords = new Map(state.collectionRecords);
        for (const key of newRecords.keys()) {
          if (key.startsWith(`${collectionName}_`)) {
            newRecords.delete(key);
          }
        }
        return {
          ...state,
          collectionRecords: newRecords,
        };
      });
      
      // Refresh collection stats
      await this.loadCollectionStats(collectionName);
      
      return true;
    } catch (error) {
      console.error(`Failed to delete record ${recordId}:`, error);
      collectionsStore.update((state) => ({
        ...state,
        error:
          error instanceof Error
            ? error.message
            : `Failed to delete record`,
      }));
      return false;
    }
  },

  /**
   * Delete multiple records
   */
  async deleteRecords(
    collectionName: string,
    recordIds: number[]
  ): Promise<boolean> {
    collectionsStore.update((state) => ({
      ...state,
      operationInProgress: "delete",
      error: null,
    }));

    try {
      await api.deleteRecords(collectionName, recordIds);
      
      // Clear cached records
      collectionsStore.update((state) => {
        const newRecords = new Map(state.collectionRecords);
        for (const key of newRecords.keys()) {
          if (key.startsWith(`${collectionName}_`)) {
            newRecords.delete(key);
          }
        }
        return {
          ...state,
          collectionRecords: newRecords,
        };
      });
      
      // Refresh collection stats
      await this.loadCollectionStats(collectionName);
      
      return true;
    } catch (error) {
      console.error(`Failed to delete ${recordIds.length} records:`, error);
      collectionsStore.update((state) => ({
        ...state,
        error:
          error instanceof Error
            ? error.message
            : `Failed to delete records`,
      }));
      return false;
    } finally {
      collectionsStore.update((state) => ({
        ...state,
        operationInProgress: null,
      }));
    }
  },
};

// Auto-cleanup on page unload
if (typeof window !== "undefined") {
  window.addEventListener("beforeunload", () => {
    collectionsActions.reset();
  });
}

export default collectionsStore;
