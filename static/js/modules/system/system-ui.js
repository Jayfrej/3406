/**
 * System UI Module
 *
 * Handles system information UI rendering:
 * - Display system logs
 * - Show system information
 * - Update last health check time
 */

class SystemUI {
    constructor() {
        this.manager = window.SystemManager;
    }

    /**
     * Render system logs
     */
    renderSystemLogs() {
        const container = document.getElementById('systemLogsContainer');
        if (!container) return;

        const logs = this.manager.getSystemLogs();
        const stats = this.manager.getLogStats();

        if (logs.length === 0) {
            container.innerHTML = `
                <div class="log-header">
                    <h3><i class="fas fa-history"></i> Log History</h3>
                    <span class="log-count">0 / ${stats.maxLogs} entries</span>
                </div>
                <div class="log-content">
                    <div class="log-empty">
                        <i class="fas fa-inbox"></i>
                        <p>No system logs yet</p>
                    </div>
                </div>
            `;
            return;
        }

        const logsHtml = logs.map(log => {
            const time = new Date(log.timestamp).toLocaleString('en-GB', {
                day: '2-digit',
                month: '2-digit',
                year: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            });

            const typeClass = log.type.toLowerCase();
            const typeLabel = log.type.toUpperCase();

            return `<div class="log-entry log-${typeClass}">${time} <span class="log-badge log-badge-${typeClass}">${typeLabel}</span> ${this.escapeHtml(log.message)}</div>`;
        }).join('');

        container.innerHTML = `
            <div class="log-header">
                <h3><i class="fas fa-history"></i> Log History</h3>
                <span class="log-count">${stats.total} / ${stats.maxLogs} entries</span>
            </div>
            <div class="log-content">
                ${logsHtml}
            </div>
        `;
    }

    /**
     * Update last update time display
     */
    updateLastUpdateTime() {
        const timeString = this.manager.getLastUpdateTime();
        const now = new Date();
        const fullTimeString = now.toLocaleString();

        const lastUpdateEl = document.getElementById('lastUpdate');
        const healthCheckEl = document.getElementById('lastHealthCheck');
        const healthCheckSystemEl = document.getElementById('lastHealthCheckSystem');

        if (lastUpdateEl) lastUpdateEl.textContent = timeString;
        if (healthCheckEl) healthCheckEl.textContent = fullTimeString;
        if (healthCheckSystemEl) healthCheckSystemEl.textContent = fullTimeString;
    }

    /**
     * Clear system logs
     * @returns {Promise<void>}
     */
    async clearSystemLogs() {
        const confirmed = await this.showConfirmDialog(
            'Clear System Logs',
            'Delete all system logs? This cannot be undone.'
        );
        if (!confirmed) return;

        this.showLoading();

        try {
            const result = await this.manager.clearSystemLogs();

            if (result.success) {
                this.showToast(result.message, 'success');
                this.renderSystemLogs();
            } else {
                this.showToast('Failed to clear logs', 'error');
            }
        } catch (error) {
            console.error('Clear logs error:', error);
            this.showToast('Failed to clear logs', 'error');
        } finally {
            this.hideLoading();
        }
    }

    /**
     * Load and render system logs
     * @returns {Promise<void>}
     */
    async loadAndRenderLogs() {
        this.showLoading();

        try {
            await this.manager.loadSystemLogs();
            this.renderSystemLogs();
        } catch (error) {
            console.error('Load logs error:', error);
        } finally {
            this.hideLoading();
        }
    }

    /**
     * Refresh system page
     * @returns {Promise<void>}
     */
    async refresh() {
        await this.loadAndRenderLogs();
        this.updateLastUpdateTime();

        // Update webhook display if available
        if (window.WebhookUI) {
            window.WebhookUI.displayWebhookUrl();
        }
    }

    /**
     * Initialize system page
     * @returns {Promise<void>}
     */
    async initialize() {
        await this.loadAndRenderLogs();
        this.updateLastUpdateTime();

        // Subscribe to real-time logs
        this.manager.subscribeSystemLogs();
    }

    /**
     * Cleanup system page
     */
    cleanup() {
        this.manager.unsubscribeSystemLogs();
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
window.SystemUI = new SystemUI();

// Export class
window.SystemUIClass = SystemUI;

