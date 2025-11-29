/**
 * Account UI Module
 *
 * Handles account management UI rendering and interactions:
 * - Render accounts table
 * - Update statistics
 * - Handle user actions
 * - Display modals and confirmations
 */

class AccountUI {
    constructor() {
        this.accountManager = window.AccountManager;
    }

    /**
     * Render accounts table
     * @param {string} tableBodyId - Table body element ID
     */
    renderAccountsTable(tableBodyId = 'accountsTableBodyAM') {
        const tbody = document.getElementById(tableBodyId);
        if (!tbody) return;

        const accounts = this.accountManager.getAccounts();

        if (!accounts.length) {
            tbody.innerHTML = `
                <tr class="no-data">
                    <td colspan="6">
                        <div class="no-data-message">
                            <i class="fas fa-inbox"></i>
                            <p>No accounts found. Add your first account above.</p>
                        </div>
                    </td>
                </tr>`;
            return;
        }

        tbody.innerHTML = accounts.map(account => {
            const statusClass = (account.status || 'Wait for Activate')
                .toLowerCase()
                .replace(/ /g, '-');
            const lastSeenText = this.formatLastSeen(account.last_seen);

            return `
                <tr data-account="${this.escapeHtml(account.account)}">
                    <td>
                        <span class="status-badge ${this.escapeHtml(statusClass)}">
                            <i class="fas fa-circle"></i>
                            ${this.escapeHtml(account.status)}
                        </span>
                    </td>
                    <td><strong>${this.escapeHtml(account.account)}</strong></td>
                    <td>${this.escapeHtml(account.nickname || '-')}</td>
                    <td>${this.escapeHtml(account.broker || '-')}</td>
                    <td title="${this.escapeHtml(account.last_seen || '')}">${lastSeenText}</td>
                    <td>
                        <div class="action-buttons">
                            ${this.renderActionButtons(account)}
                        </div>
                    </td>
                </tr>`;
        }).join('');
    }

    /**
     * Render action buttons for an account
     * @param {Object} account - Account object
     * @returns {string} HTML for action buttons
     */
    renderActionButtons(account) {
        let buttons = [];

        // Symbol mapping button
        buttons.push(`
            <button class="btn btn-info btn-sm"
                    onclick="window.AccountUI.showSymbolMapping('${this.escapeHtml(account.account)}')"
                    title="View Symbol Mappings">
                <i class="fas fa-exchange-alt"></i>
            </button>
        `);

        // Pause button (if online)
        if (account.status === 'Online') {
            buttons.push(`
                <button class="btn btn-warning btn-sm"
                        onclick="window.AccountUI.performAction('${this.escapeHtml(account.account)}', 'pause')"
                        title="Pause Account">
                    <i class="fas fa-pause"></i>
                </button>
            `);
        }

        // Resume button (if paused)
        if (account.status === 'PAUSE') {
            buttons.push(`
                <button class="btn btn-success btn-sm"
                        onclick="window.AccountUI.performAction('${this.escapeHtml(account.account)}', 'resume')"
                        title="Resume Account">
                    <i class="fas fa-play"></i>
                </button>
            `);
        }

        // Delete button
        buttons.push(`
            <button class="btn btn-secondary btn-sm"
                    onclick="window.AccountUI.performAction('${this.escapeHtml(account.account)}', 'delete')"
                    title="Delete">
                <i class="fas fa-trash"></i>
            </button>
        `);

        return buttons.join('');
    }

    /**
     * Update account statistics
     * @param {string} prefix - Element ID prefix ('AM' for account management)
     */
    updateStats(prefix = 'AM') {
        const stats = this.accountManager.getStats();

        const totalEl = document.getElementById(`totalAccounts${prefix}`);
        const onlineEl = document.getElementById(`onlineAccounts${prefix}`);
        const offlineEl = document.getElementById(`offlineAccounts${prefix}`);

        if (totalEl) totalEl.textContent = stats.total;
        if (onlineEl) onlineEl.textContent = stats.online;
        if (offlineEl) offlineEl.textContent = stats.offline;
    }

    /**
     * Add new account
     * @param {string} formId - Form element ID
     * @returns {Promise<void>}
     */
    async addAccount(formId = 'addAccountFormAM') {
        const form = document.getElementById(formId);
        if (!form) return;

        const formData = new FormData(form);
        const account = String(formData.get('account') || '').trim();
        const nickname = String(formData.get('nickname') || '').trim();

        if (!account) {
            this.showToast('Please enter account number', 'warning');
            return;
        }

        this.showLoading();

        try {
            const result = await this.accountManager.addAccount(account, nickname);

            if (result.success) {
                this.showToast(result.message, 'success');
                form.reset();

                // Refresh displays
                await this.refresh();
            } else {
                this.showToast(result.error, 'error');
            }
        } catch (error) {
            console.error('Add account error:', error);
            this.showToast('Failed to add account', 'error');
        } finally {
            this.hideLoading();
        }
    }

    /**
     * Perform account action (delete, pause, resume, etc.)
     * @param {string} accountNumber - Account number
     * @param {string} action - Action to perform
     * @returns {Promise<void>}
     */
    async performAction(accountNumber, action) {
        // Show confirmation dialog
        const confirmed = await this.showConfirmDialog(action, accountNumber);
        if (!confirmed) return;

        this.showLoading();

        try {
            let result;

            switch (action) {
                case 'delete':
                    result = await this.accountManager.deleteAccount(accountNumber);
                    break;
                case 'pause':
                    result = await this.accountManager.pauseAccount(accountNumber);
                    break;
                case 'resume':
                    result = await this.accountManager.resumeAccount(accountNumber);
                    break;
                case 'restart':
                    result = await this.accountManager.restartAccount(accountNumber);
                    break;
                case 'stop':
                    result = await this.accountManager.stopAccount(accountNumber);
                    break;
                case 'open':
                    result = await this.accountManager.openAccountTerminal(accountNumber);
                    break;
                default:
                    this.showToast('Action not available', 'warning');
                    return;
            }

            if (result.success) {
                let message = result.message;

                // Special message for delete with deleted pairs
                if (action === 'delete' && result.deletedPairs > 0) {
                    message = `Account deleted (removed ${result.deletedPairs} copy pair(s))`;
                }

                this.showToast(message, 'success');

                // Refresh displays
                await this.refresh();

                // If delete action, also refresh copy trading data
                if (action === 'delete' && window.CopyTradingManager) {
                    await window.CopyTradingManager.loadCopyPairs();
                    if (window.CopyTradingUI) {
                        window.CopyTradingUI.renderAll();
                    }
                }
            } else {
                this.showToast(result.error, 'error');
            }
        } catch (error) {
            console.error(`${action} account error:`, error);
            this.showToast(`Failed to ${action} account`, 'error');
        } finally {
            this.hideLoading();
        }
    }

    /**
     * Show confirmation dialog
     * @param {string} action - Action name
     * @param {string} accountNumber - Account number
     * @returns {Promise<boolean>} True if confirmed
     */
    async showConfirmDialog(action, accountNumber) {
        const messages = {
            delete: 'Are you sure you want to delete this account? This action cannot be undone.',
            pause: 'Pause this account? The account will not receive any signals until resumed.',
            resume: 'Resume this account? The account will start receiving signals again.',
            restart: 'Restart this account?',
            stop: 'Stop this account?'
        };

        const message = messages[action] || `Perform ${action} on account ${accountNumber}?`;
        const title = `Confirm ${action.charAt(0).toUpperCase() + action.slice(1)}`;

        // Use app's showConfirmDialog if available
        if (window.app && window.app.showConfirmDialog) {
            return await window.app.showConfirmDialog(title, message);
        }

        // Fallback to browser confirm
        return confirm(message);
    }

    /**
     * Show symbol mapping modal
     * @param {string} accountNumber - Account number
     */
    showSymbolMapping(accountNumber) {
        if (window.app && window.app.showSymbolMappingModal) {
            window.app.showSymbolMappingModal(accountNumber);
        } else {
            this.showToast('Symbol mapping feature not available', 'warning');
        }
    }

    /**
     * Filter accounts table by search term
     * @param {string} searchTerm - Search term
     * @param {string} tableBodyId - Table body element ID
     */
    filterTable(searchTerm, tableBodyId = 'accountsTableBodyAM') {
        const rows = document.querySelectorAll(`#${tableBodyId} tr:not(.no-data)`);
        const term = String(searchTerm || '').toLowerCase();

        rows.forEach(row => {
            const text = row.textContent.toLowerCase();
            row.style.display = text.includes(term) ? '' : 'none';
        });
    }

    /**
     * Refresh all account displays
     * @returns {Promise<void>}
     */
    async refresh() {
        await this.accountManager.loadAccounts();
        this.renderAccountsTable();
        this.updateStats();

        // Also refresh webhook page if needed
        if (window.WebhookManager) {
            await window.WebhookManager.loadWebhookAccounts();
            if (window.WebhookUI) {
                window.WebhookUI.renderAccountsTable(this.accountManager.getAccounts());
                window.WebhookUI.updateStats();
            }
        }
    }

    /**
     * Format last seen timestamp
     * @param {string} lastSeenStr - Last seen timestamp string
     * @returns {string} Formatted string
     */
    formatLastSeen(lastSeenStr) {
        if (!lastSeenStr) return '-';

        const lastSeen = new Date(lastSeenStr);
        const now = new Date();
        const diffSeconds = Math.floor((now - lastSeen) / 1000);

        if (diffSeconds < 10) {
            return 'Just now';
        } else if (diffSeconds < 60) {
            return `${diffSeconds}s ago`;
        } else if (diffSeconds < 3600) {
            const diffMinutes = Math.floor(diffSeconds / 60);
            return `${diffMinutes}m ago`;
        } else if (diffSeconds < 86400) {
            const diffHours = Math.floor(diffSeconds / 3600);
            return `${diffHours}h ago`;
        } else {
            return lastSeen.toLocaleString();
        }
    }

    /**
     * Escape HTML to prevent XSS
     * @param {string} str - String to escape
     * @returns {string} Escaped string
     */
    escapeHtml(str) {
        if (window.Utils && window.Utils.escapeHtml) {
            return window.Utils.escapeHtml(str);
        }
        if (typeof str !== 'string') return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    /**
     * Show toast notification
     * @param {string} message - Message to display
     * @param {string} type - Toast type (success, error, warning, info)
     */
    showToast(message, type = 'info') {
        if (window.app && window.app.showToast) {
            window.app.showToast(message, type);
        } else {
            console.log(`[TOAST:${type}] ${message}`);
        }
    }

    /**
     * Show loading indicator
     */
    showLoading() {
        if (window.app && window.app.showLoading) {
            window.app.showLoading();
        }
    }

    /**
     * Hide loading indicator
     */
    hideLoading() {
        if (window.app && window.app.hideLoading) {
            window.app.hideLoading();
        }
    }
}

// Create singleton instance
window.AccountUI = new AccountUI();

// Export class
window.AccountUIClass = AccountUI;

