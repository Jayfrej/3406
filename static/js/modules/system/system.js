/**
 * System Module
 *
 * Manages system information and logging:
 * - System logs management
 * - Real-time log subscription
 * - System status tracking
 */

class SystemManager {
    constructor() {
        this.systemLogs = [];
        this.maxSystemLogs = 300;
        this._systemEs = null; // EventSource for real-time logs
    }

    /**
     * Load system logs from server
     * @param {number} limit - Maximum number of logs to load
     * @returns {Promise<Array>} System logs
     */
    async loadSystemLogs(limit = 300) {
        try {
            const response = await window.API.get(`/api/system/logs?limit=${limit}`);

            if (!response.ok) {
                throw new Error('API not available');
            }

            const data = await response.json();
            this.systemLogs = Array.isArray(data.logs) ? data.logs : [];

            console.log('[SYSTEM] Loaded logs:', this.systemLogs.length);
            return this.systemLogs;

        } catch (error) {
            console.warn('[SYSTEM] Logs API not available, using demo logs');

            // Create demo logs for development/testing
            const demoLogs = [
                { type: 'info', message: 'System started successfully' },
                { type: 'success', message: 'Connected to MT5 server' },
                { type: 'info', message: 'Webhook endpoint initialized' },
                { type: 'info', message: 'Copy trading service active' },
                { type: 'success', message: 'Trade executed successfully' },
                { type: 'info', message: 'Monitoring active connections' },
                { type: 'success', message: 'Webhook received and processed' },
                { type: 'info', message: 'Checking account status' },
                { type: 'success', message: 'All accounts online' },
                { type: 'info', message: 'Health check completed' },
                { type: 'success', message: 'Copy trading pair synchronized' },
            ];

            const now = Date.now();
            this.systemLogs = demoLogs.map((log, index) => ({
                id: now + index,
                type: log.type,
                message: log.message,
                timestamp: new Date(now - (demoLogs.length - index) * 3000).toISOString()
            }));

            return this.systemLogs;
        }
    }

    /**
     * Clear all system logs
     * @returns {Promise<Object>} Result with success status
     */
    async clearSystemLogs() {
        try {
            const response = await window.API.post('/api/system/logs/clear', {});

            if (response.ok) {
                this.systemLogs = [];
                console.log('[SYSTEM] Logs cleared via API');
                return { success: true, message: 'System logs cleared successfully' };
            } else {
                // Fallback to local clear
                this.systemLogs = [];
                console.log('[SYSTEM] Logs cleared locally');
                return { success: true, message: 'System logs cleared' };
            }
        } catch (error) {
            // Fallback to local clear
            this.systemLogs = [];
            console.log('[SYSTEM] Logs cleared locally (fallback)');
            return { success: true, message: 'System logs cleared' };
        }
    }

    /**
     * Subscribe to real-time system logs via SSE
     */
    subscribeSystemLogs() {
        if (!('EventSource' in window)) {
            console.warn('[SYSTEM] EventSource not supported');
            return;
        }

        try {
            // Close existing connection
            if (this._systemEs) {
                try {
                    this._systemEs.close();
                } catch (e) {
                    // Ignore
                }
            }

            const es = new EventSource('/events/system-logs');

            es.onmessage = (evt) => {
                try {
                    const data = JSON.parse(evt.data);
                    this.addSystemLog(
                        data.type || 'info',
                        data.message || '',
                        data.timestamp
                    );
                } catch (e) {
                    console.warn('[SYSTEM] Invalid log event:', e);
                }
            };

            es.onerror = () => {
                // Silent error handling
            };

            this._systemEs = es;
            console.log('[SYSTEM] Subscribed to system logs');

        } catch (error) {
            console.warn('[SYSTEM] SSE unavailable:', error);
        }
    }

    /**
     * Unsubscribe from system logs
     */
    unsubscribeSystemLogs() {
        if (this._systemEs) {
            try {
                this._systemEs.close();
                this._systemEs = null;
                console.log('[SYSTEM] Unsubscribed from system logs');
            } catch (e) {
                // Ignore
            }
        }
    }

    /**
     * Add system log entry
     * @param {string} type - Log type (info, success, warning, error)
     * @param {string} message - Log message
     * @param {string} timestamp - Log timestamp
     */
    addSystemLog(type, message, timestamp) {
        const log = {
            id: Date.now() + Math.random(),
            type: type || 'info',
            message: message || '',
            timestamp: timestamp || new Date().toISOString()
        };

        this.systemLogs.unshift(log);

        // Keep only max logs
        if (this.systemLogs.length > this.maxSystemLogs) {
            this.systemLogs.pop();
        }
    }

    /**
     * Get system logs
     * @returns {Array} System logs
     */
    getSystemLogs() {
        return [...this.systemLogs];
    }

    /**
     * Filter logs by type
     * @param {string} type - Log type to filter
     * @returns {Array} Filtered logs
     */
    filterLogsByType(type) {
        if (!type || type === 'all') {
            return this.getSystemLogs();
        }
        return this.systemLogs.filter(log => log.type === type);
    }

    /**
     * Get log statistics
     * @returns {Object} Statistics
     */
    getLogStats() {
        const total = this.systemLogs.length;
        const byType = {
            info: 0,
            success: 0,
            warning: 0,
            error: 0
        };

        this.systemLogs.forEach(log => {
            const type = log.type.toLowerCase();
            if (byType.hasOwnProperty(type)) {
                byType[type]++;
            }
        });

        return {
            total,
            byType,
            maxLogs: this.maxSystemLogs
        };
    }

    /**
     * Get last update time
     * @returns {string} Formatted timestamp
     */
    getLastUpdateTime() {
        const now = new Date();
        return now.toLocaleString();
    }
}

// Create singleton instance
window.SystemManager = new SystemManager();

// Export class
window.SystemManagerClass = SystemManager;

