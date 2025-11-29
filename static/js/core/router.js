/**
 * Router Module
 *
 * Handles page navigation and routing:
 * - Page switching
 * - Navigation UI updates
 * - Page initialization
 * - History management
 */

class Router {
    constructor() {
        this.currentPage = 'accounts'; // Default page
        this.pages = ['accounts', 'webhook', 'copytrading', 'system', 'settings'];
    }

    /**
     * Initialize router
     */
    init() {
        // Setup navigation click handlers
        this.setupNavigation();

        // Setup sidebar toggle for mobile
        this.setupSidebarToggle();

        // Set default page
        this.navigateTo(this.currentPage, false);
    }

    /**
     * Setup navigation event listeners
     */
    setupNavigation() {
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const page = item.dataset.page;
                if (page) {
                    this.navigateTo(page);
                }
            });
        });
    }

    /**
     * Setup sidebar toggle button
     */
    setupSidebarToggle() {
        const sidebarToggle = document.getElementById('sidebarToggle');
        const sidebarCollapseBtn = document.getElementById('sidebarCollapseBtn');
        const sidebar = document.getElementById('sidebar');

        if (sidebarToggle && sidebar) {
            sidebarToggle.addEventListener('click', () => {
                sidebar.classList.toggle('show');
            });
        }

        if (sidebarCollapseBtn && sidebar) {
            sidebarCollapseBtn.addEventListener('click', () => {
                sidebar.classList.toggle('collapsed');
            });
        }

        // Close sidebar when clicking outside on mobile
        document.addEventListener('click', (e) => {
            if (window.innerWidth <= 1024 && sidebar) {
                if (!sidebar.contains(e.target) && !sidebarToggle?.contains(e.target)) {
                    sidebar.classList.remove('show');
                }
            }
        });
    }

    /**
     * Navigate to a page
     * @param {string} page - Page name
     * @param {boolean} initPage - Whether to initialize page data
     */
    navigateTo(page, initPage = true) {
        // Validate page
        if (!this.pages.includes(page)) {
            console.warn(`[ROUTER] Invalid page: ${page}`);
            return;
        }

        // Update current page
        this.currentPage = page;

        // Update navigation UI
        this.updateNavigation(page);

        // Update page content visibility
        this.updatePageContent(page);

        // Update header
        this.updateHeader(page);

        // Hide sidebar on mobile after selection
        this.hideSidebarOnMobile();

        // Initialize page data if needed
        if (initPage && window.app) {
            window.app.initializePage(page);
        }

        console.log(`[ROUTER] Navigated to: ${page}`);
    }

    /**
     * Update navigation active state
     * @param {string} page - Active page name
     */
    updateNavigation(page) {
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.toggle('active', item.dataset.page === page);
        });
    }

    /**
     * Update page content visibility
     * @param {string} page - Active page name
     */
    updatePageContent(page) {
        document.querySelectorAll('.page-content').forEach(content => {
            content.classList.toggle('active', content.id === `page-${page}`);
        });
    }

    /**
     * Update header content
     * @param {string} page - Page name
     */
    updateHeader(page) {
        const headerContent = document.getElementById('headerContent');
        if (!headerContent) return;

        const headers = {
            'accounts': {
                icon: 'fa-table',
                title: 'Account Management',
                subtitle: 'Manage your MT5 trading accounts'
            },
            'webhook': {
                icon: 'fa-robot',
                title: 'MT5 Trading Bot',
                subtitle: 'Multi-Account Webhook Manager'
            },
            'copytrading': {
                icon: 'fa-copy',
                title: 'Copy Trading',
                subtitle: 'Master-Slave Account Management'
            },
            'system': {
                icon: 'fa-info-circle',
                title: 'System Information',
                subtitle: 'Server status and configuration'
            },
            'settings': {
                icon: 'fa-cog',
                title: 'Settings',
                subtitle: 'Configure system settings'
            }
        };

        const header = headers[page] || headers['accounts'];
        headerContent.innerHTML = `
            <h1><i class="fas ${header.icon}"></i> ${header.title}</h1>
            <p>${header.subtitle}</p>
        `;
    }

    /**
     * Hide sidebar on mobile after navigation
     */
    hideSidebarOnMobile() {
        const sidebar = document.getElementById('sidebar');
        if (sidebar && window.innerWidth <= 1024) {
            sidebar.classList.remove('show');
        }
    }

    /**
     * Get current page
     * @returns {string} Current page name
     */
    getCurrentPage() {
        return this.currentPage;
    }

    /**
     * Check if on specific page
     * @param {string} page - Page name to check
     * @returns {boolean} True if on that page
     */
    isCurrentPage(page) {
        return this.currentPage === page;
    }

    /**
     * Get all available pages
     * @returns {Array<string>} List of page names
     */
    getPages() {
        return [...this.pages];
    }
}

// Create singleton instance
window.Router = new Router();

// Export for use in modules
window.RouterClass = Router;

