<script lang="ts">
  import { createEventDispatcher, onMount } from "svelte";
  import { chatStore, chatActions } from "../../stores/chat";
  import { notificationActions } from "../../stores/notifications";
  import Icon from "@iconify/svelte";
  
  import Button from "../common/Button.svelte";
  import LoadingSpinner from "../common/LoadingSpinner.svelte";
  
  const dispatch = createEventDispatcher();
  
  // Props
  export let collapsed = false;
  
  // Local state
  let showDeleteConfirm: string | null = null;
  let isLoadingSessions = false;
  
  // Reactive statements
  $: currentSession = $chatStore.currentSession;
  $: sessions = $chatStore.sessions;
  
  onMount(async () => {
    await loadSessions();
  });
  
  async function loadSessions() {
    try {
      isLoadingSessions = true;
      await chatActions.loadSessions();
    } catch (error) {
      console.error("Failed to load sessions:", error);
      notificationActions.error("Load Failed", "Could not load conversation history");
    } finally {
      isLoadingSessions = false;
    }
  }
  
  async function selectSession(sessionId: string) {
    if (currentSession?.id === sessionId) return;
    
    try {
      await chatActions.loadSession(sessionId);
      // Emit event to parent to update WebSocket connection
      dispatch('sessionChanged', { sessionId });
    } catch (error) {
      console.error("Failed to load session:", error);
      notificationActions.error("Load Failed", "Could not load conversation");
    }
  }
  
  function handleNewSession() {
    dispatch('newSession');
  }
  
  function toggleSidebar() {
    dispatch('toggleSidebar');
  }
  
  async function deleteSession(sessionId: string) {
    if (showDeleteConfirm === sessionId) {
      try {
        await chatActions.deleteSession(sessionId);
        showDeleteConfirm = null;
        
        // If deleted session was current, create new session
        if (currentSession?.id === sessionId) {
          handleNewSession();
        }
        
        notificationActions.success("Deleted", "Conversation deleted");
      } catch (error) {
        console.error("Failed to delete session:", error);
        notificationActions.error("Delete Failed", "Could not delete conversation");
      }
    } else {
      showDeleteConfirm = sessionId;
      // Auto-cancel confirmation after 3 seconds
      setTimeout(() => {
        if (showDeleteConfirm === sessionId) {
          showDeleteConfirm = null;
        }
      }, 3000);
    }
  }
  
  function cancelDelete() {
    showDeleteConfirm = null;
  }
  
  function formatSessionTime(timestamp: string): string {
    try {
      const date = new Date(timestamp);
      const now = new Date();
      const diffMs = now.getTime() - date.getTime();
      const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
      const diffDays = Math.floor(diffHours / 24);
      
      if (diffHours < 1) return "Just now";
      if (diffHours < 24) return `${diffHours}h ago`;
      if (diffDays < 7) return `${diffDays}d ago`;
      
      return date.toLocaleDateString();
    } catch {
      return "";
    }
  }
  
  function truncateTitle(title: string, maxLength = 25): string {
    if (title.length <= maxLength) return title;
    return title.substring(0, maxLength) + "...";
  }
</script>

<div class="h-full flex flex-col bg-white">
  <!-- Sidebar Header -->
  <div class="p-3 border-b border-gray-200">
    <div class="flex items-center justify-between">
      {#if !collapsed}
        <h3 class="font-semibold text-gray-900">Conversations</h3>
      {/if}
      
      <div class="flex items-center gap-1">
        <Button
          variant="ghost"
          size="sm"
          onClick={handleNewSession}
          ariaLabel="New conversation"
          class="!p-2"
        >
          <Icon icon="material-symbols:add" class="w-4 h-4" />
        </Button>
        
        <Button
          variant="ghost"
          size="sm"
          onClick={toggleSidebar}
          ariaLabel={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          class="!p-2"
        >
          <Icon 
            icon={collapsed ? "material-symbols:chevron-right" : "material-symbols:chevron-left"} 
            class="w-4 h-4" 
          />
        </Button>
      </div>
    </div>
  </div>
  
  <!-- Sessions List -->
  <div class="flex-1 overflow-y-auto">
    {#if isLoadingSessions}
      <div class="flex justify-center py-8">
        <LoadingSpinner size="sm" />
      </div>
    {:else if sessions.length === 0}
      <div class="p-4 text-center text-gray-500">
        {#if collapsed}
          <Icon icon="material-symbols:chat-bubble-outline" class="w-6 h-6 mx-auto mb-2" />
        {:else}
          <Icon icon="material-symbols:chat-bubble-outline" class="w-12 h-12 mx-auto mb-4" />
          <p class="text-sm">No conversations yet</p>
          <p class="text-xs mt-1">Start a new chat to see it here</p>
        {/if}
      </div>
    {:else}
      <div class="p-2">
        {#each sessions as session (session.id)}
          <div class="relative group mb-1">
            <!-- Session Item -->
            <button
              class="
                w-full text-left p-2 rounded-lg transition-colors
                hover:bg-gray-50 
                {currentSession?.id === session.id ? 'bg-blue-50 border-blue-200' : 'border-transparent'}
                {collapsed ? 'px-2' : 'px-3'}
              "
              on:click={() => selectSession(session.id)}
            >
              {#if collapsed}
                <div class="flex justify-center">
                  <Icon icon="material-symbols:chat" class="w-5 h-5 text-gray-600" />
                </div>
              {:else}
                <div class="flex items-start justify-between">
                  <div class="flex-1 min-w-0">
                    <h4 class="text-sm font-medium text-gray-900 truncate">
                      {truncateTitle(session.title)}
                    </h4>
                    <div class="flex items-center gap-2 mt-1 text-xs text-gray-500">
                      <span>{formatSessionTime(session.updated_at)}</span>
                      {#if session.message_count > 0}
                        <span>•</span>
                        <span>{session.message_count} messages</span>
                      {/if}
                    </div>
                  </div>
                  
                  <!-- Delete Button -->
                  <div class="flex-shrink-0 ml-2">
                    {#if showDeleteConfirm === session.id}
                      <div class="flex items-center gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => deleteSession(session.id)}
                          class="!p-1 text-red-600 hover:text-red-700"
                          ariaLabel="Confirm delete"
                        >
                          <Icon icon="material-symbols:check" class="w-3 h-3" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={cancelDelete}
                          class="!p-1 text-gray-600"
                          ariaLabel="Cancel delete"
                        >
                          <Icon icon="material-symbols:close" class="w-3 h-3" />
                        </Button>
                      </div>
                    {:else}
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => deleteSession(session.id)}
                        class="!p-1 opacity-0 hover:opacity-100 transition-opacity text-red-600 hover:text-red-700"
                        ariaLabel="Delete conversation"
                      >
                        <Icon icon="material-symbols:delete-outline" class="w-3 h-3" />
                      </Button>
                    {/if}
                  </div>
                </div>
              {/if}
            </button>
          </div>
        {/each}
      </div>
    {/if}
  </div>
  
  <!-- Sidebar Footer -->
  {#if !collapsed}
    <div class="p-3 border-t border-gray-200 bg-gray-50">
      <div class="text-xs text-gray-600 space-y-1">
        <div class="flex items-center justify-between">
          <span>Current session:</span>
          <span class="font-mono text-gray-500">
            {currentSession?.id ? currentSession.id.substring(0, 8) + "..." : "None"}
          </span>
        </div>
        <div class="flex items-center justify-between">
          <span>Model:</span>
          <span class="font-medium">
            {currentSession?.llm_model || "llama2"}
          </span>
        </div>
        <div class="flex items-center justify-between">
          <span>Collection:</span>
          <span class="font-medium">
            {currentSession?.collection_name || "articles"}
          </span>
        </div>
      </div>
    </div>
  {/if}
</div>

<style>
  /* Custom scrollbar for sessions list */
  .overflow-y-auto {
    scrollbar-width: thin;
    scrollbar-color: #cbd5e0 transparent;
  }
  
  .overflow-y-auto::-webkit-scrollbar {
    width: 4px;
  }
  
  .overflow-y-auto::-webkit-scrollbar-track {
    background: transparent;
  }
  
  .overflow-y-auto::-webkit-scrollbar-thumb {
    background-color: #cbd5e0;
    border-radius: 2px;
  }
  
  .overflow-y-auto::-webkit-scrollbar-thumb:hover {
    background-color: #a0aec0;
  }
</style>