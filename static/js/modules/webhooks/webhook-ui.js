/**
 * Webhook UI Module
 *
 * Handles webhook page UI rendering and updates:
 * - Display webhook URL
 * - Render webhook accounts table
 * - Update stats
 */

class WebhookUI {
    constructor() {
        this.webhookManager = window.WebhookManager;
    }

    /**
     * Display webhook URL in all relevant elements
     */
    displayWebhookUrl() {
        const url = this.webhookManager.getWebhookUrl();

        const webhookElement = document.getElementById('webhookUrl');
        const webhookElementAM = document.getElementById('webhookUrlAM');
        const webhookEndpointElement = document.getElementById('webhookEndpoint');
        const webhookEndpointSystemElement = document.getElementById('webhookEndpointSystem');

        // Update Webhook URL fields
        if (webhookElement && url) webhookElement.value = url;
        if (webhookElementAM && url) webhookElementAM.value = url;
        if (webhookEndpointElement && url) webhookEndpointElement.textContent = url;
        if (webhookEndpointSystemElement && url) webhookEndpointSystemElement.textContent = url;

        // Update Copy Trading Endpoint
        this.updateCopyTradingEndpoint(url);
    }

    /**
     * Update Copy Trading Endpoint display
     * @param {string} webhookUrl - Webhook URL
     */
    updateCopyTradingEndpoint(webhookUrl) {
        const copyTradingEndpointSystemElement = document.getElementById('copyTradingEndpointSystem');
        if (!copyTradingEndpointSystemElement) return;

        try {
            let baseUrl = '';
            if (webhookUrl) {
                const url = new URL(webhookUrl);
                baseUrl = `${url.protocol}//${url.host}`;
            } else {
                baseUrl = `${window.location.protocol}//${window.location.host}`;
            }
            const copyTradingEndpoint = `${baseUrl}/api/copy/trade`;
            copyTradingEndpointSystemElement.textContent = copyTradingEndpoint;
        } catch (e) {
            copyTradingEndpointSystemElement.textContent = 'Error: Invalid URL';
        }
    }

    /**
     * Render webhook accounts table
     * @param {Array} serverAccounts - All server accounts for status lookup
     */
    renderAccountsTable(serverAccounts = []) {
        const tbody = document.querySelector('#page-webhook .accounts-table tbody');
        if (!tbody) return;

        const webhookAccounts = this.webhookManager.getAccounts();

        if (!webhookAccounts.length) {
            tbody.innerHTML = `
                <tr class="no-data">
                    <td colspan="6">
                        <div class="no-data-message">
                            <i class="fas fa-inbox"></i>
                            <p>No webhook accounts. Use "Add from Server" to add.</p>
                        </div>
                    </td>
                </tr>`;
            return;
        }

        tbody.innerHTML = webhookAccounts.map(webhookAccount => {
            const accNumber = webhookAccount.account || webhookAccount.id || '';

            // Find matching server account for current status
            const serverAccount = serverAccounts.find(a => String(a.account) === String(accNumber));

            // Use server data if available, otherwise use webhook data
            const status = serverAccount?.status || 'Unknown';
            const pid = serverAccount?.pid || '-';
            const created = serverAccount?.created || webhookAccount.created || '-';
            const nickname = serverAccount?.nickname || webhookAccount.nickname || '-';

            const statusClass = status.toLowerCase();
            const createdDate = created !== '-' ? new Date(created).toLocaleString() : '-';

            return `
                <tr data-account="${this.escapeHtml(accNumber)}">
                    <td>
                        <span class="status-badge ${this.escapeHtml(statusClass)}">
                            <i class="fas fa-circle"></i>
                            ${this.escapeHtml(status)}
                        </span>
                    </td>
                    <td><strong>${this.escapeHtml(accNumber)}</strong></td>
                    <td>${this.escapeHtml(nickname)}</td>
                    <td>${this.escapeHtml(pid)}</td>
                    <td title="${this.escapeHtml(createdDate)}">${this.formatDate(created)}</td>
                    <td>
                        <div class="action-buttons">
                            <button class="btn btn-secondary btn-sm" 
                                    onclick="window.WebhookUI.removeAccount('${this.escapeHtml(accNumber)}')" 
                                    title="Remove from Webhook">
                                <i class="fas fa-trash"></i>
                            </button>
                        </div>
                    </td>
                </tr>`;
        }).join('');
    }

    /**
     * Update webhook statistics
     */
    updateStats() {
        const webhookAccounts = this.webhookManager.getAccounts();
        const total = webhookAccounts.length;

        // Count online accounts (this would need server account data)
        const online = webhookAccounts.filter(acc => acc.status === 'Online').length;
        const offline = total - online;

        const totalEl = document.getElementById('totalAccounts');
        const onlineEl = document.getElementById('onlineAccounts');
        const offlineEl = document.getElementById('offlineAccounts');
        const statusEl = document.getElementById('serverStatus');

        if (totalEl) totalEl.textContent = total;
        if (onlineEl) onlineEl.textContent = online;
        if (offlineEl) offlineEl.textContent = offline;
        if (statusEl) {
            statusEl.className = 'status-dot ' + (online > 0 ? 'online' : 'offline');
            statusEl.textContent = online > 0 ? 'Online' : 'Offline';
        }
    }

    /**
     * Show account selection modal for webhook
     * @param {Array} availableAccounts - Accounts not in webhook
     */
    showAccountSelectionModal(availableAccounts) {
        if (!availableAccounts || availableAccounts.length === 0) {
            if (window.app && window.app.showToast) {
                window.app.showToast('All accounts are already added to webhook', 'info');
            }
            return;
        }

        // Use app's showModal if available
        if (window.app && window.app.showModal) {
            const accountList = availableAccounts.map(acc =>
                `<li data-account="${acc.account}">${acc.account} - ${acc.nickname || 'No nickname'}</li>`
            ).join('');

            window.app.showModal(
                'Add Account to Webhook',
                `<ul class="account-selection-list">${accountList}</ul>`,
                () => {
                    // Handle account selection
                    const selected = document.querySelector('.account-selection-list li.selected');
                    if (selected) {
                        const accountNumber = selected.dataset.account;
                        const account = availableAccounts.find(a => a.account === accountNumber);
                        if (account) {
                            this.addAccount(account);
                        }
                    }
                },
                'Add'
            );
        }
    }

    /**
     * Add account to webhook
     * @param {Object} account - Account to add
     */
    async addAccount(account) {
        const success = await this.webhookManager.addAccount(account);

        if (success) {
            if (window.app && window.app.showToast) {
                window.app.showToast('Account added to webhook', 'success');
            }

            // Refresh display
            if (window.app && window.app.loadData) {
                window.app.loadData();
            }
        } else {
            if (window.app && window.app.showToast) {
                window.app.showToast('Failed to add account to webhook', 'error');
            }
        }
    }

    /**
     * Remove account from webhook
     * @param {string} accountNumber - Account number
     */
    async removeAccount(accountNumber) {
        if (!confirm(`Remove account ${accountNumber} from webhook?`)) {
            return;
        }

        const success = await this.webhookManager.removeAccount(accountNumber);

        if (success) {
            if (window.app && window.app.showToast) {
                window.app.showToast('Account removed from webhook', 'success');
            }

            // Refresh display
            if (window.app && window.app.loadData) {
                window.app.loadData();
            }
        } else {
            if (window.app && window.app.showToast) {
                window.app.showToast('Failed to remove account', 'error');
            }
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
     * Format date
     * @param {string|Date} date - Date to format
     * @returns {string} Formatted date
     */
    formatDate(date) {
        if (window.Utils && window.Utils.formatDate) {
            return window.Utils.formatDate(date);
        }
        if (!date || date === '-') return '-';
        try {
            return new Date(date).toLocaleString();
        } catch (e) {
            return '-';
        }
    }

    /**
     * Copy webhook URL to clipboard
     */
    async copyWebhookUrl() {
        await this.webhookManager.copyWebhookUrl();
    }

    /**
     * Copy copy trading endpoint to clipboard
     */
    async copyCopyTradingEndpoint() {
        try {
            const webhookUrl = this.webhookManager.getWebhookUrl();
            let baseUrl = '';

            if (webhookUrl) {
                const url = new URL(webhookUrl);
                baseUrl = `${url.protocol}//${url.host}`;
            } else {
                baseUrl = `${window.location.protocol}//${window.location.host}`;
            }

            const copyTradingEndpoint = `${baseUrl}/api/copy/trade`;

            if (window.Utils && window.Utils.copyToClipboard) {
                window.Utils.copyToClipboard(
                    copyTradingEndpoint,
                    'Copy Trading Endpoint copied to clipboard!',
                    window.app ? window.app.showToast.bind(window.app) : null
                );
            }
        } catch (error) {
            console.error('Failed to copy endpoint:', error);
            if (window.app && window.app.showToast) {
                window.app.showToast('Failed to copy endpoint', 'error');
            }
        }
    }
}

// Create singleton instance
window.WebhookUI = new WebhookUI();

// Export class
window.WebhookUIClass = WebhookUI;

