/**
 * API service for communicating with FastAPI backend
 */

import axios from 'axios';
import type { AxiosInstance, AxiosResponse } from 'axios';

const API_BASE_URL = '/api/v1';

export interface Collection {
  name: string;
  points_count: number;
  vectors_count: number;
  status: string;
}

export interface CollectionStats {
  name: string;
  points_count: number;
  vectors_count: number;
  status: string;
  config: {
    vector_size: number;
    distance: string;
  };
}

export interface SystemStatus {
  qdrant_status: string;
  ollama_status: string;
  active_connections: number;
  uptime: string;
}

export interface ServiceHealth {
  service: string;
  status: string;
  url: string;
  response_time_ms?: number;
  error?: string;
}

export interface HealthResponse {
  status: string;
  services: ServiceHealth[];
  timestamp: number;
}

export interface ModelInfo {
  name: string;
  size: number;
  modified_at: string;
}

export interface ModelsResponse {
  embedding_models: ModelInfo[];
  llm_models: ModelInfo[];
  total_models: number;
}

class ApiService {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Request interceptor
    this.client.interceptors.request.use(
      (config) => {
        console.log(`API Request: ${config.method?.toUpperCase()} ${config.url}`);
        return config;
      },
      (error) => {
        console.error('API Request Error:', error);
        return Promise.reject(error);
      }
    );

    // Response interceptor
    this.client.interceptors.response.use(
      (response: AxiosResponse) => {
        console.log(`API Response: ${response.status} ${response.config.url}`);
        return response;
      },
      (error) => {
        console.error('API Response Error:', error);
        if (error.response?.status === 401) {
          // Handle unauthorized access
          console.warn('Unauthorized access - redirect to login');
        }
        return Promise.reject(error);
      }
    );
  }

  // System endpoints
  async getSystemStatus(): Promise<SystemStatus> {
    const response = await this.client.get<SystemStatus>('/system/status');
    return response.data;
  }

  async getHealth(): Promise<HealthResponse> {
    const response = await this.client.get<HealthResponse>('/system/health');
    return response.data;
  }

  async getModels(): Promise<ModelsResponse> {
    const response = await this.client.get<ModelsResponse>('/system/models');
    return response.data;
  }

  // Collections endpoints
  async getCollections(): Promise<Collection[]> {
    const response = await this.client.get<Collection[]>('/collections/');
    return response.data;
  }

  async getCollectionStats(collectionName: string): Promise<CollectionStats> {
    const response = await this.client.get<CollectionStats>(`/collections/${collectionName}/stats`);
    return response.data;
  }

  async createCollection(data: {
    name: string;
    vector_size: number;
    distance_metric?: string;
  }): Promise<Collection> {
    const response = await this.client.post<Collection>('/collections/', data);
    return response.data;
  }

  async deleteCollection(collectionName: string): Promise<{ message: string }> {
    const response = await this.client.delete(`/collections/${collectionName}`);
    return response.data;
  }

  // Generic HTTP methods
  async get<T = any>(endpoint: string): Promise<T> {
    const response = await this.client.get<T>(endpoint);
    return response.data;
  }

  async post<T = any>(endpoint: string, data?: any): Promise<T> {
    const response = await this.client.post<T>(endpoint, data);
    return response.data;
  }

  async put<T = any>(endpoint: string, data?: any): Promise<T> {
    const response = await this.client.put<T>(endpoint, data);
    return response.data;
  }

  async delete<T = any>(endpoint: string): Promise<T> {
    const response = await this.client.delete<T>(endpoint);
    return response.data;
  }
}

// Export singleton instance
export const api = new ApiService();
export default api;