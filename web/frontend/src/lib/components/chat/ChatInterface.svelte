<script lang="ts">
  import { onMount, onDestroy, afterUpdate } from "svelte";
  import { websocketService, ChatWebSocket } from "../../services/websocket";
  import { chatStore, chatActions } from "../../stores/chat";
  import { notificationActions } from "../../stores/notifications";
  
  import ChatMessage from "./ChatMessage.svelte";
  import ChatInput from "./ChatInput.svelte";
  import ChatSidebar from "./ChatSidebar.svelte";
  import ChatSettings from "./ChatSettings.svelte";
  import TypingIndicator from "./TypingIndicator.svelte";
  import Card from "../common/Card.svelte";
  import LoadingSpinner from "../common/LoadingSpinner.svelte";
  import Button from "../common/Button.svelte";
  import Icon from "@iconify/svelte";

  // Props
  export let sessionId: string | null = null;
  export let showSidebar: boolean = true;
  export let autoFocus: boolean = true;

  // Local state
  let messagesContainer: HTMLElement;
  let chatWebSocket: ChatWebSocket | null = null;
  let isConnected = false;
  let isTyping = false;
  let sidebarCollapsed = false;
  let showSettingsModal = false;

  // Reactive statements
  $: currentSession = $chatStore.currentSession;
  $: messages = $chatStore.messages;
  $: isLoading = $chatStore.isLoading;
  $: connectionStatus = $chatStore.connectionStatus;

  onMount(async () => {
    // Initialize or resume session
    await chatActions.initializeSession(sessionId);
    
    // Setup WebSocket connection
    if (currentSession) {
      connectWebSocket(currentSession.id);
    }
  });

  onDestroy(() => {
    if (chatWebSocket) {
      chatWebSocket.disconnect();
    }
  });

  afterUpdate(() => {
    // Auto-scroll to bottom when new messages arrive
    if (messagesContainer && messages.length > 0) {
      scrollToBottom();
    }
  });

  function connectWebSocket(sessionId: string) {
    try {
      chatWebSocket = new ChatWebSocket(sessionId);
      
      chatWebSocket.connect((message) => {
        handleWebSocketMessage(message);
      }).then(() => {
        isConnected = true;
        chatActions.setConnectionStatus("connected");
      }).catch((error) => {
        console.error("WebSocket connection failed:", error);
        isConnected = false;
        chatActions.setConnectionStatus("disconnected");
        notificationActions.error("Connection Failed", "Could not connect to chat service");
      });
    } catch (error) {
      console.error("Failed to setup WebSocket:", error);
      notificationActions.error("WebSocket Error", "Failed to setup real-time connection");
    }
  }

  function handleWebSocketMessage(message: any) {
    console.log("[ChatInterface] WebSocket message received:", message);
    
    switch (message.type) {
      case "connected":
        console.log("Chat WebSocket connected");
        break;
        
      case "status":
        // Update status (searching, generating, etc.)
        console.log("[ChatInterface] Status update:", message.data);
        chatActions.setStatusMessage(message.data);
        break;
        
      case "context":
        // Handle context information
        console.log("[ChatInterface] Context received, sources count:", message.data.sources?.length || 0);
        if (message.data.sources) {
          chatActions.setCurrentSources(message.data.sources);
        }
        break;
        
      case "content":
        // Handle streaming content
        console.log("[ChatInterface] Streaming content chunk:", message.data);
        chatActions.appendStreamingContent(message.data);
        isTyping = true;
        break;
        
      case "complete":
        // Handle completion
        console.log("[ChatInterface] Response complete:", message.data);
        isTyping = false;
        chatActions.finalizeStreamingMessage(message.data);
        break;
        
      case "error":
        isTyping = false;
        console.error("[ChatInterface] Chat error:", message.data.error);
        chatActions.addErrorMessage(message.data.error);
        notificationActions.error("Chat Error", message.data.error);
        break;
        
      case "pong":
        // Handle ping response
        console.log("[ChatInterface] Pong received");
        break;
        
      default:
        console.warn("[ChatInterface] Unknown WebSocket message type:", message.type);
    }
  }

  function scrollToBottom(smooth = true) {
    if (messagesContainer) {
      messagesContainer.scrollTo({
        top: messagesContainer.scrollHeight,
        behavior: smooth ? "smooth" : "instant"
      });
    }
  }

  async function handleSendMessage(message: string) {
    console.log("[ChatInterface] handleSendMessage called with:", message);
    console.log("[ChatInterface] Current state - session:", currentSession?.id, "connected:", isConnected, "loading:", isLoading);
    
    if (!currentSession || !isConnected || isLoading) {
      console.warn("[ChatInterface] Cannot send message - missing requirements");
      return;
    }
    
    try {
      // Add user message to store
      console.log("[ChatInterface] Adding user message to store");
      await chatActions.addUserMessage(message);
      
      // Send via WebSocket for streaming response
      if (chatWebSocket) {
        console.log("[ChatInterface] Sending message via WebSocket");
        chatWebSocket.sendMessage(message);
      } else {
        console.error("[ChatInterface] No WebSocket connection available!");
      }
      
      // Scroll to bottom
      setTimeout(() => scrollToBottom(), 100);
      
    } catch (error) {
      console.error("[ChatInterface] Failed to send message:", error);
      notificationActions.error("Send Failed", "Could not send message");
    }
  }

  function handleNewSession() {
    chatActions.createNewSession().then(() => {
      if (chatWebSocket) {
        chatWebSocket.disconnect();
      }
      if (currentSession) {
        connectWebSocket(currentSession.id);
      }
    });
  }

  function toggleSidebar() {
    sidebarCollapsed = !sidebarCollapsed;
  }
  
  function openSettings() {
    showSettingsModal = true;
  }
  
  function closeSettings() {
    showSettingsModal = false;
  }
</script>

<div class="flex h-full bg-gray-50">
  <!-- Chat Sidebar -->
  {#if showSidebar}
    <div 
      class="
        {sidebarCollapsed ? 'w-12' : 'w-80'} 
        transition-all duration-300 ease-in-out
        bg-white border-r border-gray-200 flex-shrink-0
      "
    >
      <ChatSidebar 
        collapsed={sidebarCollapsed}
        on:toggleSidebar={toggleSidebar}
        on:newSession={handleNewSession}
      />
    </div>
  {/if}

  <!-- Main Chat Area -->
  <div class="flex-1 flex flex-col min-w-0">
    <!-- Chat Header -->
    <header class="bg-white border-b border-gray-200 px-4 py-3">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-3">
          {#if showSidebar && sidebarCollapsed}
            <Button
              variant="ghost" 
              size="sm" 
              onClick={toggleSidebar}
              ariaLabel="Expand sidebar"
            >
              <Icon icon="material-symbols:menu" class="w-5 h-5" />
            </Button>
          {/if}
          
          <div>
            <h2 class="font-semibold text-gray-900">
              {currentSession?.title || "New Conversation"}
            </h2>
            <div class="flex items-center gap-2 text-sm text-gray-500">
              <div 
                class="w-2 h-2 rounded-full {isConnected ? 'bg-green-500' : 'bg-red-500'}"
              ></div>
              <span>{connectionStatus}</span>
              {#if currentSession?.llm_model}
                <span>•</span>
                <span>{currentSession.llm_model}</span>
              {/if}
            </div>
          </div>
        </div>
        
        <div class="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleNewSession}
            ariaLabel="New conversation"
          >
            <Icon icon="material-symbols:add" class="w-5 h-5" />
          </Button>
          
          <Button
            variant="ghost"
            size="sm"
            onClick={openSettings}
            ariaLabel="Chat settings"
            disabled={!currentSession}
          >
            <Icon icon="material-symbols:settings" class="w-5 h-5" />
          </Button>
        </div>
      </div>
    </header>

    <!-- Messages Area -->
    <div 
      class="flex-1 overflow-y-auto p-4 space-y-4" 
      bind:this={messagesContainer}
    >
      {#if messages.length === 0}
        <!-- Welcome Message -->
        <div class="flex items-center justify-center h-full">
          <Card>
            <div class="py-8 max-w-md text-center">
              <div class="text-blue-500 mb-4">
                <Icon icon="material-symbols:chat" class="w-16 h-16 mx-auto" />
              </div>
              <h3 class="text-xl font-semibold text-gray-900 mb-2">
                Start a conversation
              </h3>
              <p class="text-gray-600 mb-6">
                Ask me anything about your documents. I'll search through your 
                vector database and provide relevant answers.
              </p>
              <div class="text-sm text-gray-500">
                <div class="flex items-center justify-center gap-2 mb-1">
                  <Icon icon="material-symbols:database" class="w-4 h-4" />
                  <span>Collection: {currentSession?.collection_name || "articles"}</span>
                </div>
                <div class="flex items-center justify-center gap-2">
                  <Icon icon="material-symbols:smart_toy" class="w-4 h-4" />
                  <span>Model: {currentSession?.llm_model || "llama2"}</span>
                </div>
              </div>
            </div>
          </Card>
        </div>
      {:else}
        <!-- Message List -->
        {#each messages as message (message.id)}
          <ChatMessage {message} />
        {/each}
        
        <!-- Typing Indicator -->
        {#if isTyping}
          <TypingIndicator />
        {/if}
        
        <!-- Loading State -->
        {#if isLoading}
          <div class="flex justify-center py-4">
            <LoadingSpinner size="sm" />
          </div>
        {/if}
      {/if}
    </div>

    <!-- Chat Input -->
    <div class="border-t border-gray-200 bg-white p-4">
      <ChatInput 
        {autoFocus}
        disabled={!isConnected || isLoading}
        placeholder={isConnected ? "Type your message..." : "Connecting..."}
        on:send={(e) => handleSendMessage(e.detail.message)}
      />
    </div>
  </div>
</div>

<!-- Settings Modal -->
{#if showSettingsModal && currentSession}
  <div 
    class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4"
    style="z-index: 9999;"
    tabindex="0"
    on:click={(e) => {
      if (e.target === e.currentTarget) {
        closeSettings();
      }
    }}
    on:keydown={(e) => {
      if (e.key === 'Escape') {
        closeSettings();
      }
    }}
    role="dialog"
    aria-modal="true"
    aria-labelledby="settings-title"
  >
    <ChatSettings 
      session={currentSession} 
      onClose={closeSettings} 
    />
  </div>
{/if}

<style>
  /* Custom scrollbar for messages */
  .overflow-y-auto {
    scrollbar-width: thin;
    scrollbar-color: #cbd5e0 transparent;
  }
  
  .overflow-y-auto::-webkit-scrollbar {
    width: 6px;
  }
  
  .overflow-y-auto::-webkit-scrollbar-track {
    background: transparent;
  }
  
  .overflow-y-auto::-webkit-scrollbar-thumb {
    background-color: #cbd5e0;
    border-radius: 3px;
  }
  
  .overflow-y-auto::-webkit-scrollbar-thumb:hover {
    background-color: #a0aec0;
  }
</style>