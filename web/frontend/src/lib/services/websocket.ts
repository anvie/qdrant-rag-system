/**
 * WebSocket service for real-time communication
 */

export interface WebSocketMessage {
  type: string;
  data: any;
  timestamp: number;
}

export type MessageHandler = (message: WebSocketMessage) => void;

class WebSocketService {
  private connections: Map<string, WebSocket> = new Map();
  private handlers: Map<string, MessageHandler[]> = new Map();
  private reconnectAttempts: Map<string, number> = new Map();
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;

  /**
   * Connect to a WebSocket endpoint
   */
  connect(endpoint: string, onMessage?: MessageHandler): Promise<WebSocket> {
    return new Promise((resolve, reject) => {
      try {
        // Close existing connection if any
        this.disconnect(endpoint);

        const wsUrl = `ws://localhost:8000/ws${endpoint}`;
        const ws = new WebSocket(wsUrl);

        ws.onopen = () => {
          // console.log(`WebSocket connected: ${endpoint}`);
          this.connections.set(endpoint, ws);
          this.reconnectAttempts.set(endpoint, 0);

          if (onMessage) {
            this.addHandler(endpoint, onMessage);
          }

          resolve(ws);
        };

        ws.onmessage = (event) => {
          try {
            const message: WebSocketMessage = JSON.parse(event.data);
            this.handleMessage(endpoint, message);
          } catch (error) {
            console.error("Failed to parse WebSocket message:", error);
          }
        };

        ws.onclose = (event) => {
          // console.log(
          //   `WebSocket closed: ${endpoint}`,
          //   event.code,
          //   event.reason,
          // );
          this.connections.delete(endpoint);

          // Attempt reconnection if not manual close
          if (event.code !== 1000) {
            this.attemptReconnect(endpoint, onMessage);
          }
        };

        ws.onerror = (error) => {
          console.error(`WebSocket error: ${endpoint}`, error);
          reject(error);
        };
      } catch (error) {
        reject(error);
      }
    });
  }

  /**
   * Disconnect from WebSocket endpoint
   */
  disconnect(endpoint: string): void {
    const ws = this.connections.get(endpoint);
    if (ws) {
      ws.close(1000, "Manual disconnect");
      this.connections.delete(endpoint);
      this.handlers.delete(endpoint);
      this.reconnectAttempts.delete(endpoint);
    }
  }

  /**
   * Send message to WebSocket endpoint
   */
  send(endpoint: string, message: any): void {
    const ws = this.connections.get(endpoint);
    console.log("[WebSocketService] send called - endpoint:", endpoint, "connected:", ws?.readyState === WebSocket.OPEN);
    
    if (ws && ws.readyState === WebSocket.OPEN) {
      // If message already has type and data structure, use it directly
      const payload = JSON.stringify(
        message.type && message.data 
          ? message 
          : {
              type: "message",
              data: message,
              timestamp: Date.now(),
            }
      );
      console.log("[WebSocketService] Sending payload:", payload);
      ws.send(payload);
    } else {
      console.warn(`[WebSocketService] WebSocket not connected: ${endpoint}`);
    }
  }

  /**
   * Add message handler for endpoint
   */
  addHandler(endpoint: string, handler: MessageHandler): void {
    if (!this.handlers.has(endpoint)) {
      this.handlers.set(endpoint, []);
    }
    this.handlers.get(endpoint)!.push(handler);
  }

  /**
   * Remove message handler
   */
  removeHandler(endpoint: string, handler: MessageHandler): void {
    const handlers = this.handlers.get(endpoint);
    if (handlers) {
      const index = handlers.indexOf(handler);
      if (index > -1) {
        handlers.splice(index, 1);
      }
    }
  }

  /**
   * Get connection status
   */
  isConnected(endpoint: string): boolean {
    const ws = this.connections.get(endpoint);
    return ws?.readyState === WebSocket.OPEN;
  }

  /**
   * Get all active connections
   */
  getActiveConnections(): string[] {
    return Array.from(this.connections.keys()).filter((endpoint) =>
      this.isConnected(endpoint),
    );
  }

  /**
   * Handle incoming messages
   */
  private handleMessage(endpoint: string, message: WebSocketMessage): void {
    const handlers = this.handlers.get(endpoint);
    if (handlers) {
      handlers.forEach((handler) => {
        try {
          handler(message);
        } catch (error) {
          console.error("Error in WebSocket message handler:", error);
        }
      });
    }
  }

  /**
   * Attempt to reconnect to WebSocket
   */
  private attemptReconnect(endpoint: string, onMessage?: MessageHandler): void {
    const attempts = this.reconnectAttempts.get(endpoint) || 0;

    if (attempts < this.maxReconnectAttempts) {
      console.log(
        `Attempting to reconnect (${attempts + 1}/${this.maxReconnectAttempts}): ${endpoint}`,
      );

      setTimeout(
        () => {
          this.reconnectAttempts.set(endpoint, attempts + 1);
          this.connect(endpoint, onMessage).catch((error) => {
            console.error("Reconnection failed:", error);
          });
        },
        this.reconnectDelay * Math.pow(2, attempts),
      ); // Exponential backoff
    } else {
      console.error(`Max reconnection attempts reached for: ${endpoint}`);
      this.reconnectAttempts.delete(endpoint);
    }
  }

  /**
   * Disconnect all connections
   */
  disconnectAll(): void {
    for (const endpoint of this.connections.keys()) {
      this.disconnect(endpoint);
    }
  }
}

// Specialized WebSocket connections
export class IndexingWebSocket {
  private ws: WebSocketService;
  private endpoint: string;

  constructor(jobId: string) {
    this.ws = new WebSocketService();
    this.endpoint = `/indexing/${jobId}`;
  }

  connect(onProgress: (progress: any) => void): Promise<WebSocket> {
    return this.ws.connect(this.endpoint, (message) => {
      if (message.type === "progress") {
        onProgress(message.data);
      }
    });
  }

  disconnect(): void {
    this.ws.disconnect(this.endpoint);
  }
}

export class ChatWebSocket {
  private ws: WebSocketService;
  private endpoint: string;
  private sessionId: string;
  private pingInterval: number | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;

  constructor(sessionId: string) {
    this.ws = new WebSocketService();
    this.sessionId = sessionId;
    this.endpoint = `/chat/${sessionId}`;
  }

  connect(onMessage: (message: any) => void): Promise<WebSocket> {
    return this.ws.connect(this.endpoint, (wsMessage) => {
      // Handle different message types
      switch (wsMessage.type) {
        case "connected":
          this.reconnectAttempts = 0;
          this.startPing();
          onMessage(wsMessage);
          break;
          
        case "status":
        case "context":
        case "content":
        case "complete":
        case "error":
          onMessage(wsMessage);
          break;
          
        case "pong":
          // Handle ping response (keep connection alive)
          break;
          
        default:
          // Forward unknown message types
          onMessage(wsMessage);
      }
    }).catch((error) => {
      console.error("ChatWebSocket connection failed:", error);
      this.attemptReconnect(onMessage);
      throw error;
    });
  }

  sendMessage(message: string): void {
    console.log("[ChatWebSocket] sendMessage called with:", message);
    console.log("[ChatWebSocket] Endpoint:", this.endpoint);
    console.log("[ChatWebSocket] Connection status:", this.ws.isConnected(this.endpoint));
    
    try {
      const messagePayload = {
        type: "message",
        data: {
          message: message,
          timestamp: Date.now()
        }
      };
      console.log("[ChatWebSocket] Sending payload:", messagePayload);
      
      this.ws.send(this.endpoint, messagePayload);
      console.log("[ChatWebSocket] Message sent successfully");
    } catch (error) {
      console.error("[ChatWebSocket] Failed to send chat message:", error);
      throw error;
    }
  }

  sendTypingIndicator(isTyping: boolean): void {
    try {
      this.ws.send(this.endpoint, {
        type: "typing",
        data: {
          status: isTyping,
          timestamp: Date.now()
        }
      });
    } catch (error) {
      console.error("Failed to send typing indicator:", error);
    }
  }

  ping(): void {
    try {
      this.ws.send(this.endpoint, {
        type: "ping",
        data: {
          timestamp: Date.now()
        }
      });
    } catch (error) {
      console.error("Failed to send ping:", error);
    }
  }

  disconnect(): void {
    this.stopPing();
    this.ws.disconnect(this.endpoint);
  }

  isConnected(): boolean {
    return this.ws.isConnected(this.endpoint);
  }

  private startPing(): void {
    this.stopPing(); // Clear any existing ping
    
    this.pingInterval = window.setInterval(() => {
      if (this.isConnected()) {
        this.ping();
      } else {
        this.stopPing();
      }
    }, 30000); // Ping every 30 seconds
  }

  private stopPing(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  private async attemptReconnect(onMessage: (message: any) => void): Promise<void> {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error("Max reconnection attempts reached");
      return;
    }

    this.reconnectAttempts++;
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
    
    console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts}) in ${delay}ms...`);
    
    setTimeout(async () => {
      try {
        await this.connect(onMessage);
        console.log("Reconnected successfully");
      } catch (error) {
        console.error("Reconnection failed:", error);
        this.attemptReconnect(onMessage);
      }
    }, delay);
  }
}

// Export singleton instance
export const websocketService = new WebSocketService();
export default websocketService;
