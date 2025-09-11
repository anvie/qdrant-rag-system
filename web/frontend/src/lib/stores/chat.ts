/**
 * Chat store for managing conversation state and interactions
 */

import { writable, derived, get } from "svelte/store";
import { api } from "../services/api";
import type { AxiosError } from "axios";

// Types
export interface ChatMessage {
  id: string;
  session_id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  response_time_ms?: number;
  sources?: Source[];
  search_query?: string;
}

export interface Source {
  index: number;
  title: string;
  article_id: number | string;
  chunk_index: number;
  score: number;
}

export interface ChatSession {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  collection_name: string;
  llm_model: string;
  embedding_model: string;
  temperature: number;
  top_k: number;
  min_score: number;
  max_context_length: number;
  max_tokens: number;
  system_prompt?: string;
  show_sources: boolean;
  message_count: number;
}

export interface StreamingState {
  isStreaming: boolean;
  currentContent: string;
  statusMessage: string;
  sources: Source[];
}

export interface ChatState {
  // Session management
  currentSession: ChatSession | null;
  sessions: ChatSession[];
  
  // Messages
  messages: ChatMessage[];
  
  // UI state
  isLoading: boolean;
  connectionStatus: "connecting" | "connected" | "disconnected" | "error";
  
  // Streaming state
  streaming: StreamingState;
  
  // Error handling
  lastError: string | null;
}

// Initial state
const initialState: ChatState = {
  currentSession: null,
  sessions: [],
  messages: [],
  isLoading: false,
  connectionStatus: "disconnected",
  streaming: {
    isStreaming: false,
    currentContent: "",
    statusMessage: "",
    sources: []
  },
  lastError: null,
};

// Create writable store
const chatStore = writable<ChatState>(initialState);

// Derived stores for easier access
export const currentSession = derived(chatStore, ($store) => $store.currentSession);
export const messages = derived(chatStore, ($store) => $store.messages);
export const isLoading = derived(chatStore, ($store) => $store.isLoading);
export const connectionStatus = derived(chatStore, ($store) => $store.connectionStatus);
export const streamingState = derived(chatStore, ($store) => $store.streaming);

// Chat actions
export const chatActions = {
  // Initialize chat store
  async initialize() {
    chatStore.update((state) => ({
      ...state,
      isLoading: true,
      lastError: null,
    }));

    try {
      // Load recent sessions
      await this.loadSessions();
    } catch (error) {
      console.error("Failed to initialize chat store:", error);
      chatStore.update((state) => ({
        ...state,
        lastError: this.getErrorMessage(error),
      }));
    } finally {
      chatStore.update((state) => ({
        ...state,
        isLoading: false,
      }));
    }
  },

  // Session management
  async createNewSession(options?: {
    title?: string;
    collection_name?: string;
    llm_model?: string;
    embedding_model?: string;
    temperature?: number;
    top_k?: number;
    min_score?: number;
    max_context_length?: number;
    max_tokens?: number;
    system_prompt?: string;
    show_sources?: boolean;
  }): Promise<ChatSession> {
    chatStore.update((state) => ({
      ...state,
      isLoading: true,
      lastError: null,
    }));

    try {
      const session = await api.post<ChatSession>("/chat/sessions", options || {});
      
      chatStore.update((state) => ({
        ...state,
        currentSession: session,
        sessions: [session, ...state.sessions],
        messages: [],
        isLoading: false,
      }));

      // Remember this new session
      this.rememberLastSession(session.id);

      return session;
    } catch (error) {
      const errorMsg = this.getErrorMessage(error);
      chatStore.update((state) => ({
        ...state,
        lastError: errorMsg,
        isLoading: false,
      }));
      throw error;
    }
  },

  async loadSession(sessionId: string): Promise<void> {
    chatStore.update((state) => ({
      ...state,
      isLoading: true,
      lastError: null,
    }));

    try {
      // Load session details
      const session = await api.get<ChatSession>(`/chat/sessions/${sessionId}`);
      
      // Load session messages
      const messages = await api.get<ChatMessage[]>(`/chat/sessions/${sessionId}/messages`);

      chatStore.update((state) => ({
        ...state,
        currentSession: session,
        messages: messages,
        isLoading: false,
      }));
      
      // Remember this session for future page loads
      this.rememberLastSession(sessionId);
    } catch (error) {
      const errorMsg = this.getErrorMessage(error);
      chatStore.update((state) => ({
        ...state,
        lastError: errorMsg,
        isLoading: false,
      }));
      throw error;
    }
  },

  async loadSessions(limit = 20, offset = 0): Promise<void> {
    try {
      const sessions = await api.get<ChatSession[]>(`/chat/sessions?limit=${limit}&offset=${offset}`);
      
      chatStore.update((state) => ({
        ...state,
        sessions: offset === 0 ? sessions : [...state.sessions, ...sessions],
      }));
    } catch (error) {
      console.error("Failed to load sessions:", error);
      throw error;
    }
  },

  async deleteSession(sessionId: string): Promise<void> {
    try {
      await api.delete(`/chat/sessions/${sessionId}`);
      
      chatStore.update((state) => ({
        ...state,
        sessions: state.sessions.filter(s => s.id !== sessionId),
        // Clear current session if it was deleted
        currentSession: state.currentSession?.id === sessionId ? null : state.currentSession,
        messages: state.currentSession?.id === sessionId ? [] : state.messages,
      }));
    } catch (error) {
      console.error("Failed to delete session:", error);
      throw error;
    }
  },

  async updateSessionSettings(sessionId: string, settings: Partial<ChatSession>): Promise<void> {
    try {
      const updatedSession = await api.put<ChatSession>(`/chat/sessions/${sessionId}`, settings);
      
      chatStore.update((state) => ({
        ...state,
        currentSession: state.currentSession?.id === sessionId ? updatedSession : state.currentSession,
        sessions: state.sessions.map(s => s.id === sessionId ? updatedSession : s),
      }));
    } catch (error) {
      console.error("Failed to update session settings:", error);
      throw error;
    }
  },

  // Message management
  async addUserMessage(content: string): Promise<void> {
    const currentState = get(chatStore);
    if (!currentState.currentSession) {
      throw new Error("No active session");
    }

    // Create temporary message for immediate UI update
    const tempMessage: ChatMessage = {
      id: `temp-${Date.now()}`,
      session_id: currentState.currentSession.id,
      role: "user",
      content,
      created_at: new Date().toISOString(),
    };

    chatStore.update((state) => ({
      ...state,
      messages: [...state.messages, tempMessage],
    }));

    // The actual message will be added via WebSocket or API response
  },

  async sendMessage(content: string, stream = true): Promise<void> {
    const currentState = get(chatStore);
    if (!currentState.currentSession) {
      throw new Error("No active session");
    }

    chatStore.update((state) => ({
      ...state,
      isLoading: true,
      lastError: null,
    }));

    try {
      const response = await api.post(`/chat/sessions/${currentState.currentSession.id}/messages`, {
        message: content,
        stream,
      });

      if (!stream) {
        // Handle non-streaming response
        chatStore.update((state) => ({
          ...state,
          messages: [...state.messages, response.message],
          isLoading: false,
        }));
      }
      // Streaming responses are handled via WebSocket
    } catch (error) {
      const errorMsg = this.getErrorMessage(error);
      chatStore.update((state) => ({
        ...state,
        lastError: errorMsg,
        isLoading: false,
      }));
      throw error;
    }
  },

  // Streaming management
  setConnectionStatus(status: ChatState["connectionStatus"]): void {
    chatStore.update((state) => ({
      ...state,
      connectionStatus: status,
    }));
  },

  setStatusMessage(message: string): void {
    chatStore.update((state) => ({
      ...state,
      streaming: {
        ...state.streaming,
        statusMessage: message,
      },
    }));
  },

  setCurrentSources(sources: Source[]): void {
    chatStore.update((state) => ({
      ...state,
      streaming: {
        ...state.streaming,
        sources,
      },
    }));
  },

  appendStreamingContent(content: string): void {
    chatStore.update((state) => ({
      ...state,
      streaming: {
        ...state.streaming,
        isStreaming: true,
        currentContent: state.streaming.currentContent + content,
      },
    }));
  },

  finalizeStreamingMessage(metadata: { response_time_ms?: number; sources?: Source[] }): void {
    const currentState = get(chatStore);
    
    if (currentState.streaming.currentContent && currentState.currentSession) {
      const assistantMessage: ChatMessage = {
        id: `msg-${Date.now()}`,
        session_id: currentState.currentSession.id,
        role: "assistant",
        content: currentState.streaming.currentContent,
        created_at: new Date().toISOString(),
        response_time_ms: metadata.response_time_ms,
        sources: metadata.sources || currentState.streaming.sources,
      };

      chatStore.update((state) => ({
        ...state,
        messages: [...state.messages, assistantMessage],
        streaming: {
          isStreaming: false,
          currentContent: "",
          statusMessage: "",
          sources: [],
        },
        isLoading: false,
      }));
    }
  },

  addErrorMessage(error: string): void {
    const currentState = get(chatStore);
    
    if (currentState.currentSession) {
      const errorMessage: ChatMessage = {
        id: `error-${Date.now()}`,
        session_id: currentState.currentSession.id,
        role: "assistant",
        content: `❌ Error: ${error}`,
        created_at: new Date().toISOString(),
      };

      chatStore.update((state) => ({
        ...state,
        messages: [...state.messages, errorMessage],
        streaming: {
          isStreaming: false,
          currentContent: "",
          statusMessage: "",
          sources: [],
        },
        isLoading: false,
        lastError: error,
      }));
    }
  },

  // Utility methods
  clearError(): void {
    chatStore.update((state) => ({
      ...state,
      lastError: null,
    }));
  },

  reset(): void {
    chatStore.set(initialState);
  },

  // Initialize or resume session
  async initializeSession(sessionId?: string): Promise<void> {
    // Initialize chat store
    await this.initialize();
    
    if (sessionId) {
      // Load specific session
      await this.loadSession(sessionId);
      // Remember this session
      this.rememberLastSession(sessionId);
    } else {
      // Try to resume last used session from localStorage
      const lastSessionId = this.getLastSessionId();
      let sessionToLoad: string | null = null;
      
      if (lastSessionId) {
        const currentState = get(chatStore);
        // Check if the remembered session still exists
        const rememberedSession = currentState.sessions.find(s => s.id === lastSessionId);
        if (rememberedSession) {
          sessionToLoad = lastSessionId;
        }
      }
      
      if (!sessionToLoad) {
        // Check if there are existing sessions and use the most recent one
        const currentState = get(chatStore);
        if (currentState.sessions && currentState.sessions.length > 0) {
          // Use the most recent session (first in the list since they're sorted by updated_at desc)
          const mostRecentSession = currentState.sessions[0];
          sessionToLoad = mostRecentSession.id;
        }
      }
      
      if (sessionToLoad) {
        await this.loadSession(sessionToLoad);
        this.rememberLastSession(sessionToLoad);
      } else {
        // No existing sessions, create a new one
        const newSession = await this.createNewSession();
        this.rememberLastSession(newSession.id);
      }
    }
  },

  // Session persistence helpers
  rememberLastSession(sessionId: string): void {
    try {
      localStorage.setItem('chat_last_session_id', sessionId);
    } catch (error) {
      console.warn('Could not save session to localStorage:', error);
    }
  },

  getLastSessionId(): string | null {
    try {
      return localStorage.getItem('chat_last_session_id');
    } catch (error) {
      console.warn('Could not read session from localStorage:', error);
      return null;
    }
  },

  getErrorMessage(error: unknown): string {
    if (typeof error === "string") return error;
    
    const axiosError = error as AxiosError;
    if (axiosError.response?.data) {
      const data = axiosError.response.data as any;
      return data.detail || data.message || "Unknown error occurred";
    }
    
    if (axiosError.message) return axiosError.message;
    
    return "An unexpected error occurred";
  },
};

// Export the main store and actions
export { chatStore };
export default chatStore;