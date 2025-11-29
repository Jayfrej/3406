/**
 * Main Application Coordinator
 *
 * Initializes and coordinates all modules:
 * - Core utilities (API, Auth, Theme, Router)
 * - Feature modules (Webhooks, Accounts, Copy Trading, System, Settings)
 * - UI components (Toast, Modal, Loading)
 * - App lifecycle management
 */

class AppCoordinator {
    constructor() {
        this.initialized = false;
        this.currentPage = 'accounts';
        this.refreshInterval = null;
    }

    /**
     * Initialize application
     * @returns {Promise<void>}
     */
    async init() {
        if (this.initialized) {
            console.warn('[APP] Already initialized');
            return;
        }

        console.log('[APP] Initializing application...');

        try {
            // 1. Initialize theme
            if (window.Theme) {
                window.Theme.init();
            }

            // 2. Ensure authentication
            if (window.Auth) {
                await window.Auth.ensureLogin();
            }

            // 3. Initialize router
            if (window.Router) {
                window.Router.init();
            }

            // 4. Setup global event listeners
            this.setupEventListeners();

            // 5. Load initial data for default page (accounts)
            this.currentPage = 'accounts';
            await this.initializePage('accounts');

            // 6. Start auto-refresh
            this.startAutoRefresh();

            this.initialized = true;
            console.log('[APP] Application initialized successfully');

        } catch (error) {
            console.error('[APP] Initialization error:', error);
            if (window.Toast) {
                window.Toast.error('Failed to initialize application');
            }
        }
    }

    /**
     * Setup global event listeners
     */
    setupEventListeners() {
        // Theme toggle button
        const themeBtn = document.getElementById('themeToggleBtn');
        if (themeBtn && window.Theme) {
            themeBtn.addEventListener('click', () => window.Theme.toggleTheme());
        }

        // Sidebar navigation
        const navItems = document.querySelectorAll('.nav-item');
        navItems.forEach(item => {
            item.addEventListener('click', async (e) => {
                e.preventDefault();
                const page = item.dataset.page;
                if (page) {
                    await this.navigateToPage(page);
                }
            });
        });

        // Sidebar toggle for mobile
        const sidebarToggle = document.getElementById('sidebarToggle');
        const sidebar = document.getElementById('sidebar');
        if (sidebarToggle && sidebar) {
            sidebarToggle.addEventListener('click', () => {
                sidebar.classList.toggle('show');
            });
        }

        // Sidebar collapse button
        const sidebarCollapseBtn = document.getElementById('sidebarCollapseBtn');
        if (sidebarCollapseBtn && sidebar) {
            sidebarCollapseBtn.addEventListener('click', () => {
                sidebar.classList.toggle('collapsed');
            });
        }

        // Online/offline detection
        window.addEventListener('online', async () => {
            if (window.Toast) {
                window.Toast.success('Connection restored');
            }
            await this.refreshCurrentPage();
        });

        window.addEventListener('offline', () => {
            if (window.Toast) {
                window.Toast.warning('Connection lost');
            }
        });

        // Close sidebar on outside click (mobile)
        document.addEventListener('click', (e) => {
            if (window.innerWidth <= 1024 && sidebar) {
                if (!sidebar.contains(e.target) && !sidebarToggle?.contains(e.target)) {
                    sidebar.classList.remove('show');
                }
            }
        });

        console.log('[APP] Event listeners setup complete');
    }

    /**
     * Navigate to a page
     * @param {string} page - Page name
     * @returns {Promise<void>}
     */
    async navigateToPage(page) {
        console.log(`[APP] Navigating to: ${page}`);

        // Cleanup current page
        await this.cleanupCurrentPage();

        // Update current page
        this.currentPage = page;

        // Use router for navigation
        if (window.Router) {
            window.Router.navigateTo(page, false);
        }

        // Initialize new page
        await this.initializePage(page);
    }

    /**
     * Initialize page-specific data and UI
     * @param {string} page - Page name
     * @returns {Promise<void>}
     */
    async initializePage(page) {
        console.log(`[APP] Initializing page: ${page}`);

        if (window.Loading) {
            window.Loading.show();
        }

        try {
            switch (page) {
                case 'accounts':
                    await this.initAccountsPage();
                    break;

                case 'webhook':
                    await this.initWebhookPage();
                    break;

                case 'copytrading':
                    await this.initCopyTradingPage();
                    break;

                case 'system':
                    await this.initSystemPage();
                    break;

                case 'settings':
                    await this.initSettingsPage();
                    break;

                default:
                    console.warn(`[APP] Unknown page: ${page}`);
            }
        } catch (error) {
            console.error(`[APP] Error initializing ${page}:`, error);
            if (window.Toast) {
                window.Toast.error(`Failed to load ${page} page`);
            }
        } finally {
            if (window.Loading) {
                window.Loading.hide();
            }
        }
    }

    /**
     * Initialize Accounts page
     * @returns {Promise<void>}
     */
    async initAccountsPage() {
        if (window.AccountManager && window.AccountUI) {
            await window.AccountManager.loadAccounts();
            window.AccountUI.renderAccountsTable();
            window.AccountUI.updateStats();
        }
    }

    /**
     * Initialize Webhook page
     * @returns {Promise<void>}
     */
    async initWebhookPage() {
        if (window.WebhookManager && window.WebhookUI) {
            await window.WebhookManager.loadWebhookUrl();
            await window.WebhookManager.loadWebhookAccounts();

            // Get server accounts for status display
            const serverAccounts = window.AccountManager ?
                window.AccountManager.getAccounts() : [];

            window.WebhookUI.displayWebhookUrl();
            window.WebhookUI.renderAccountsTable(serverAccounts);
            window.WebhookUI.updateStats();
        }
    }

    /**
     * Initialize Copy Trading page
     * @returns {Promise<void>}
     */
    async initCopyTradingPage() {
        if (window.CopyTradingManager && window.CopyTradingUI) {
            // Load all copy trading data
            await Promise.all([
                window.CopyTradingManager.loadCopyPairs(),
                window.CopyTradingManager.loadMasterAccounts(),
                window.CopyTradingManager.loadSlaveAccounts(),
                window.CopyTradingManager.loadCopyHistory()
            ]);

            // Render all UI
            window.CopyTradingUI.renderAll();

            // Subscribe to real-time events
            window.CopyTradingManager.subscribeCopyEvents();
            window.CopyTradingManager.setupCopyHistoryAutoRefresh();
        }
    }

    /**
     * Initialize System page
     * @returns {Promise<void>}
     */
    async initSystemPage() {
        if (window.SystemUI) {
            await window.SystemUI.initialize();
        }
    }

    /**
     * Initialize Settings page
     * @returns {Promise<void>}
     */
    async initSettingsPage() {
        if (window.SettingsUI) {
            await window.SettingsUI.initialize();
        }
    }

    /**
     * Cleanup current page before navigating away
     * @returns {Promise<void>}
     */
    async cleanupCurrentPage() {
        console.log(`[APP] Cleaning up page: ${this.currentPage}`);

        switch (this.currentPage) {
            case 'copytrading':
                if (window.CopyTradingManager) {
                    window.CopyTradingManager.unsubscribeCopyEvents();
                    window.CopyTradingManager.stopCopyHistoryAutoRefresh();
                }
                break;

            case 'system':
                if (window.SystemUI) {
                    window.SystemUI.cleanup();
                }
                break;
        }
    }

    /**
     * Refresh current page data
     * @returns {Promise<void>}
     */
    async refreshCurrentPage() {
        console.log(`[APP] Refreshing page: ${this.currentPage}`);

        try {
            switch (this.currentPage) {
                case 'accounts':
                    if (window.AccountUI) {
                        await window.AccountUI.refresh();
                    }
                    break;

                case 'webhook':
                    if (window.WebhookManager && window.WebhookUI) {
                        await window.WebhookManager.loadWebhookAccounts();
                        const serverAccounts = window.AccountManager ?
                            window.AccountManager.getAccounts() : [];
                        window.WebhookUI.renderAccountsTable(serverAccounts);
                    }
                    break;

                case 'copytrading':
                    if (window.CopyTradingUI) {
                        await window.CopyTradingUI.refresh();
                    }
                    break;

                case 'system':
                    if (window.SystemUI) {
                        await window.SystemUI.refresh();
                    }
                    break;
            }
        } catch (error) {
            console.error(`[APP] Error refreshing ${this.currentPage}:`, error);
        }
    }

    /**
     * Start auto-refresh interval
     */
    startAutoRefresh() {
        if (this.refreshInterval) {
            return;
        }

        // Refresh every 30 seconds when page is visible
        this.refreshInterval = setInterval(async () => {
            if (!document.hidden) {
                await this.refreshCurrentPage();
            }
        }, 30000);

        console.log('[APP] Auto-refresh started (30s interval)');
    }

    /**
     * Stop auto-refresh interval
     */
    stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
            console.log('[APP] Auto-refresh stopped');
        }
    }

    /**
     * Cleanup on app shutdown
     */
    cleanup() {
        this.stopAutoRefresh();

        if (window.CopyTradingManager) {
            window.CopyTradingManager.unsubscribeCopyEvents();
            window.CopyTradingManager.stopCopyHistoryAutoRefresh();
        }

        if (window.SystemManager) {
            window.SystemManager.unsubscribeSystemLogs();
        }

        console.log('[APP] Cleanup complete');
    }

    /**
     * Get current page
     * @returns {string} Current page name
     */
    getCurrentPage() {
        return this.currentPage;
    }
}

// Create global app coordinator instance
window.AppCoordinator = new AppCoordinator();

// Export class
window.AppCoordinatorClass = AppCoordinator;

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.AppCoordinator.init();
    });
} else {
    // DOM already loaded
    window.AppCoordinator.init();
}

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    window.AppCoordinator.cleanup();
});

console.log('[APP] Main coordinator loaded');

