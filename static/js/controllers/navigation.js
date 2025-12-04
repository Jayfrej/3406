/**
 * @file navigation.js
 * @description Page navigation controller
 * @module controllers/navigation
 */

import appState from '../config/state.js';
import { PAGES } from '../config/constants.js';

/**
 * Navigation controller for page switching
 */
class NavigationController {
  constructor() {
    this.pageInitializers = {};
  }

  /**
   * Register page initializer
   * @param {string} page - Page name
   * @param {Function} initializer - Async initialization function
   */
  registerInitializer(page, initializer) {
    this.pageInitializers[page] = initializer;
  }

  /**
   * Switch to a page
   * @param {string} page - Page name
   */
  async switchTo(page) {
    console.log(`[NAV] Switching to page: ${page}`);
    appState.setCurrentPage(page);

    // Update navigation items
    document.querySelectorAll('.nav-item').forEach(item => {
      item.classList.toggle('active', item.dataset.page === page);
    });

    // Update page content visibility
    document.querySelectorAll('.page-content').forEach(content => {
      content.classList.toggle('active', content.id === `page-${page}`);
    });

    // Update header
    this.updateHeader(page);

    // Hide sidebar on mobile after selection
    const sidebar = document.getElementById('sidebar');
    if (sidebar && window.innerWidth <= 1024) {
      sidebar.classList.remove('show');
    }

    // Initialize page data
    await this.initializePage(page);
  }

  /**
   * Update header content based on page
   * @param {string} page
   */
  updateHeader(page) {
    const headerContent = document.getElementById('headerContent');
    if (!headerContent) return;

    const headers = {
      [PAGES.ACCOUNTS]: {
        title: 'Account Management',
        icon: 'fa-table',
        description: 'Manage your MT5 trading accounts'
      },
      [PAGES.WEBHOOK]: {
        title: 'MT5 Trading Bot',
        icon: 'fa-robot',
        description: 'Multi-Account Webhook Manager'
      },
      [PAGES.COPYTRADING]: {
        title: 'Copy Trading',
        icon: 'fa-copy',
        description: 'Master-Slave Account Management'
      },
      [PAGES.SYSTEM]: {
        title: 'System Information',
        icon: 'fa-info-circle',
        description: 'Server status and configuration'
      },
      [PAGES.SETTINGS]: {
        title: 'Settings',
        icon: 'fa-cog',
        description: 'Configure system settings'
      }
    };

    const config = headers[page] || headers[PAGES.ACCOUNTS];
    headerContent.innerHTML = `
      <h1><i class="fas ${config.icon}"></i> ${config.title}</h1>
      <p>${config.description}</p>
    `;
  }

  /**
   * Initialize page-specific data
   * @param {string} page
   */
  async initializePage(page) {
    console.log(`[NAV] Initializing page: ${page}`);

    const initializer = this.pageInitializers[page];
    if (initializer) {
      await initializer();
    }
  }

  /**
   * Setup navigation event listeners
   */
  setupListeners() {
    // Sidebar navigation clicks
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(item => {
      item.addEventListener('click', (e) => {
        e.preventDefault();
        const page = item.dataset.page;
        this.switchTo(page);
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
  }

  /**
   * Get current page
   * @returns {string}
   */
  getCurrentPage() {
    return appState.currentPage;
  }
}

// Export singleton
const navigation = new NavigationController();
export default navigation;

// Also export class for testing
export { NavigationController };

