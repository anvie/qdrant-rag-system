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
    if (ws && ws.readyState === WebSocket.OPEN) {
      const payload = JSON.stringify({
        type: "message",
        data: message,
        timestamp: Date.now(),
      });
      ws.send(payload);
    } else {
      console.warn(`WebSocket not connected: ${endpoint}`);
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

  constructor(sessionId: string) {
    this.ws = new WebSocketService();
    this.endpoint = `/chat/${sessionId}`;
  }

  connect(onMessage: (message: any) => void): Promise<WebSocket> {
    return this.ws.connect(this.endpoint, (wsMessage) => {
      if (wsMessage.type === "chat_response") {
        onMessage(wsMessage.data);
      }
    });
  }

  sendMessage(message: string): void {
    this.ws.send(this.endpoint, { message });
  }

  disconnect(): void {
    this.ws.disconnect(this.endpoint);
  }
}

// Export singleton instance
export const websocketService = new WebSocketService();
export default websocketService;
