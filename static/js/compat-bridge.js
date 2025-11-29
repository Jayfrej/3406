/**
 * Compatibility Bridge for Legacy app.js
 *
 * This file provides backward compatibility by creating a TradingBotUI class
 * that delegates to the new modular system. This allows existing code to work
 * without modification while using the new architecture under the hood.
 */

class TradingBotUI {
    constructor() {
        // Legacy properties for compatibility
        this.accounts = [];
        this.webhookAccounts = [];
        this.webhookUrl = '';
        this.currentAction = null;
        this.refreshInterval = null;
        this.currentPage = 'accounts';
        this.copyPairs = [];
        this.copyHistory = [];
        this.masterAccounts = [];
        this.slaveAccounts = [];
        this.systemLogs = [];
        this.plans = [];

        console.log('[COMPAT] Legacy compatibility bridge initialized');
    }

    // =================== Delegated Methods ===================

    /**
     * Show toast notification
     */
    showToast(message, type = 'info', duration) {
        if (window.Toast) {
            window.Toast.show(message, type, duration);
        }
    }

    /**
     * Show loading overlay
     */
    showLoading() {
        if (window.Loading) {
            window.Loading.show();
        }
    }

    /**
     * Hide loading overlay
     */
    hideLoading() {
        if (window.Loading) {
            window.Loading.hide();
        }
    }

    /**
     * Show confirmation dialog
     */
    async showConfirmDialog(title, message) {
        if (window.Modal) {
            return await window.Modal.showConfirmDialog(title, message);
        }
        return confirm(message);
    }

    /**
     * Show custom confirmation
     */
    async showCustomConfirm(title, message) {
        if (window.Modal) {
            return await window.Modal.showCustomConfirm(title, message);
        }
        return confirm(message);
    }

    /**
     * Show modal
     */
    showModal(title, content, onConfirm, confirmText) {
        if (window.Modal) {
            return window.Modal.show(title, content, onConfirm, confirmText);
        }
    }

    /**
     * Close modal
     */
    closeModal() {
        if (window.Modal) {
            window.Modal.close();
        }
    }

    /**
     * Confirm action
     */
    confirmAction() {
        if (window.Modal) {
            window.Modal.confirm();
        }
    }

    /**
     * Escape HTML
     */
    escape(text) {
        if (window.Utils && window.Utils.escapeHtml) {
            return window.Utils.escapeHtml(text);
        }
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Format date
     */
    formatDate(dateString) {
        if (window.Utils && window.Utils.formatDate) {
            return window.Utils.formatDate(dateString);
        }
        return dateString;
    }

    /**
     * Fetch with auth
     */
    async fetchWithAuth(url, options = {}) {
        if (window.API) {
            return await window.API.fetchWithAuth(url, options);
        }
        return await fetch(url, options);
    }

    // =================== Account Management Delegates ===================

    /**
     * Load account management data
     */
    async loadAccountManagementData() {
        if (window.AccountManager && window.AccountUI) {
            await window.AccountManager.loadAccounts();
            this.accounts = window.AccountManager.getAccounts();
            window.AccountUI.renderAccountsTable();
            window.AccountUI.updateStats();
        }
    }

    /**
     * Add account (Account Management)
     */
    async addAccountAM() {
        if (window.AccountUI) {
            await window.AccountUI.addAccount('addAccountFormAM');
        }
    }

    /**
     * Perform account action (Account Management)
     */
    async performAccountActionAM(account, action) {
        if (window.AccountUI) {
            await window.AccountUI.performAction(account, action);
        }
    }

    /**
     * Update accounts table (Account Management)
     */
    updateAccountsTableAM() {
        if (window.AccountUI) {
            window.AccountUI.renderAccountsTable('accountsTableBodyAM');
        }
    }

    /**
     * Update stats (Account Management)
     */
    updateStatsAM() {
        if (window.AccountUI) {
            window.AccountUI.updateStats('AM');
        }
    }

    // =================== Webhook Delegates ===================

    /**
     * Load data (Webhook page)
     */
    async loadData() {
        if (window.WebhookManager && window.AccountManager) {
            await window.WebhookManager.loadWebhookAccounts();
            await window.AccountManager.loadAccounts();
            this.webhookAccounts = window.WebhookManager.getAccounts();
            this.accounts = window.AccountManager.getAccounts();

            if (window.WebhookUI) {
                window.WebhookUI.renderAccountsTable(this.accounts);
                window.WebhookUI.updateStats();
            }
        }
    }

    /**
     * Add account (Webhook page)
     */
    async addAccount() {
        if (window.AccountUI) {
            await window.AccountUI.addAccount('addAccountForm');
        }
    }

    /**
     * Update webhook display
     */
    updateWebhookDisplay() {
        if (window.WebhookUI) {
            window.WebhookUI.displayWebhookUrl();
        }
    }

    /**
     * Update accounts table (Webhook page)
     */
    updateAccountsTable() {
        if (window.WebhookUI && window.AccountManager) {
            const serverAccounts = window.AccountManager.getAccounts();
            window.WebhookUI.renderAccountsTable(serverAccounts);
        }
    }

    /**
     * Update stats (Webhook page)
     */
    updateStats() {
        if (window.WebhookUI) {
            window.WebhookUI.updateStats();
        }
    }

    /**
     * Copy webhook URL
     */
    async copyWebhookUrl() {
        if (window.WebhookUI) {
            await window.WebhookUI.copyWebhookUrl();
        }
    }

    /**
     * Copy copy trading endpoint
     */
    async copyCopyTradingEndpoint() {
        if (window.WebhookUI) {
            await window.WebhookUI.copyCopyTradingEndpoint();
        }
    }

    // =================== Copy Trading Delegates ===================

    /**
     * Load copy pairs
     */
    async loadCopyPairs() {
        if (window.CopyTradingManager) {
            await window.CopyTradingManager.loadCopyPairs();
            this.copyPairs = window.CopyTradingManager.getCopyPairs();
            this.plans = window.CopyTradingManager.getPlans();
        }
    }

    /**
     * Load copy history
     */
    async loadCopyHistory() {
        if (window.CopyTradingManager) {
            await window.CopyTradingManager.loadCopyHistory();
            this.copyHistory = window.CopyTradingManager.getCopyHistory();
        }
    }

    /**
     * Load master accounts
     */
    async loadMasterAccounts() {
        if (window.CopyTradingManager) {
            await window.CopyTradingManager.loadMasterAccounts();
            this.masterAccounts = window.CopyTradingManager.getMasterAccounts();
        }
    }

    /**
     * Load slave accounts
     */
    async loadSlaveAccounts() {
        if (window.CopyTradingManager) {
            await window.CopyTradingManager.loadSlaveAccounts();
            this.slaveAccounts = window.CopyTradingManager.getSlaveAccounts();
        }
    }

    /**
     * Render copy pairs
     */
    renderCopyPairs() {
        if (window.CopyTradingUI) {
            window.CopyTradingUI.renderCopyPairs();
        }
    }

    /**
     * Render copy history
     */
    renderCopyHistory() {
        if (window.CopyTradingUI) {
            window.CopyTradingUI.renderCopyHistory();
        }
    }

    /**
     * Render master accounts
     */
    renderMasterAccounts() {
        if (window.CopyTradingUI) {
            window.CopyTradingUI.renderMasterAccounts();
        }
    }

    /**
     * Render slave accounts
     */
    renderSlaveAccounts() {
        if (window.CopyTradingUI) {
            window.CopyTradingUI.renderSlaveAccounts();
        }
    }

    /**
     * Update pair count
     */
    updatePairCount() {
        if (window.CopyTradingUI) {
            window.CopyTradingUI.updatePairCount();
        }
    }

    // =================== System Delegates ===================

    /**
     * Load system logs
     */
    async loadSystemLogs() {
        if (window.SystemManager) {
            await window.SystemManager.loadSystemLogs();
            this.systemLogs = window.SystemManager.getSystemLogs();
        }
    }

    /**
     * Render system logs
     */
    renderSystemLogs() {
        if (window.SystemUI) {
            window.SystemUI.renderSystemLogs();
        }
    }

    /**
     * Update last update time
     */
    updateLastUpdateTime() {
        if (window.SystemUI) {
            window.SystemUI.updateLastUpdateTime();
        }
    }

    /**
     * Clear system logs
     */
    async clearSystemLogs() {
        if (window.SystemUI) {
            await window.SystemUI.clearSystemLogs();
        }
    }

    // =================== Settings Delegates ===================

    /**
     * Load all settings
     */
    async loadAllSettings() {
        if (window.SettingsUI) {
            await window.SettingsUI.loadAndRenderSettings();
        }
    }

    /**
     * Load email settings
     */
    async loadEmailSettings() {
        if (window.SettingsUI) {
            await window.SettingsUI.loadEmailSettings();
        }
    }

    /**
     * Save email settings
     */
    async saveEmailSettings() {
        if (window.SettingsUI) {
            await window.SettingsUI.saveEmailSettings();
        }
    }

    /**
     * Test email settings
     */
    async testEmailSettings() {
        if (window.SettingsUI) {
            await window.SettingsUI.testEmailSettings();
        }
    }

    /**
     * Save rate limit settings
     */
    async saveRateLimitSettings() {
        if (window.SettingsUI) {
            await window.SettingsUI.saveRateLimitSettings();
        }
    }

    /**
     * Reset rate limit settings
     */
    async resetRateLimitSettings() {
        if (window.SettingsUI) {
            await window.SettingsUI.resetRateLimitSettings();
        }
    }

    /**
     * Populate symbol mapping accounts
     */
    async populateSymbolMappingAccounts() {
        if (window.SettingsUI) {
            await window.SettingsUI.populateSymbolMappingAccounts();
        }
    }

    /**
     * Load account symbol mappings
     */
    async loadAccountSymbolMappings(accountNumber) {
        if (window.SettingsUI) {
            await window.SettingsUI.loadAccountSymbolMappings(accountNumber);
        }
    }

    /**
     * Add symbol mapping
     */
    async addSymbolMapping() {
        if (window.SettingsUI) {
            await window.SettingsUI.addSymbolMapping();
        }
    }

    /**
     * Remove symbol mapping
     */
    async removeSymbolMapping(from) {
        if (window.SettingsUI) {
            await window.SettingsUI.removeSymbolMapping(from);
        }
    }

    // =================== Page Management ===================

    /**
     * Switch page
     */
    switchPage(page) {
        if (window.AppCoordinator) {
            window.AppCoordinator.navigateToPage(page);
        }
        this.currentPage = page;
    }

    /**
     * Initialize page
     */
    async initializePage(page) {
        if (window.AppCoordinator) {
            await window.AppCoordinator.initializePage(page);
        }
    }

    // =================== Lifecycle Methods ===================

    /**
     * Initialize (legacy - now handled by AppCoordinator)
     */
    init() {
        console.log('[COMPAT] Legacy init() called - delegating to AppCoordinator');
        // AppCoordinator handles initialization
    }

    /**
     * Start auto refresh
     */
    startAutoRefresh() {
        if (window.AppCoordinator) {
            window.AppCoordinator.startAutoRefresh();
        }
    }

    /**
     * Stop auto refresh
     */
    stopAutoRefresh() {
        if (window.AppCoordinator) {
            window.AppCoordinator.stopAutoRefresh();
        }
    }

    /**
     * Cleanup
     */
    cleanup() {
        if (window.AppCoordinator) {
            window.AppCoordinator.cleanup();
        }
    }
}

// Create global instance for backward compatibility
window.ui = new TradingBotUI();

console.log('[COMPAT] Compatibility bridge loaded - window.ui available');

