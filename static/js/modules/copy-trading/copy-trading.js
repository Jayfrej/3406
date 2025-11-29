/**
 * Copy Trading Module
 *
 * Manages copy trading operations:
 * - Load/manage copy pairs
 * - Master/Slave account management
 * - Copy history tracking
 * - Real-time event subscription
 */

class CopyTradingManager {
    constructor() {
        this.copyPairs = [];
        this.copyHistory = [];
        this.masterAccounts = [];
        this.slaveAccounts = [];
        this.plans = []; // Legacy format for UI compatibility
        this._copyEs = null; // EventSource for real-time updates
        this.copyHistoryInterval = null;
    }

    /**
     * Load all copy pairs from server
     * @returns {Promise<Array>} List of copy pairs
     */
    async loadCopyPairs() {
        try {
            const response = await window.API.get('/api/pairs');

            if (!response.ok) {
                throw new Error('Failed to load pairs');
            }

            const data = await response.json();
            this.copyPairs = Array.isArray(data.pairs) ? data.pairs : [];

            // Sync with plans format for UI compatibility
            this.plans = this.copyPairs.map(pair => ({
                id: pair.id,
                masterAccount: pair.master_account || pair.masterAccount,
                slaveAccount: pair.slave_account || pair.slaveAccount,
                masterNickname: pair.master_nickname || pair.masterNickname || '',
                slaveNickname: pair.slave_nickname || pair.slaveNickname || '',
                apiToken: pair.api_key || pair.apiKey,
                status: pair.status || 'active',
                settings: {
                    autoMapSymbol: pair.settings?.auto_map_symbol ?? pair.settings?.autoMapSymbol ?? true,
                    autoMapVolume: pair.settings?.auto_map_volume ?? pair.settings?.autoMapVolume ?? true,
                    copyPSL: pair.settings?.copy_psl ?? pair.settings?.copyPSL ?? true,
                    volumeMode: pair.settings?.volume_mode || pair.settings?.volumeMode || 'multiply',
                    multiplier: pair.settings?.multiplier || 2
                }
            }));

            // Auto-cleanup deleted accounts
            await this.cleanupDeletedAccounts();

            console.log('[COPY_TRADING] Loaded pairs:', this.copyPairs.length);
            return this.copyPairs;
        } catch (error) {
            console.error('[COPY_TRADING] Error loading pairs:', error);
            return [];
        }
    }

    /**
     * Load copy history from server
     * @param {number} limit - Number of records to load
     * @returns {Promise<Array>} Copy history
     */
    async loadCopyHistory(limit = 100) {
        try {
            const response = await window.API.get(`/api/copy/history?limit=${limit}`);

            if (!response.ok) {
                throw new Error('Failed to load history');
            }

            const data = await response.json();
            this.copyHistory = Array.isArray(data.history) ? data.history : [];

            console.log('[COPY_TRADING] Loaded history:', this.copyHistory.length);
            return this.copyHistory;
        } catch (error) {
            console.error('[COPY_TRADING] Error loading history:', error);
            return [];
        }
    }

    /**
     * Cleanup deleted accounts from master/slave lists
     * @returns {Promise<void>}
     */
    async cleanupDeletedAccounts() {
        try {
            // Load server accounts
            const response = await window.API.get('/accounts');
            if (!response.ok) return;

            const data = await response.json();
            const serverAccountNumbers = new Set(
                (data.accounts || []).map(a => String(a.account))
            );

            // Check master accounts
            let masterChanged = false;
            const validMasters = this.masterAccounts.filter(m => {
                const exists = serverAccountNumbers.has(String(m.accountNumber));
                if (!exists) {
                    console.log(`[CLEANUP] Removing deleted master account: ${m.accountNumber}`);
                    masterChanged = true;
                }
                return exists;
            });

            if (masterChanged) {
                this.masterAccounts = validMasters;
            }

            // Check slave accounts
            let slaveChanged = false;
            const validSlaves = this.slaveAccounts.filter(s => {
                const exists = serverAccountNumbers.has(String(s.accountNumber));
                if (!exists) {
                    console.log(`[CLEANUP] Removing deleted slave account: ${s.accountNumber}`);
                    slaveChanged = true;
                }
                return exists;
            });

            if (slaveChanged) {
                this.slaveAccounts = validSlaves;
            }

            if (masterChanged || slaveChanged) {
                console.log('[CLEANUP] Removed deleted accounts from copy trading');
            }

        } catch (error) {
            console.error('[CLEANUP] Error during account cleanup:', error);
        }
    }

    /**
     * Load master accounts from server
     * @returns {Promise<Array>} Master accounts
     */
    async loadMasterAccounts() {
        try {
            const response = await window.API.get('/api/copy/master-accounts');

            if (!response.ok) {
                throw new Error('Failed to fetch master accounts');
            }

            const data = await response.json();
            this.masterAccounts = Array.isArray(data.accounts)
                ? data.accounts.map(acc => ({
                    id: acc.id,
                    accountNumber: acc.account,
                    nickname: acc.nickname || ''
                }))
                : [];

            console.log('[COPY_TRADING] Loaded master accounts:', this.masterAccounts.length);
            return this.masterAccounts;
        } catch (error) {
            console.error('[COPY_TRADING] Error loading master accounts:', error);
            this.masterAccounts = [];
            return [];
        }
    }

    /**
     * Load slave accounts from server
     * @returns {Promise<Array>} Slave accounts
     */
    async loadSlaveAccounts() {
        try {
            const response = await window.API.get('/api/copy/slave-accounts');

            if (!response.ok) {
                throw new Error('Failed to fetch slave accounts');
            }

            const data = await response.json();
            this.slaveAccounts = Array.isArray(data.accounts)
                ? data.accounts.map(acc => ({
                    id: acc.id,
                    accountNumber: acc.account,
                    nickname: acc.nickname || ''
                }))
                : [];

            console.log('[COPY_TRADING] Loaded slave accounts:', this.slaveAccounts.length);
            return this.slaveAccounts;
        } catch (error) {
            console.error('[COPY_TRADING] Error loading slave accounts:', error);
            this.slaveAccounts = [];
            return [];
        }
    }

    /**
     * Add master account
     * @param {Object} account - Account data {accountNumber, nickname}
     * @returns {Promise<Object>} Result with success status
     */
    async addMasterAccount(account) {
        try {
            const response = await window.API.post('/api/copy/master-accounts', {
                account: account.accountNumber || account.account,
                nickname: account.nickname || ''
            });

            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.error || 'Failed to save master account');
            }

            const data = await response.json();
            const savedAccount = data.account;

            // Add to local array
            this.masterAccounts.push({
                id: savedAccount.id,
                accountNumber: savedAccount.account,
                nickname: savedAccount.nickname || ''
            });

            console.log('[COPY_TRADING] Master account added:', savedAccount.account);
            return { success: true, account: savedAccount };

        } catch (error) {
            console.error('[COPY_TRADING] Error adding master account:', error);
            return { success: false, error: error.message };
        }
    }

    /**
     * Add slave account
     * @param {Object} account - Account data {accountNumber, nickname}
     * @returns {Promise<Object>} Result with success status
     */
    async addSlaveAccount(account) {
        try {
            const response = await window.API.post('/api/copy/slave-accounts', {
                account: account.accountNumber || account.account,
                nickname: account.nickname || ''
            });

            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.error || 'Failed to save slave account');
            }

            const data = await response.json();
            const savedAccount = data.account;

            // Add to local array
            this.slaveAccounts.push({
                id: savedAccount.id,
                accountNumber: savedAccount.account,
                nickname: savedAccount.nickname || ''
            });

            console.log('[COPY_TRADING] Slave account added:', savedAccount.account);
            return { success: true, account: savedAccount };

        } catch (error) {
            console.error('[COPY_TRADING] Error adding slave account:', error);
            return { success: false, error: error.message };
        }
    }

    /**
     * Delete master account
     * @param {string} accountId - Account ID
     * @returns {Promise<Object>} Result with success status
     */
    async deleteMasterAccount(accountId) {
        try {
            const response = await window.API.delete(`/api/copy/master-accounts/${accountId}`);

            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.error || 'Failed to delete master account');
            }

            // Remove from local array
            this.masterAccounts = this.masterAccounts.filter(a =>
                a.id !== accountId && a.accountNumber !== accountId
            );

            console.log('[COPY_TRADING] Master account deleted:', accountId);
            return { success: true };

        } catch (error) {
            console.error('[COPY_TRADING] Error deleting master account:', error);
            return { success: false, error: error.message };
        }
    }

    /**
     * Delete slave account
     * @param {string} accountId - Account ID
     * @returns {Promise<Object>} Result with success status
     */
    async deleteSlaveAccount(accountId) {
        try {
            const response = await window.API.delete(`/api/copy/slave-accounts/${accountId}`);

            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.error || 'Failed to delete slave account');
            }

            // Remove from local array
            this.slaveAccounts = this.slaveAccounts.filter(a =>
                a.id !== accountId && a.accountNumber !== accountId
            );

            console.log('[COPY_TRADING] Slave account deleted:', accountId);
            return { success: true };

        } catch (error) {
            console.error('[COPY_TRADING] Error deleting slave account:', error);
            return { success: false, error: error.message };
        }
    }

    /**
     * Subscribe to real-time copy events
     */
    subscribeCopyEvents() {
        try {
            if (this._copyEs) {
                this._copyEs.close();
            }

            const es = new EventSource('/events/copy-trades');

            es.onmessage = (evt) => {
                try {
                    const data = JSON.parse(evt.data);

                    if (data.event === 'copy_history_cleared') {
                        this.copyHistory = [];
                        return;
                    }

                    this.addCopyToHistory(data);
                } catch (e) {
                    console.warn('[COPY_TRADING] Invalid copy event:', e);
                }
            };

            this._copyEs = es;
            console.log('[COPY_TRADING] Subscribed to copy events');

        } catch (error) {
            console.warn('[COPY_TRADING] SSE unavailable:', error);
        }
    }

    /**
     * Unsubscribe from copy events
     */
    unsubscribeCopyEvents() {
        if (this._copyEs) {
            this._copyEs.close();
            this._copyEs = null;
            console.log('[COPY_TRADING] Unsubscribed from copy events');
        }
    }

    /**
     * Add copy trade to history
     * @param {Object} item - Copy trade data
     */
    addCopyToHistory(item) {
        const normalized = {
            id: item.id || String(Date.now()),
            status: (item.status || '').toLowerCase() === 'error' ? 'error' : 'success',
            master: item.master || '-',
            slave: item.slave || '-',
            action: item.action || '-',
            symbol: item.symbol || '-',
            volume: item.volume ?? '',
            price: item.price ?? '',
            reason: item.reason || '',
            timestamp: item.timestamp || new Date().toISOString()
        };

        this.copyHistory.unshift(normalized);

        // Keep only last 100 records
        if (this.copyHistory.length > 100) {
            this.copyHistory = this.copyHistory.slice(0, 100);
        }
    }

    /**
     * Setup auto-refresh for copy history
     * @param {number} interval - Refresh interval in milliseconds
     */
    setupCopyHistoryAutoRefresh(interval = 5000) {
        this.stopCopyHistoryAutoRefresh();

        this.copyHistoryInterval = setInterval(async () => {
            // Only refresh if on copy trading page
            if (window.Router && window.Router.isCurrentPage('copytrading')) {
                await this.loadCopyHistory();
            }
        }, interval);

        console.log(`[COPY_TRADING] Auto-refresh started (${interval}ms interval)`);
    }

    /**
     * Stop auto-refresh
     */
    stopCopyHistoryAutoRefresh() {
        if (this.copyHistoryInterval) {
            clearInterval(this.copyHistoryInterval);
            this.copyHistoryInterval = null;
            console.log('[COPY_TRADING] Auto-refresh stopped');
        }
    }

    /**
     * Get copy pairs
     * @returns {Array} Copy pairs
     */
    getCopyPairs() {
        return [...this.copyPairs];
    }

    /**
     * Get copy history
     * @returns {Array} Copy history
     */
    getCopyHistory() {
        return [...this.copyHistory];
    }

    /**
     * Get master accounts
     * @returns {Array} Master accounts
     */
    getMasterAccounts() {
        return [...this.masterAccounts];
    }

    /**
     * Get slave accounts
     * @returns {Array} Slave accounts
     */
    getSlaveAccounts() {
        return [...this.slaveAccounts];
    }

    /**
     * Get plans (legacy format)
     * @returns {Array} Plans
     */
    getPlans() {
        return [...this.plans];
    }

    /**
     * Filter copy history
     * @param {Object} filters - Filter criteria {status, account}
     * @returns {Array} Filtered history
     */
    filterCopyHistory(filters = {}) {
        let filtered = [...this.copyHistory];

        if (filters.status && filters.status !== 'all') {
            filtered = filtered.filter(h => h.status === filters.status);
        }

        if (filters.account && filters.account !== 'all') {
            filtered = filtered.filter(h =>
                h.master === filters.account || h.slave === filters.account
            );
        }

        return filtered;
    }

    /**
     * Get copy trading statistics
     * @returns {Object} Statistics
     */
    getStats() {
        const totalPairs = this.copyPairs.length;
        const activePairs = this.copyPairs.filter(p => p.status === 'active').length;
        const totalMasters = this.masterAccounts.length;
        const totalSlaves = this.slaveAccounts.length;

        const recentHistory = this.copyHistory.slice(0, 10);
        const successCount = recentHistory.filter(h => h.status === 'success').length;
        const errorCount = recentHistory.filter(h => h.status === 'error').length;

        return {
            totalPairs,
            activePairs,
            totalMasters,
            totalSlaves,
            recentSuccess: successCount,
            recentErrors: errorCount
        };
    }
}

// Create singleton instance
window.CopyTradingManager = new CopyTradingManager();

// Export class
window.CopyTradingManagerClass = CopyTradingManager;

