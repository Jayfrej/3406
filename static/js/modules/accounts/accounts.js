/**
 * Accounts Module
 *
 * Manages MT5 trading accounts:
 * - Load/list accounts from server
 * - Add/delete accounts
 * - Pause/resume accounts
 * - Account status tracking
 */

class AccountManager {
    constructor() {
        this.accounts = [];
    }

    /**
     * Load all accounts from server
     * @returns {Promise<Array>} List of accounts
     */
    async loadAccounts() {
        try {
            const response = await window.API.get('/accounts');

            if (response.ok) {
                const data = await response.json();
                this.accounts = data.accounts || [];
                console.log('[ACCOUNTS] Loaded accounts:', this.accounts.length);
                return this.accounts;
            } else {
                console.warn('[ACCOUNTS] Failed to load accounts:', response.status);
                return [];
            }
        } catch (error) {
            console.error('[ACCOUNTS] Error loading accounts:', error);
            return [];
        }
    }

    /**
     * Add new account
     * @param {string} account - Account number
     * @param {string} nickname - Account nickname
     * @returns {Promise<Object>} Response with success status and message
     */
    async addAccount(account, nickname = '') {
        try {
            account = String(account || '').trim();
            nickname = String(nickname || '').trim();

            if (!account) {
                return { success: false, error: 'Account number is required' };
            }

            const response = await window.API.post('/accounts', {
                account,
                nickname
            });

            const data = await response.json();

            if (response.ok) {
                console.log('[ACCOUNTS] Account added:', account);
                // Reload accounts to get updated list
                await this.loadAccounts();
                return { success: true, message: 'Account added successfully', data };
            } else {
                return { success: false, error: data.error || 'Failed to add account' };
            }
        } catch (error) {
            console.error('[ACCOUNTS] Error adding account:', error);
            return { success: false, error: 'Failed to add account' };
        }
    }

    /**
     * Delete account
     * @param {string} accountNumber - Account number to delete
     * @returns {Promise<Object>} Response with success status and deleted pairs count
     */
    async deleteAccount(accountNumber) {
        try {
            const response = await window.API.delete(`/accounts/${accountNumber}`);
            const data = await response.json();

            if (response.ok) {
                console.log('[ACCOUNTS] Account deleted:', accountNumber);
                // Remove from local list
                this.accounts = this.accounts.filter(a => a.account !== accountNumber);

                return {
                    success: true,
                    message: 'Account deleted successfully',
                    deletedPairs: data.deleted_pairs || 0
                };
            } else {
                return { success: false, error: data.error || 'Failed to delete account' };
            }
        } catch (error) {
            console.error('[ACCOUNTS] Error deleting account:', error);
            return { success: false, error: 'Failed to delete account' };
        }
    }

    /**
     * Pause account
     * @param {string} accountNumber - Account number to pause
     * @returns {Promise<Object>} Response with success status
     */
    async pauseAccount(accountNumber) {
        try {
            const response = await window.API.post(`/accounts/${accountNumber}/pause`, {});
            const data = await response.json();

            if (response.ok) {
                console.log('[ACCOUNTS] Account paused:', accountNumber);
                // Update local account status
                const account = this.accounts.find(a => a.account === accountNumber);
                if (account) {
                    account.status = 'PAUSE';
                }
                return { success: true, message: 'Account paused successfully' };
            } else {
                return { success: false, error: data.error || 'Failed to pause account' };
            }
        } catch (error) {
            console.error('[ACCOUNTS] Error pausing account:', error);
            return { success: false, error: 'Failed to pause account' };
        }
    }

    /**
     * Resume account
     * @param {string} accountNumber - Account number to resume
     * @returns {Promise<Object>} Response with success status
     */
    async resumeAccount(accountNumber) {
        try {
            const response = await window.API.post(`/accounts/${accountNumber}/resume`, {});
            const data = await response.json();

            if (response.ok) {
                console.log('[ACCOUNTS] Account resumed:', accountNumber);
                // Update local account status
                const account = this.accounts.find(a => a.account === accountNumber);
                if (account) {
                    account.status = 'Online';
                }
                return { success: true, message: 'Account resumed successfully' };
            } else {
                return { success: false, error: data.error || 'Failed to resume account' };
            }
        } catch (error) {
            console.error('[ACCOUNTS] Error resuming account:', error);
            return { success: false, error: 'Failed to resume account' };
        }
    }

    /**
     * Restart account (for local instances)
     * @param {string} accountNumber - Account number to restart
     * @returns {Promise<Object>} Response with success status
     */
    async restartAccount(accountNumber) {
        try {
            const response = await window.API.post(`/accounts/${accountNumber}/restart`, {});
            const data = await response.json();

            if (response.ok) {
                console.log('[ACCOUNTS] Account restarted:', accountNumber);
                return { success: true, message: 'Account restarted successfully' };
            } else {
                return { success: false, error: data.error || 'Failed to restart account' };
            }
        } catch (error) {
            console.error('[ACCOUNTS] Error restarting account:', error);
            return { success: false, error: 'Failed to restart account' };
        }
    }

    /**
     * Stop account (for local instances)
     * @param {string} accountNumber - Account number to stop
     * @returns {Promise<Object>} Response with success status
     */
    async stopAccount(accountNumber) {
        try {
            const response = await window.API.post(`/accounts/${accountNumber}/stop`, {});
            const data = await response.json();

            if (response.ok) {
                console.log('[ACCOUNTS] Account stopped:', accountNumber);
                return { success: true, message: 'Account stopped successfully' };
            } else {
                return { success: false, error: data.error || 'Failed to stop account' };
            }
        } catch (error) {
            console.error('[ACCOUNTS] Error stopping account:', error);
            return { success: false, error: 'Failed to stop account' };
        }
    }

    /**
     * Open account terminal (for local instances)
     * @param {string} accountNumber - Account number
     * @returns {Promise<Object>} Response with success status
     */
    async openAccountTerminal(accountNumber) {
        try {
            const response = await window.API.post(`/accounts/${accountNumber}/open`, {});
            const data = await response.json();

            if (response.ok) {
                console.log('[ACCOUNTS] Account terminal opened:', accountNumber);
                return { success: true, message: 'Terminal opened successfully' };
            } else {
                return { success: false, error: data.error || 'Failed to open terminal' };
            }
        } catch (error) {
            console.error('[ACCOUNTS] Error opening terminal:', error);
            return { success: false, error: 'Failed to open terminal' };
        }
    }

    /**
     * Get all accounts
     * @returns {Array} List of accounts
     */
    getAccounts() {
        return [...this.accounts];
    }

    /**
     * Get account by number
     * @param {string} accountNumber - Account number
     * @returns {Object|null} Account object or null
     */
    getAccount(accountNumber) {
        return this.accounts.find(a => a.account === accountNumber) || null;
    }

    /**
     * Get account statistics
     * @returns {Object} Stats object with total, online, offline counts
     */
    getStats() {
        const total = this.accounts.length;
        const online = this.accounts.filter(acc => acc.status === 'Online').length;
        const offline = total - online;
        const paused = this.accounts.filter(acc => acc.status === 'PAUSE').length;

        return { total, online, offline, paused };
    }

    /**
     * Filter accounts by search term
     * @param {string} searchTerm - Search term
     * @returns {Array} Filtered accounts
     */
    filterAccounts(searchTerm) {
        if (!searchTerm) return this.getAccounts();

        const term = String(searchTerm).toLowerCase();
        return this.accounts.filter(account => {
            const accountText = `${account.account} ${account.nickname || ''} ${account.broker || ''} ${account.status || ''}`.toLowerCase();
            return accountText.includes(term);
        });
    }

    /**
     * Check if account exists
     * @param {string} accountNumber - Account number
     * @returns {boolean} True if account exists
     */
    hasAccount(accountNumber) {
        return this.accounts.some(a => a.account === accountNumber);
    }

    /**
     * Get online accounts
     * @returns {Array} Online accounts
     */
    getOnlineAccounts() {
        return this.accounts.filter(a => a.status === 'Online');
    }

    /**
     * Get offline accounts
     * @returns {Array} Offline accounts
     */
    getOfflineAccounts() {
        return this.accounts.filter(a => a.status !== 'Online');
    }

    /**
     * Get paused accounts
     * @returns {Array} Paused accounts
     */
    getPausedAccounts() {
        return this.accounts.filter(a => a.status === 'PAUSE');
    }
}

// Create singleton instance
window.AccountManager = new AccountManager();

// Export class
window.AccountManagerClass = AccountManager;

