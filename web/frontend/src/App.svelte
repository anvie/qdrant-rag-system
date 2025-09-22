<script lang="ts">
  import { onMount } from "svelte";

  // Layout components
  import Navigation from "./lib/components/layout/Navigation.svelte";
  import NotificationToast from "./lib/components/layout/NotificationToast.svelte";

  // Dashboard components
  import SystemStatus from "./lib/components/dashboard/SystemStatus.svelte";
  import CollectionsList from "./lib/components/dashboard/CollectionsList.svelte";
  import StatsCard from "./lib/components/dashboard/StatsCard.svelte";

  // Search components
  import SearchInterface from "./lib/components/search/SearchInterface.svelte";
  import SearchResults from "./lib/components/search/SearchResults.svelte";
  import ArticlePreview from "./lib/components/search/ArticlePreview.svelte";

  // Chat components
  import ChatInterface from "./lib/components/chat/ChatInterface.svelte";
  
  // Collection components
  import CollectionDetail from "./lib/components/collections/CollectionDetail.svelte";

  // Common components
  import Card from "./lib/components/common/Card.svelte";
  import Button from "./lib/components/common/Button.svelte";
  import LoadingSpinner from "./lib/components/common/LoadingSpinner.svelte";
  import Icon from "@iconify/svelte";

  // Stores
  import {
    collectionsActions,
    collectionsStats,
  } from "./lib/stores/collections";
  import { overallHealth, connectionStatus } from "./lib/stores/system";
  import { notificationActions } from "./lib/stores/notifications";

  // URL routing helpers (defined first)
  const getPageFromHash = (): { page: string; params?: any } => {
    if (typeof window === "undefined") return { page: "dashboard" };
    const hash = window.location.hash.slice(1); // Remove #
    
    // Check for collection detail page
    if (hash.startsWith("collection/")) {
      const collectionName = hash.slice(11); // Remove "collection/"
      return { page: "collection-detail", params: { collectionName } };
    }
    
    const validPages = [
      "dashboard",
      "collections",
      "search",
      "chat",
      "settings",
    ];
    return { page: validPages.includes(hash) ? hash : "dashboard" };
  };

  // App state - initialize currentPage from URL immediately
  const initialRoute = getPageFromHash();
  let currentPage: string = initialRoute.page;
  let currentParams: any = initialRoute.params || {};
  let sidebarCollapsed: boolean = false;
  let mobileMenuOpen: boolean = false;

  const updateHash = (page: string, params?: any) => {
    if (typeof window === "undefined") return;
    if (page === "dashboard") {
      // Remove hash for dashboard (default page)
      window.location.hash = "";
    } else if (page === "collection-detail" && params?.collectionName) {
      window.location.hash = `collection/${params.collectionName}`;
    } else {
      window.location.hash = page;
    }
  };

  // URL sync is handled by onMount and hashchange events

  // Responsive breakpoint handling
  let windowWidth: number = 0;
  $: isMobile = windowWidth < 768;
  $: isTablet = windowWidth >= 768 && windowWidth < 1024;

  // Auto-collapse sidebar on mobile
  $: if (isMobile) {
    sidebarCollapsed = true;
    mobileMenuOpen = false;
  }

  // Page navigation handler
  const handleNavigation = (event: CustomEvent<{ page: string; params?: any }>) => {
    const { page, params } = event.detail;
    currentPage = page;
    currentParams = params || {};
    updateHash(page, params);
    if (isMobile) {
      mobileMenuOpen = false;
    }
  };

  // Direct navigation helper
  const navigateToPage = (page: string, params?: any) => {
    currentPage = page;
    currentParams = params || {};
    updateHash(page, params);
    if (isMobile) {
      mobileMenuOpen = false;
    }
  };

  // Handle hash change events (back/forward navigation)
  const handleHashChange = () => {
    const route = getPageFromHash();
    if (route.page !== currentPage || JSON.stringify(route.params) !== JSON.stringify(currentParams)) {
      currentPage = route.page;
      currentParams = route.params || {};
    }
  };

  // Sidebar toggle handler
  const handleSidebarToggle = () => {
    if (isMobile) {
      mobileMenuOpen = !mobileMenuOpen;
    } else {
      sidebarCollapsed = !sidebarCollapsed;
    }
  };

  // Close mobile menu on backdrop click
  const closeMobileMenu = () => {
    if (isMobile) {
      mobileMenuOpen = false;
    }
  };

  // Page titles
  const pageTitles: Record<string, string> = {
    dashboard: "Dashboard",
    collections: "Collections",
    "collection-detail": "Collection Details",
    search: "Search",
    chat: "Chat",
    settings: "Settings",
  };
  
  // Get current page title
  $: pageTitle = currentPage === "collection-detail" && currentParams.collectionName
    ? `Collection: ${currentParams.collectionName}`
    : pageTitles[currentPage] || "Dashboard";

  // Initialize app
  onMount(async () => {
    await collectionsActions.initialize();
    await collectionsActions.loadAllCollectionStats();
  });
</script>

<svelte:window bind:innerWidth={windowWidth} on:hashchange={handleHashChange} />

<div class="min-h-screen bg-gray-50 flex">
  <!-- Mobile Menu Backdrop -->
  {#if mobileMenuOpen && isMobile}
    <div
      class="fixed inset-0 bg-black bg-opacity-50 z-40"
      role="button"
      on:click={closeMobileMenu}
      on:keydown={(e) => e.key === "Escape" && closeMobileMenu()}
      tabindex="0"
      aria-label="Close mobile menu"
    ></div>
  {/if}

  <!-- Sidebar -->
  <aside
    class="
      {isMobile ? 'fixed' : 'relative'} 
      {isMobile && !mobileMenuOpen ? '-translate-x-full' : 'translate-x-0'}
      {sidebarCollapsed && !isMobile ? 'w-16' : 'w-64'}
      h-screen bg-white border-r border-gray-200 transition-all duration-300 ease-in-out z-50
    "
  >
    <Navigation
      collapsed={sidebarCollapsed && !isMobile}
      {currentPage}
      on:navigate={handleNavigation}
      on:toggleSidebar={handleSidebarToggle}
    />
  </aside>

  <!-- Main Content Area -->
  <div class="flex-1 flex flex-col h-screen overflow-hidden">
    <!-- Top Header -->
    <header class="bg-white border-b border-gray-200 px-4 sm:px-6 py-4">
      <div class="flex items-center justify-between">
        <!-- Mobile Menu Button & Page Title -->
        <div class="flex items-center gap-4">
          {#if isMobile}
            <Button
              variant="ghost"
              size="sm"
              onClick={handleSidebarToggle}
              ariaLabel="Toggle menu"
            >
              <Icon icon="material-symbols:menu" class="w-5 h-5" />
            </Button>
          {/if}

          <div>
            <h1 class="text-xl font-semibold text-gray-900">
              {pageTitle}
            </h1>
            <p class="text-sm text-gray-600 mt-0.5">
              {#if currentPage === "dashboard"}
                System overview and real-time monitoring
              {:else if currentPage === "collections"}
                Manage your vector collections
              {:else if currentPage === "collection-detail"}
                View and manage collection records
              {:else if currentPage === "search"}
                Search through your vectors
              {:else if currentPage === "chat"}
                RAG-powered chat interface
              {:else}
                System configuration
              {/if}
            </p>
          </div>
        </div>

        <!-- System Status Indicator -->
        <div class="flex items-center gap-3">
          <!-- Connection Status -->
          <div
            class="flex items-center gap-2 px-3 py-1.5 rounded-full bg-gray-100"
          >
            <div
              class="w-2 h-2 rounded-full {$connectionStatus.api &&
              $connectionStatus.qdrant
                ? 'bg-green-500'
                : 'bg-red-500'}"
            ></div>
            <span class="text-xs font-medium text-gray-700">
              {$overallHealth === "healthy"
                ? "Online"
                : $overallHealth === "partial"
                  ? "Partial"
                  : "Offline"}
            </span>
          </div>

          <!-- Notifications Badge -->
          <Button
            variant="ghost"
            size="sm"
            ariaLabel="Notifications"
            class="relative"
          >
            <Icon icon="material-symbols:notifications" class="w-5 h-5" />
          </Button>
        </div>
      </div>
    </header>

    <!-- Page Content -->
    <main class="flex-1 overflow-auto p-4 sm:p-6" class:flex={currentPage === "chat"} class:flex-col={currentPage === "chat"} class:overflow-hidden={currentPage === "chat"}>
      {#if currentPage === "dashboard"}
        <!-- Dashboard Page -->
        <div class="space-y-6">
          <!-- Overview Stats -->
          <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
            <StatsCard
              title="Collections"
              value={$collectionsStats.total}
              subtitle="Total collections"
              icon="material-symbols:view-list"
              color="blue"
              clickable={true}
              onClick={() => navigateToPage("collections")}
            />

            <StatsCard
              title="Active"
              value={$collectionsStats.activeCollections}
              subtitle="Ready collections"
              icon="material-symbols:check-circle"
              color="green"
              trend="neutral"
            />

            <StatsCard
              title="Total Vectors"
              value={$collectionsStats.totalPoints}
              subtitle="Embeddings"
              icon="material-symbols:bar-chart"
              color="purple"
            />
          </div>

          <!-- System Status and Collections Overview -->
          <div class="grid grid-cols-1 xl:grid-cols-2 gap-6">
            <!-- System Status -->
            <SystemStatus />

            <!-- Quick Collections View -->
            <Card>
              <div slot="header" class="flex items-center justify-between">
                <h3 class="text-lg font-medium text-gray-900">
                  Recent Collections
                </h3>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => navigateToPage("collections")}
                >
                  View All
                  <Icon
                    icon="material-symbols:chevron-right"
                    class="w-4 h-4 ml-1"
                  />
                </Button>
              </div>

              <div class="text-center py-8 text-gray-500">
                <Icon
                  icon="material-symbols:view-list"
                  class="w-12 h-12 mx-auto mb-4"
                />
                <p>View collections in the Collections tab</p>
              </div>
            </Card>
          </div>
        </div>
      {:else if currentPage === "collections"}
        <!-- Collections Page -->
        <CollectionsList on:viewCollection={(e) => navigateToPage('collection-detail', { collectionName: e.detail.collectionName })} />
      {:else if currentPage === "collection-detail"}
        <!-- Collection Detail Page -->
        <CollectionDetail collectionName={currentParams.collectionName} />
      {:else if currentPage === "search"}
        <!-- Search Page -->
        <div class="space-y-6">
          <!-- Search Interface -->
          <SearchInterface autoFocus={true} />

          <!-- Search Results -->
          <SearchResults />
        </div>
      {:else if currentPage === "chat"}
        <!-- Chat Page -->
        <div class="flex-1 -m-4 sm:-m-6 min-h-0">
          <ChatInterface 
            showSidebar={true}
            autoFocus={true}
          />
        </div>
      {:else}
        <!-- Settings Page (Placeholder) -->
        <Card>
          <div class="text-center py-12">
            <div class="text-gray-500 mb-4">
              <Icon
                icon="material-symbols:settings"
                class="w-16 h-16 mx-auto"
              />
            </div>
            <h3 class="text-xl font-medium text-gray-900 mb-2">Settings</h3>
            <p class="text-gray-600 mb-6 max-w-md mx-auto">
              Configure system settings, manage connections, and customize your
              RAG system preferences.
            </p>
            <div
              class="inline-flex items-center px-4 py-2 bg-gray-100 text-gray-800 rounded-full text-sm font-medium"
            >
              <Icon icon="material-symbols:schedule" class="w-4 h-4 mr-2" />
              Coming Soon
            </div>
          </div>
        </Card>
      {/if}
    </main>
  </div>
</div>

<!-- Toast Notifications -->
<NotificationToast />

<!-- Article Preview Modal -->
<ArticlePreview />
