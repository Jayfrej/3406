/**
 * @file state.js
 * @description Singleton state manager for global application state
 * @module config/state
 *
 * CRITICAL: This module holds all global state variables that were
 * previously scattered throughout app.js. This singleton pattern
 * prevents circular import issues and ensures state consistency.
 */

class AppState {
  constructor() {
    if (AppState.instance) {
      return AppState.instance;
    }

    // =====================================================
    // ACCOUNT DATA
    // =====================================================
    this.accounts = [];                    // Server-backed account list
    this.webhookAccounts = [];             // Webhook Management accounts
    this.webhookUrl = '';                  // Current webhook URL

    // =====================================================
    // COPY TRADING DATA
    // =====================================================
    this.copyPairs = [];                   // Copy trading pairs from server
    this.plans = [];                       // Plans (synced with copyPairs)
    this.masterAccounts = [];              // Master accounts for copy trading
    this.slaveAccounts = [];               // Slave accounts for copy trading
    this.copyHistory = [];                 // Copy trade history

    // =====================================================
    // HISTORY & LOGS
    // =====================================================
    this.tradeHistory = [];                // Trade history array
    this.systemLogs = [];                  // System logs array

    // =====================================================
    // UI STATE
    // =====================================================
    this.currentPage = 'accounts';         // Current active page
    this.currentAction = null;             // Current modal action callback
    this.currentExampleIndex = 0;          // Current JSON example index

    // =====================================================
    // INTERVALS & CONNECTIONS
    // =====================================================
    this.refreshInterval = null;           // Auto-refresh interval ID
    this.copyHistoryInterval = null;       // Copy history refresh interval
    this._es = null;                       // Trade events EventSource
    this._copyEs = null;                   // Copy events EventSource
    this._systemEs = null;                 // System logs EventSource

    // =====================================================
    // SYMBOL MAPPING STATE
    // =====================================================
    this.currentMappings = [];             // Current symbol mappings in edit

    // Freeze instance as singleton
    AppState.instance = this;
  }

  // =====================================================
  // STATE GETTERS
  // =====================================================

  getAccounts() {
    return this.accounts;
  }

  getWebhookAccounts() {
    return this.webhookAccounts;
  }

  getCopyPairs() {
    return this.copyPairs;
  }

  getMasterAccounts() {
    return this.masterAccounts;
  }

  getSlaveAccounts() {
    return this.slaveAccounts;
  }

  getTradeHistory() {
    return this.tradeHistory;
  }

  getCopyHistory() {
    return this.copyHistory;
  }

  getSystemLogs() {
    return this.systemLogs;
  }

  // =====================================================
  // STATE SETTERS
  // =====================================================

  setAccounts(accounts) {
    this.accounts = Array.isArray(accounts) ? accounts : [];
  }

  setWebhookAccounts(accounts) {
    this.webhookAccounts = Array.isArray(accounts) ? accounts : [];
  }

  setWebhookUrl(url) {
    this.webhookUrl = url || '';
  }

  setCopyPairs(pairs) {
    this.copyPairs = Array.isArray(pairs) ? pairs : [];
  }

  setPlans(plans) {
    this.plans = Array.isArray(plans) ? plans : [];
  }

  setMasterAccounts(accounts) {
    this.masterAccounts = Array.isArray(accounts) ? accounts : [];
  }

  setSlaveAccounts(accounts) {
    this.slaveAccounts = Array.isArray(accounts) ? accounts : [];
  }

  setTradeHistory(history) {
    this.tradeHistory = Array.isArray(history) ? history : [];
  }

  setCopyHistory(history) {
    this.copyHistory = Array.isArray(history) ? history : [];
  }

  setSystemLogs(logs) {
    this.systemLogs = Array.isArray(logs) ? logs : [];
  }

  setCurrentPage(page) {
    this.currentPage = page;
  }

  // =====================================================
  // ARRAY OPERATIONS
  // =====================================================

  addToTradeHistory(item) {
    const idx = this.tradeHistory.findIndex(x => x.id === item.id);
    if (idx !== -1) {
      this.tradeHistory.splice(idx, 1);
    }
    this.tradeHistory.unshift(item);
  }

  addToCopyHistory(item) {
    this.copyHistory.unshift(item);
  }

  addToSystemLogs(log) {
    this.systemLogs.unshift(log);
  }

  trimTradeHistory(maxItems) {
    if (this.tradeHistory.length > maxItems) {
      this.tradeHistory = this.tradeHistory.slice(0, maxItems);
    }
  }

  trimCopyHistory(maxItems) {
    if (this.copyHistory.length > maxItems) {
      this.copyHistory = this.copyHistory.slice(0, maxItems);
    }
  }

  trimSystemLogs(maxItems) {
    if (this.systemLogs.length > maxItems) {
      this.systemLogs = this.systemLogs.slice(0, maxItems);
    }
  }

  // =====================================================
  // FILTER OPERATIONS
  // =====================================================

  filterMasterAccounts(predicate) {
    this.masterAccounts = this.masterAccounts.filter(predicate);
  }

  filterSlaveAccounts(predicate) {
    this.slaveAccounts = this.slaveAccounts.filter(predicate);
  }

  filterTradeHistory(predicate) {
    this.tradeHistory = this.tradeHistory.filter(predicate);
  }

  filterWebhookAccounts(predicate) {
    this.webhookAccounts = this.webhookAccounts.filter(predicate);
  }

  // =====================================================
  // EVENT SOURCE MANAGEMENT
  // =====================================================

  setTradeEventSource(es) {
    if (this._es) {
      try { this._es.close(); } catch {}
    }
    this._es = es;
  }

  setCopyEventSource(es) {
    if (this._copyEs) {
      try { this._copyEs.close(); } catch {}
    }
    this._copyEs = es;
  }

  setSystemEventSource(es) {
    if (this._systemEs) {
      try { this._systemEs.close(); } catch {}
    }
    this._systemEs = es;
  }

  closeAllEventSources() {
    if (this._es) {
      try { this._es.close(); } catch {}
      this._es = null;
    }
    if (this._copyEs) {
      try { this._copyEs.close(); } catch {}
      this._copyEs = null;
    }
    if (this._systemEs) {
      try { this._systemEs.close(); } catch {}
      this._systemEs = null;
    }
  }

  // =====================================================
  // INTERVAL MANAGEMENT
  // =====================================================

  setRefreshInterval(intervalId) {
    this.clearRefreshInterval();
    this.refreshInterval = intervalId;
  }

  clearRefreshInterval() {
    if (this.refreshInterval) {
      clearInterval(this.refreshInterval);
      this.refreshInterval = null;
    }
  }

  setCopyHistoryInterval(intervalId) {
    this.clearCopyHistoryInterval();
    this.copyHistoryInterval = intervalId;
  }

  clearCopyHistoryInterval() {
    if (this.copyHistoryInterval) {
      clearInterval(this.copyHistoryInterval);
      this.copyHistoryInterval = null;
    }
  }

  // =====================================================
  // CLEANUP
  // =====================================================

  cleanup() {
    this.clearRefreshInterval();
    this.clearCopyHistoryInterval();
    this.closeAllEventSources();
  }

  // =====================================================
  // RESET STATE (for testing)
  // =====================================================

  reset() {
    this.cleanup();
    this.accounts = [];
    this.webhookAccounts = [];
    this.webhookUrl = '';
    this.copyPairs = [];
    this.plans = [];
    this.masterAccounts = [];
    this.slaveAccounts = [];
    this.copyHistory = [];
    this.tradeHistory = [];
    this.systemLogs = [];
    this.currentPage = 'accounts';
    this.currentAction = null;
    this.currentExampleIndex = 0;
    this.currentMappings = [];
  }
}

// Export singleton instance
const appState = new AppState();
export default appState;

// Also export the class for testing purposes
export { AppState };

