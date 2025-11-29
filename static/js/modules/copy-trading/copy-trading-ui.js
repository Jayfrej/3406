/**
 * Copy Trading UI Module
 *
 * Handles copy trading UI rendering and interactions:
 * - Render copy pairs table
 * - Render master/slave accounts
 * - Render copy history
 * - Handle user actions
 * - Display modals and forms
 */

class CopyTradingUI {
    constructor() {
        this.manager = window.CopyTradingManager;
    }

    /**
     * Render all copy trading UI elements
     */
    renderAll() {
        this.renderCopyPairs();
        this.renderMasterAccounts();
        this.renderSlaveAccounts();
        this.renderCopyHistory();
        this.updatePairCount();
    }

    /**
     * Render copy pairs table
     */
    renderCopyPairs() {
        const container = document.getElementById('activePairsContainer');
        if (!container) return;

        const pairs = this.manager.getCopyPairs();

        if (!pairs.length) {
            container.innerHTML = `
                <div class="no-data-message">
                    <i class="fas fa-inbox"></i>
                    <p>No copy trading pairs configured.</p>
                </div>`;
            return;
        }

        container.innerHTML = pairs.map(pair => {
            const statusClass = (pair.status || 'active').toLowerCase();
            const masterNickname = pair.master_nickname || pair.masterNickname || '';
            const slaveNickname = pair.slave_nickname || pair.slaveNickname || '';

            return `
                <div class="pair-card">
                    <div class="pair-header">
                        <span class="status-badge ${this.escapeHtml(statusClass)}">
                            ${this.escapeHtml(pair.status || 'Active')}
                        </span>
                        <div class="pair-actions">
                            <button class="btn-icon" onclick="window.CopyTradingUI.editPair('${pair.id}')" title="Edit">
                                <i class="fas fa-edit"></i>
                            </button>
                            <button class="btn-icon" onclick="window.CopyTradingUI.deletePair('${pair.id}')" title="Delete">
                                <i class="fas fa-trash"></i>
                            </button>
                        </div>
                    </div>
                    <div class="pair-body">
                        <div class="pair-flow">
                            <div class="account-box master">
                                <span class="label">Master</span>
                                <strong>${this.escapeHtml(pair.master_account || pair.masterAccount)}</strong>
                                ${masterNickname ? `<small>${this.escapeHtml(masterNickname)}</small>` : ''}
                            </div>
                            <div class="flow-arrow">
                                <i class="fas fa-arrow-right"></i>
                            </div>
                            <div class="account-box slave">
                                <span class="label">Slave</span>
                                <strong>${this.escapeHtml(pair.slave_account || pair.slaveAccount)}</strong>
                                ${slaveNickname ? `<small>${this.escapeHtml(slaveNickname)}</small>` : ''}
                            </div>
                        </div>
                        <div class="pair-settings">
                            <div><strong>Volume Mode:</strong> ${this.escapeHtml(pair.settings?.volume_mode || pair.settings?.volumeMode || 'multiply')}</div>
                            <div><strong>Multiplier:</strong> ${pair.settings?.multiplier || 2}x</div>
                            ${pair.settings?.copyPSL !== false ? '<div><i class="fas fa-check"></i> Copy P/SL</div>' : ''}
                        </div>
                    </div>
                </div>`;
        }).join('');
    }

    /**
     * Render master accounts
     */
    renderMasterAccounts() {
        const container = document.getElementById('masterAccountsContainer');
        if (!container) return;

        const masters = this.manager.getMasterAccounts();

        if (!masters.length) {
            container.innerHTML = `
                <div class="no-data-message">
                    <i class="fas fa-inbox"></i>
                    <p>No master accounts added.</p>
                </div>`;
            return;
        }

        container.innerHTML = masters.map(master => `
            <div class="account-card">
                <div class="account-info">
                    <strong>${this.escapeHtml(master.accountNumber)}</strong>
                    ${master.nickname ? `<small>${this.escapeHtml(master.nickname)}</small>` : ''}
                </div>
                <button class="btn btn-sm btn-secondary" 
                        onclick="window.CopyTradingUI.removeMasterAccount('${this.escapeHtml(master.id || master.accountNumber)}')"
                        title="Remove">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        `).join('');
    }

    /**
     * Render slave accounts
     */
    renderSlaveAccounts() {
        const container = document.getElementById('slaveAccountsContainer');
        if (!container) return;

        const slaves = this.manager.getSlaveAccounts();

        if (!slaves.length) {
            container.innerHTML = `
                <div class="no-data-message">
                    <i class="fas fa-inbox"></i>
                    <p>No slave accounts added.</p>
                </div>`;
            return;
        }

        container.innerHTML = slaves.map(slave => `
            <div class="account-card">
                <div class="account-info">
                    <strong>${this.escapeHtml(slave.accountNumber)}</strong>
                    ${slave.nickname ? `<small>${this.escapeHtml(slave.nickname)}</small>` : ''}
                </div>
                <button class="btn btn-sm btn-secondary" 
                        onclick="window.CopyTradingUI.removeSlaveAccount('${this.escapeHtml(slave.id || slave.accountNumber)}')"
                        title="Remove">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        `).join('');
    }

    /**
     * Render copy history table
     */
    renderCopyHistory() {
        const tbody = document.getElementById('copyHistoryTableBody');
        if (!tbody) return;

        // Get filters
        const statusFilter = document.getElementById('copyHistoryFilter')?.value || 'all';
        const accountFilter = document.getElementById('copyAccountFilter')?.value || 'all';

        const filtered = this.manager.filterCopyHistory({
            status: statusFilter,
            account: accountFilter
        });

        if (!filtered.length) {
            tbody.innerHTML = `
                <tr class="no-data">
                    <td colspan="7">
                        <div class="no-data-message">
                            <i class="fas fa-inbox"></i>
                            <p>No copy trading history.</p>
                        </div>
                    </td>
                </tr>`;
            return;
        }

        tbody.innerHTML = filtered.map(item => {
            const statusClass = item.status === 'success' ? 'success' : 'error';
            const timestamp = item.timestamp ? new Date(item.timestamp).toLocaleString() : '-';

            return `
                <tr class="copy-history-row ${statusClass}">
                    <td>
                        <span class="status-badge ${statusClass}">
                            ${item.status === 'success' 
                                ? '<i class="fas fa-check"></i>' 
                                : '<i class="fas fa-times"></i>'}
                            ${this.escapeHtml(item.status)}
                        </span>
                    </td>
                    <td><strong>${this.escapeHtml(item.master)}</strong></td>
                    <td><strong>${this.escapeHtml(item.slave)}</strong></td>
                    <td>${this.escapeHtml(item.action)}</td>
                    <td>${this.escapeHtml(item.symbol)}</td>
                    <td>${item.volume || '-'}</td>
                    <td title="${timestamp}">${this.formatRelativeTime(item.timestamp)}</td>
                </tr>`;
        }).join('');
    }

    /**
     * Update pair count display
     */
    updatePairCount() {
        const stats = this.manager.getStats();

        const totalEl = document.getElementById('totalPairs');
        const activeEl = document.getElementById('activePairs');
        const mastersEl = document.getElementById('totalMasters');
        const slavesEl = document.getElementById('totalSlaves');

        if (totalEl) totalEl.textContent = stats.totalPairs;
        if (activeEl) activeEl.textContent = stats.activePairs;
        if (mastersEl) mastersEl.textContent = stats.totalMasters;
        if (slavesEl) slavesEl.textContent = stats.totalSlaves;
    }

    /**
     * Add master account
     * @param {string} formId - Form element ID
     * @returns {Promise<void>}
     */
    async addMasterAccount(formId = 'addMasterForm') {
        const form = document.getElementById(formId);
        if (!form) return;

        const accountNumber = form.querySelector('[name="accountNumber"]')?.value?.trim();
        const nickname = form.querySelector('[name="nickname"]')?.value?.trim();

        if (!accountNumber) {
            this.showToast('Please enter master account number', 'warning');
            return;
        }

        this.showLoading();

        try {
            const result = await this.manager.addMasterAccount({
                accountNumber,
                nickname
            });

            if (result.success) {
                this.showToast('Master account added successfully', 'success');
                form.reset();
                this.renderMasterAccounts();
                this.updatePairCount();
            } else {
                this.showToast(result.error || 'Failed to add master account', 'error');
            }
        } catch (error) {
            console.error('Add master account error:', error);
            this.showToast('Failed to add master account', 'error');
        } finally {
            this.hideLoading();
        }
    }

    /**
     * Add slave account
     * @param {string} formId - Form element ID
     * @returns {Promise<void>}
     */
    async addSlaveAccount(formId = 'addSlaveForm') {
        const form = document.getElementById(formId);
        if (!form) return;

        const accountNumber = form.querySelector('[name="accountNumber"]')?.value?.trim();
        const nickname = form.querySelector('[name="nickname"]')?.value?.trim();

        if (!accountNumber) {
            this.showToast('Please enter slave account number', 'warning');
            return;
        }

        this.showLoading();

        try {
            const result = await this.manager.addSlaveAccount({
                accountNumber,
                nickname
            });

            if (result.success) {
                this.showToast('Slave account added successfully', 'success');
                form.reset();
                this.renderSlaveAccounts();
                this.updatePairCount();
            } else {
                this.showToast(result.error || 'Failed to add slave account', 'error');
            }
        } catch (error) {
            console.error('Add slave account error:', error);
            this.showToast('Failed to add slave account', 'error');
        } finally {
            this.hideLoading();
        }
    }

    /**
     * Remove master account
     * @param {string} accountId - Account ID
     * @returns {Promise<void>}
     */
    async removeMasterAccount(accountId) {
        const confirmed = await this.showConfirmDialog(
            'Remove Master Account',
            'Remove this account from Copy Trading? This cannot be undone.'
        );
        if (!confirmed) return;

        this.showLoading();

        try {
            const result = await this.manager.deleteMasterAccount(accountId);

            if (result.success) {
                this.showToast('Master account removed successfully', 'success');
                this.renderMasterAccounts();
                this.updatePairCount();
            } else {
                this.showToast(result.error || 'Failed to remove master account', 'error');
            }
        } catch (error) {
            console.error('Remove master account error:', error);
            this.showToast('Failed to remove master account', 'error');
        } finally {
            this.hideLoading();
        }
    }

    /**
     * Remove slave account
     * @param {string} accountId - Account ID
     * @returns {Promise<void>}
     */
    async removeSlaveAccount(accountId) {
        const confirmed = await this.showConfirmDialog(
            'Remove Slave Account',
            'Remove this account from Copy Trading? This cannot be undone.'
        );
        if (!confirmed) return;

        this.showLoading();

        try {
            const result = await this.manager.deleteSlaveAccount(accountId);

            if (result.success) {
                this.showToast('Slave account removed successfully', 'success');
                this.renderSlaveAccounts();
                this.updatePairCount();
            } else {
                this.showToast(result.error || 'Failed to remove slave account', 'error');
            }
        } catch (error) {
            console.error('Remove slave account error:', error);
            this.showToast('Failed to remove slave account', 'error');
        } finally {
            this.hideLoading();
        }
    }

    /**
     * Edit copy pair (placeholder - implement as needed)
     * @param {string} pairId - Pair ID
     */
    editPair(pairId) {
        this.showToast('Edit pair feature - implement as needed', 'info');
        // TODO: Implement edit pair modal
    }

    /**
     * Delete copy pair (placeholder - implement as needed)
     * @param {string} pairId - Pair ID
     */
    async deletePair(pairId) {
        const confirmed = await this.showConfirmDialog(
            'Delete Copy Pair',
            'Delete this copy trading pair? This cannot be undone.'
        );
        if (!confirmed) return;

        this.showToast('Delete pair feature - implement as needed', 'info');
        // TODO: Implement delete pair API call
    }

    /**
     * Copy copy trading endpoint to clipboard
     */
    async copyCopyTradingEndpoint() {
        try {
            const webhookUrl = window.WebhookManager ? window.WebhookManager.getWebhookUrl() : '';
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
                    this.showToast.bind(this)
                );
            }
        } catch (error) {
            console.error('Failed to copy endpoint:', error);
            this.showToast('Failed to copy endpoint', 'error');
        }
    }

    /**
     * Refresh all copy trading data
     * @returns {Promise<void>}
     */
    async refresh() {
        this.showLoading();

        try {
            await Promise.all([
                this.manager.loadCopyPairs(),
                this.manager.loadMasterAccounts(),
                this.manager.loadSlaveAccounts(),
                this.manager.loadCopyHistory()
            ]);

            this.renderAll();
        } catch (error) {
            console.error('Refresh error:', error);
            this.showToast('Failed to refresh data', 'error');
        } finally {
            this.hideLoading();
        }
    }

    /**
     * Format relative time
     * @param {string} timestamp - Timestamp
     * @returns {string} Relative time
     */
    formatRelativeTime(timestamp) {
        if (window.Utils && window.Utils.formatRelativeTime) {
            return window.Utils.formatRelativeTime(timestamp);
        }
        return timestamp ? new Date(timestamp).toLocaleString() : '-';
    }

    /**
     * Escape HTML
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
     * Show confirmation dialog
     * @param {string} title - Dialog title
     * @param {string} message - Dialog message
     * @returns {Promise<boolean>} True if confirmed
     */
    async showConfirmDialog(title, message) {
        if (window.app && window.app.showConfirmDialog) {
            return await window.app.showConfirmDialog(title, message);
        }
        return confirm(message);
    }

    /**
     * Show toast notification
     * @param {string} message - Message
     * @param {string} type - Toast type
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
window.CopyTradingUI = new CopyTradingUI();

// Export class
window.CopyTradingUIClass = CopyTradingUI;

