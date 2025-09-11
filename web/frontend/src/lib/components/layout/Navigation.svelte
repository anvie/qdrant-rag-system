<script lang="ts">
  import { createEventDispatcher } from "svelte";
  import Button from "../common/Button.svelte";
  import Icon from "@iconify/svelte";

  export let collapsed: boolean = false;
  export let currentPage: string = "dashboard";

  const dispatch = createEventDispatcher<{
    navigate: { page: string };
    toggleSidebar: void;
  }>();

  // Navigation items
  const navItems = [
    {
      id: "dashboard",
      label: "Dashboard",
      icon: "material-symbols:dashboard",
      description: "System overview",
    },
    {
      id: "collections",
      label: "Collections",
      icon: "material-symbols:view-list",
      description: "Manage collections",
    },
    {
      id: "search",
      label: "Search",
      icon: "material-symbols:search",
      description: "Search vectors",
    },
    {
      id: "chat",
      label: "Chat",
      icon: "material-symbols:chat",
      description: "RAG Chat interface",
      disabled: true,
    },
  ];

  const settingsItems = [
    {
      id: "settings",
      label: "Settings",
      icon: "material-symbols:settings",
      description: "App settings",
      disabled: true,
    },
  ];

  // Handle navigation
  const navigate = (page: string) => {
    dispatch("navigate", { page });
  };

  // Handle sidebar toggle
  const toggleSidebar = () => {
    dispatch("toggleSidebar");
  };

  // Get nav item classes
  const getNavItemClasses = (itemId: string, disabled: boolean = false) => {
    const baseClasses =
      "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors duration-200";

    if (disabled) {
      return `${baseClasses} text-gray-400 cursor-not-allowed`;
    }

    if (currentPage === itemId) {
      return `${baseClasses} bg-blue-100 text-blue-700 border border-blue-200`;
    }

    return `${baseClasses} text-gray-700 hover:bg-gray-100 hover:text-gray-900`;
  };
</script>

<nav class="h-full flex flex-col">
  <!-- Header -->
  <div class="flex items-center justify-between p-4 border-b border-gray-200">
    {#if !collapsed}
      <div class="flex items-center gap-2">
        <div
          class="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center"
        >
          <Icon icon="material-symbols:database" class="w-5 h-5 text-white" />
        </div>
        <span class="text-lg font-semibold text-gray-900">Qdrant RAG</span>
      </div>
    {:else}
      <div
        class="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center mx-auto"
      >
        <Icon icon="line-md:database" class="w-5 h-5 text-white" />
      </div>
    {/if}

    <!-- Collapse toggle (desktop only) -->
    <Button
      variant="ghost"
      size="sm"
      onClick={toggleSidebar}
      ariaLabel={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      class="hidden md:flex"
    >
      <Icon
        icon={collapsed
          ? "material-symbols:chevron-right"
          : "material-symbols:chevron-left"}
        class="w-4 h-4"
      />
    </Button>
  </div>

  <!-- Main Navigation -->
  <div class="flex-1 p-2 space-y-6">
    <!-- Primary Navigation -->
    <div>
      {#if !collapsed}
        <h3
          class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3"
        >
          Main
        </h3>
      {/if}

      <ul class="space-y-1">
        {#each navItems as item}
          <li>
            <button
              class={getNavItemClasses(item.id, item.disabled)}
              disabled={item.disabled}
              on:click={() => !item.disabled && navigate(item.id)}
              title={collapsed ? item.label : ""}
            >
              <div class="flex-shrink-0">
                <Icon icon={item.icon} class="w-5 h-5" />
              </div>

              {#if !collapsed}
                <span class="flex-1 text-left">{item.label}</span>

                {#if item.disabled}
                  <span
                    class="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full"
                  >
                    Soon
                  </span>
                {/if}
              {/if}
            </button>

            {#if !collapsed && item.description}
              <p class="text-xs text-gray-500 ml-8 mt-1">
                {item.description}
              </p>
            {/if}
          </li>
        {/each}
      </ul>
    </div>

    <!-- Secondary Navigation -->
    <div>
      {#if !collapsed}
        <h3
          class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3"
        >
          System
        </h3>
      {/if}

      <ul class="space-y-1">
        {#each settingsItems as item}
          <li>
            <button
              class={getNavItemClasses(item.id, item.disabled)}
              disabled={item.disabled}
              on:click={() => !item.disabled && navigate(item.id)}
              title={collapsed ? item.label : ""}
            >
              <div class="flex-shrink-0">
                <Icon icon={item.icon} class="w-5 h-5" />
              </div>

              {#if !collapsed}
                <span class="flex-1 text-left">{item.label}</span>

                {#if item.disabled}
                  <span
                    class="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full"
                  >
                    Soon
                  </span>
                {/if}
              {/if}
            </button>

            {#if !collapsed && item.description}
              <p class="text-xs text-gray-500 ml-8 mt-1">
                {item.description}
              </p>
            {/if}
          </li>
        {/each}
      </ul>
    </div>
  </div>

  <!-- Footer -->
  <div class="p-4 border-t border-gray-200">
    {#if !collapsed}
      <div class="text-xs text-gray-500 text-center">
        <p>Qdrant RAG System</p>
        <p class="mt-1">v1.0.0</p>
      </div>
    {:else}
      <div class="flex justify-center">
        <div
          class="w-2 h-2 bg-green-500 rounded-full"
          title="System Online"
        ></div>
      </div>
    {/if}
  </div>
</nav>

