/**
 * Webhooks Module
 *
 * Manages webhook configuration and accounts:
 * - Fetch webhook URL from server
 * - Manage webhook accounts list
 * - Add/remove accounts from webhook
 */

class WebhookManager {
    constructor() {
        this.webhookUrl = '';
        this.webhookAccounts = [];
    }

    /**
     * Load webhook URL from server
     * @returns {Promise<string>} Webhook URL
     */
    async loadWebhookUrl() {
        try {
            const response = await window.API.get('/webhook-url');

            if (response.ok) {
                const data = await response.json();
                this.webhookUrl = data.url || '';
                console.log('[WEBHOOKS] Webhook URL loaded:', this.webhookUrl);
                return this.webhookUrl;
            } else {
                console.warn('[WEBHOOKS] Failed to load webhook URL:', response.status);
                return '';
            }
        } catch (error) {
            console.error('[WEBHOOKS] Error loading webhook URL:', error);
            return '';
        }
    }

    /**
     * Load webhook accounts from server
     * @returns {Promise<Array>} List of webhook accounts
     */
    async loadWebhookAccounts() {
        try {
            const response = await window.API.get('/webhook-accounts');

            if (response.ok) {
                const data = await response.json();
                this.webhookAccounts = Array.isArray(data.accounts) ? data.accounts : [];
                console.log('[WEBHOOKS] Loaded webhook accounts:', this.webhookAccounts.length);
            } else {
                // Fallback to localStorage
                const saved = localStorage.getItem('mt5_webhook_accounts');
                this.webhookAccounts = saved ? JSON.parse(saved) : [];
                console.log('[WEBHOOKS] Loaded from localStorage:', this.webhookAccounts.length);
            }

            return this.webhookAccounts;
        } catch (error) {
            console.error('[WEBHOOKS] Error loading webhook accounts:', error);

            // Fallback to localStorage
            const saved = localStorage.getItem('mt5_webhook_accounts');
            this.webhookAccounts = saved ? JSON.parse(saved) : [];
            return this.webhookAccounts;
        }
    }

    /**
     * Add account to webhook
     * @param {Object} account - Account data
     * @returns {Promise<boolean>} Success status
     */
    async addAccount(account) {
        try {
            const accountNumber = account.account || account.accountNumber;
            const nickname = account.nickname || '';

            const response = await window.API.post('/webhook-accounts', {
                account: accountNumber,
                nickname: nickname,
                enabled: true
            });

            if (response.ok) {
                // Add to local list if not exists
                if (!this.webhookAccounts.some(a => (a.account || a.id) === accountNumber)) {
                    this.webhookAccounts.push({
                        account: accountNumber,
                        nickname: nickname,
                        enabled: true,
                        created: new Date().toISOString()
                    });
                }

                console.log('[WEBHOOKS] Account added:', accountNumber);
                return true;
            } else {
                const data = await response.json();
                throw new Error(data.error || 'Failed to add account');
            }
        } catch (error) {
            console.error('[WEBHOOKS] Error adding account:', error);
            return false;
        }
    }

    /**
     * Remove account from webhook
     * @param {string} accountNumber - Account number to remove
     * @returns {Promise<boolean>} Success status
     */
    async removeAccount(accountNumber) {
        try {
            const response = await window.API.delete(`/webhook-accounts/${accountNumber}`);

            if (response.ok) {
                // Remove from local list
                this.webhookAccounts = this.webhookAccounts.filter(
                    a => (a.account || a.id) !== accountNumber
                );

                console.log('[WEBHOOKS] Account removed:', accountNumber);
                return true;
            } else {
                const data = await response.json();
                throw new Error(data.error || 'Failed to remove account');
            }
        } catch (error) {
            console.error('[WEBHOOKS] Error removing account:', error);
            return false;
        }
    }

    /**
     * Get webhook accounts
     * @returns {Array} List of webhook accounts
     */
    getAccounts() {
        return [...this.webhookAccounts];
    }

    /**
     * Get webhook URL
     * @returns {string} Webhook URL
     */
    getWebhookUrl() {
        return this.webhookUrl;
    }

    /**
     * Check if account is in webhook list
     * @param {string} accountNumber - Account number
     * @returns {boolean} True if account is in webhook
     */
    hasAccount(accountNumber) {
        return this.webhookAccounts.some(a => (a.account || a.id) === accountNumber);
    }

    /**
     * Get available accounts (not in webhook)
     * @param {Array} allAccounts - All available accounts
     * @returns {Array} Accounts not in webhook
     */
    getAvailableAccounts(allAccounts) {
        const webhookAccountNumbers = new Set(
            this.webhookAccounts.map(a => a.account || a.id)
        );

        return allAccounts.filter(
            acc => !webhookAccountNumbers.has(acc.account)
        );
    }

    /**
     * Copy webhook URL to clipboard
     * @returns {Promise<void>}
     */
    async copyWebhookUrl() {
        if (!this.webhookUrl) {
            if (window.app && window.app.showToast) {
                window.app.showToast('Webhook URL not available', 'warning');
            }
            return;
        }

        if (window.Utils) {
            window.Utils.copyToClipboard(
                this.webhookUrl,
                'Webhook URL copied to clipboard!',
                window.app ? window.app.showToast.bind(window.app) : null
            );
        }
    }
}

// Create singleton instance
window.WebhookManager = new WebhookManager();

// Export class
window.WebhookManagerClass = WebhookManager;

