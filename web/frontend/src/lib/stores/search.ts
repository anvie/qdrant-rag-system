/**
 * Search store for managing search state and operations
 */

import { writable, derived, get } from 'svelte/store';
import { api, type SearchRequest, type SearchResponse, type SearchResult, type ArticleResponse } from '../services/api';
import { notificationActions } from './notifications';

export interface SearchFilters {
  collection: string;
  limit: number;
  min_score: number;
  hybrid: boolean;
  fusion_method: string;
  group_by_article: boolean;
}

export interface SearchHistoryItem {
  id: string;
  query: string;
  filters: SearchFilters;
  timestamp: number;
  results_count: number;
  query_time: number;
}

export interface SearchState {
  // Query state
  query: string;
  filters: SearchFilters;
  
  // Results state
  results: SearchResult[];
  currentResponse: SearchResponse | null;
  
  // UI state
  loading: boolean;
  error: string | null;
  
  // History and cache
  history: SearchHistoryItem[];
  
  // Current article view
  currentArticle: ArticleResponse | null;
  articleLoading: boolean;
}

// Initial state
const initialFilters: SearchFilters = {
  collection: 'articles',
  limit: 10,
  min_score: 0.0,
  hybrid: false,
  fusion_method: 'rrf',
  group_by_article: false
};

const initialState: SearchState = {
  query: '',
  filters: { ...initialFilters },
  results: [],
  currentResponse: null,
  loading: false,
  error: null,
  history: [],
  currentArticle: null,
  articleLoading: false
};

// Create writable stores
const searchState = writable<SearchState>(initialState);

// Load search history from localStorage on init
if (typeof window !== 'undefined') {
  const savedHistory = localStorage.getItem('search_history');
  if (savedHistory) {
    try {
      const history = JSON.parse(savedHistory);
      searchState.update(state => ({ ...state, history }));
    } catch (e) {
      console.warn('Failed to load search history from localStorage:', e);
    }
  }
}

// Derived stores
export const searchQuery = derived(searchState, $state => $state.query);
export const searchFilters = derived(searchState, $state => $state.filters);
export const searchResults = derived(searchState, $state => $state.results);
export const searchLoading = derived(searchState, $state => $state.loading);
export const searchError = derived(searchState, $state => $state.error);
export const searchHistory = derived(searchState, $state => $state.history);
export const currentSearchResponse = derived(searchState, $state => $state.currentResponse);
export const currentArticle = derived(searchState, $state => $state.currentArticle);
export const articleLoading = derived(searchState, $state => $state.articleLoading);

// Search statistics
export const searchStats = derived(searchState, $state => ({
  totalResults: $state.results.length,
  uniqueArticles: new Set($state.results.map(r => r.article_id)).size,
  avgScore: $state.results.length > 0 
    ? $state.results.reduce((sum, r) => sum + r.score, 0) / $state.results.length 
    : 0,
  queryTime: $state.currentResponse?.query_time || 0
}));

// Actions
export const searchActions = {
  // Update query
  setQuery: (query: string) => {
    searchState.update(state => ({ 
      ...state, 
      query,
      error: null 
    }));
  },

  // Update filters
  updateFilters: (newFilters: Partial<SearchFilters>) => {
    searchState.update(state => ({
      ...state,
      filters: { ...state.filters, ...newFilters },
      error: null
    }));
  },

  // Reset filters to defaults
  resetFilters: () => {
    searchState.update(state => ({
      ...state,
      filters: { ...initialFilters }
    }));
  },

  // Execute search
  executeSearch: async (customQuery?: string, customFilters?: Partial<SearchFilters>) => {
    const currentState = get(searchState);
    const query = customQuery || currentState.query;
    const filters = customFilters ? { ...currentState.filters, ...customFilters } : currentState.filters;

    console.log('ExecuteSearch called with query:', query, 'filters:', filters);

    if (!query.trim()) {
      notificationActions.error('Search query cannot be empty', 'Please enter a search term');
      return;
    }

    searchState.update(state => ({ 
      ...state, 
      loading: true, 
      error: null,
      results: []
    }));

    try {
      const searchRequest: SearchRequest = {
        query,
        collection: filters.collection,
        limit: filters.limit,
        min_score: filters.min_score,
        hybrid: filters.hybrid,
        fusion_method: filters.fusion_method,
        group_by_article: filters.group_by_article
      };

      const response = await api.search(searchRequest);

      // Add to history
      const historyItem: SearchHistoryItem = {
        id: Date.now().toString(),
        query,
        filters: { ...filters },
        timestamp: Date.now(),
        results_count: response.total_found,
        query_time: response.query_time
      };

      searchState.update(state => {
        const newHistory = [historyItem, ...state.history.slice(0, 49)]; // Keep last 50 searches
        
        // Save to localStorage
        if (typeof window !== 'undefined') {
          try {
            localStorage.setItem('search_history', JSON.stringify(newHistory));
          } catch (e) {
            console.warn('Failed to save search history to localStorage:', e);
          }
        }

        return {
          ...state,
          loading: false,
          results: response.results,
          currentResponse: response,
          history: newHistory,
          query,
          filters
        };
      });

      notificationActions.success(
        'Search completed',
        `Found ${response.total_found} results in ${(response.query_time * 1000).toFixed(0)}ms`
      );

    } catch (error: any) {
      console.error('Search failed:', error);
      const errorMessage = error.response?.data?.detail || error.message || 'Search failed';
      
      searchState.update(state => ({ 
        ...state, 
        loading: false,
        error: errorMessage,
        results: []
      }));

      notificationActions.error('Search failed', errorMessage);
    }
  },

  // Search from history
  searchFromHistory: (historyItem: SearchHistoryItem) => {
    searchState.update(state => ({
      ...state,
      query: historyItem.query,
      filters: historyItem.filters
    }));
    
    searchActions.executeSearch(historyItem.query, historyItem.filters);
  },

  // Clear search results
  clearResults: () => {
    searchState.update(state => ({
      ...state,
      results: [],
      currentResponse: null,
      error: null,
      query: ''
    }));
  },

  // Clear search history
  clearHistory: () => {
    searchState.update(state => ({ ...state, history: [] }));
    
    if (typeof window !== 'undefined') {
      localStorage.removeItem('search_history');
    }
    
    notificationActions.info('Search history cleared', 'All previous searches have been removed');
  },

  // Load full article
  loadArticle: async (articleId: number, collection?: string) => {
    searchState.update(state => ({ 
      ...state, 
      articleLoading: true,
      currentArticle: null
    }));

    try {
      const article = await api.getArticle(articleId, collection);
      
      searchState.update(state => ({
        ...state,
        articleLoading: false,
        currentArticle: article
      }));

      notificationActions.success('Article loaded', `Loaded ${article.total_chunks} chunks`);
      
    } catch (error: any) {
      const errorMessage = error.response?.data?.detail || error.message || 'Failed to load article';
      
      searchState.update(state => ({ 
        ...state, 
        articleLoading: false,
        currentArticle: null
      }));

      notificationActions.error('Failed to load article', errorMessage);
    }
  },

  // Close article view
  closeArticle: () => {
    searchState.update(state => ({
      ...state,
      currentArticle: null
    }));
  },

  // Find similar documents
  findSimilar: async (documentId: number, collection?: string, limit?: number) => {
    searchState.update(state => ({ 
      ...state, 
      loading: true, 
      error: null 
    }));

    try {
      const response = await api.findSimilar(documentId, collection, limit);
      
      searchState.update(state => ({
        ...state,
        loading: false,
        results: response.results,
        currentResponse: response,
        query: response.query
      }));

      notificationActions.success(
        'Similar documents found',
        `Found ${response.total_found} similar documents`
      );
      
    } catch (error: any) {
      const errorMessage = error.response?.data?.detail || error.message || 'Failed to find similar documents';
      
      searchState.update(state => ({ 
        ...state, 
        loading: false,
        error: errorMessage 
      }));

      notificationActions.error('Failed to find similar documents', errorMessage);
    }
  },

  // Reset entire search state
  reset: () => {
    searchState.set(initialState);
  }
};

// Export the store and actions
export default searchState;