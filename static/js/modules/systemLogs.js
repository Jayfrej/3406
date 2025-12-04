/**
 * @file systemLogs.js
 * @description System Logs module
 * @module modules/systemLogs
 */

import appState from '../config/state.js';
import { SystemAPI } from '../services/api.js';
import toast from '../services/toast.js';
import modal from '../services/modal.js';
import { escape, formatLogTimestamp } from '../utils/helpers.js';
import { UI_CONFIG } from '../config/constants.js';

/**
 * System Logs Module
 */
class SystemLogsModule {

  // =====================================================
  // DATA LOADING
  // =====================================================

  /**
   * Load system logs from server
   */
  async loadSystemLogs() {
    try {
      const data = await SystemAPI.getLogs(UI_CONFIG.MAX_SYSTEM_LOGS);
      appState.setSystemLogs(data.logs || []);
      this.renderSystemLogs();
    } catch (e) {
      console.warn('System logs API not available, using demo logs');
      this.loadDemoLogs();
    }
  }

  /**
   * Load demo logs for development/testing
   */
  loadDemoLogs() {
    const demoLogs = [
      { type: 'info', message: 'System started successfully' },
      { type: 'success', message: 'Connected to MT5 server' },
      { type: 'info', message: 'Webhook endpoint initialized' },
      { type: 'info', message: 'Copy trading service active' },
      { type: 'success', message: 'Trade executed successfully' },
      { type: 'info', message: 'Monitoring active connections' },
      { type: 'success', message: 'Trade executed successfully' },
      { type: 'success', message: 'Webhook received and processed' },
      { type: 'info', message: 'Checking account status' },
      { type: 'success', message: 'All accounts online' },
      { type: 'info', message: 'Health check completed' },
      { type: 'success', message: 'Copy trading pair synchronized' },
    ];

    const now = Date.now();
    const logs = demoLogs.map((log, index) => ({
      id: now + index,
      type: log.type,
      message: log.message,
      timestamp: new Date(now - (demoLogs.length - index) * 3000).toISOString()
    }));

    appState.setSystemLogs(logs);
    this.renderSystemLogs();
  }

  // =====================================================
  // OPERATIONS
  // =====================================================

  /**
   * Add system log entry
   */
  addSystemLog(type, message, timestamp) {
    const log = {
      id: Date.now() + Math.random(),
      type: type || 'info',
      message: message || '',
      timestamp: timestamp || new Date().toISOString()
    };

    appState.addToSystemLogs(log);
    appState.trimSystemLogs(UI_CONFIG.MAX_SYSTEM_LOGS);

    if (appState.currentPage === 'system') {
      this.renderSystemLogs();
    }
  }

  /**
   * Clear system logs
   */
  async clearSystemLogs() {
    const ok = await modal.showConfirm(
      'Clear System Logs',
      'Delete all system logs? This cannot be undone.'
    );
    if (!ok) return;

    try {
      const res = await SystemAPI.clearLogs();
      if (res.ok) {
        appState.setSystemLogs([]);
        this.renderSystemLogs();
        toast.success('System logs cleared successfully');
      } else {
        // Fallback to local clear
        appState.setSystemLogs([]);
        this.renderSystemLogs();
        toast.success('System logs cleared');
      }
    } catch (e) {
      appState.setSystemLogs([]);
      this.renderSystemLogs();
      toast.success('System logs cleared');
    }
  }

  // =====================================================
  // RENDERING
  // =====================================================

  /**
   * Render system logs
   */
  renderSystemLogs() {
    const container = document.getElementById('systemLogsContainer');
    if (!container) return;

    const logs = appState.getSystemLogs();
    const totalLogs = logs.length;
    const maxLogs = UI_CONFIG.MAX_SYSTEM_LOGS;

    if (totalLogs === 0) {
      container.innerHTML = `
        <div class="log-header">
          <h3><i class="fas fa-history"></i> Log History</h3>
          <span class="log-count">0 / ${maxLogs} entries</span>
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
      const time = formatLogTimestamp(log.timestamp);
      const typeClass = log.type.toLowerCase();
      const typeLabel = log.type.toUpperCase();

      return `<div class="log-entry log-${typeClass}">${time} <span class="log-badge log-badge-${typeClass}">${typeLabel}</span> ${escape(log.message)}</div>`;
    }).join('');

    container.innerHTML = `
      <div class="log-header">
        <h3><i class="fas fa-history"></i> Log History</h3>
        <span class="log-count">${totalLogs} / ${maxLogs} entries</span>
      </div>
      <div class="log-content">
        ${logsHtml}
      </div>
    `;
  }
}

// Export singleton
const systemLogsModule = new SystemLogsModule();
export default systemLogsModule;
export { SystemLogsModule };

