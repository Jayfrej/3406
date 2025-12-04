/**
 * @file history.js
 * @description Trade History module
 * @module modules/history
 */

import appState from '../config/state.js';
import { TradesAPI } from '../services/api.js';
import toast from '../services/toast.js';
import modal from '../services/modal.js';
import { escape, formatActionBadge } from '../utils/helpers.js';
import { UI_CONFIG } from '../config/constants.js';

/**
 * Trade History Module
 */
class HistoryModule {

  // =====================================================
  // DATA LOADING
  // =====================================================

  /**
   * Load initial history from server
   */
  async loadInitialHistory() {
    try {
      const data = await TradesAPI.getHistory(UI_CONFIG.MAX_HISTORY_ITEMS);
      const trades = data.trades || [];
      trades.reverse().forEach(tr => this.addTradeToHistory(tr));
    } catch (e) {
      console.warn('loadInitialHistory failed:', e);
    }
  }

  // =====================================================
  // OPERATIONS
  // =====================================================

  /**
   * Add trade to history
   */
  addTradeToHistory(tr) {
    const norm = {
      id: tr.id || String(Date.now()),
      status: (tr.status || '').toLowerCase() === 'error' ? 'error' : 'success',
      action: (tr.action || '').toUpperCase(),
      symbol: tr.symbol || '-',
      account: tr.account || tr.account_number || '-',
      volume: tr.volume ?? '',
      price: tr.price ?? '',
      tp: tr.tp ?? '',
      sl: tr.sl ?? '',
      message: tr.message || '',
      timestamp: tr.timestamp || new Date().toISOString(),
    };

    appState.addToTradeHistory(norm);
    appState.trimTradeHistory(UI_CONFIG.MAX_HISTORY_ITEMS);
    this.updateAccountFilterOptions();
    this.renderHistory();
  }

  /**
   * Clear trade history
   */
  async clearHistory() {
    const ok = await modal.showConfirm(
      'Clear Trading History',
      'Delete all saved trade history? This cannot be undone.'
    );
    if (!ok) return;

    try {
      const res = await TradesAPI.clearHistory();
      if (res.ok) {
        appState.setTradeHistory([]);
        this.renderHistory();
        this.updateAccountFilterOptions();
        toast.success('History cleared successfully');
      } else {
        toast.error('Failed to clear history');
      }
    } catch (e) {
      console.error('Clear history error:', e);
      toast.error('Failed to clear history');
    }
  }

  /**
   * Handle history cleared event (from SSE)
   */
  onHistoryCleared() {
    appState.setTradeHistory([]);
    this.renderHistory();
    this.updateAccountFilterOptions();
  }

  /**
   * Handle account deleted event (from SSE)
   */
  onAccountDeleted(account) {
    appState.filterTradeHistory(t => String(t.account) !== String(account));
    this.renderHistory();
    this.updateAccountFilterOptions();
  }

  // =====================================================
  // RENDERING
  // =====================================================

  /**
   * Render trade history
   */
  renderHistory() {
    const tbody = document.getElementById('historyTableBody');
    if (!tbody) return;

    const statusSel = document.getElementById('historyFilter');
    const statusFilter = (statusSel?.value || 'all').toLowerCase();

    const accSel = document.getElementById('accountFilter');
    const accountFilter = (accSel?.value || 'all').toLowerCase();

    const list = appState.tradeHistory.filter(t => {
      if (statusFilter === 'success' && t.status !== 'success') return false;
      if (statusFilter === 'error' && t.status !== 'error') return false;
      if (accountFilter !== 'all' && String(t.account).toLowerCase() !== accountFilter) return false;
      return true;
    });

    if (!list.length) {
      tbody.innerHTML = `
        <tr class="no-data">
          <td colspan="10">
            <div class="no-data-message">
              <i class="fas fa-clock-rotate-left"></i>
              <p>No trading history yet. Trades will appear here when executed.</p>
            </div>
          </td>
        </tr>`;
      return;
    }

    tbody.innerHTML = list.map(t => {
      const time = new Date(t.timestamp).toLocaleString();
      const badge = t.status === 'success' ?
        '<span class="status-badge success">success</span>' :
        '<span class="status-badge error">error</span>';
      const tpDisplay = (t.tp && t.tp !== '-') ? t.tp : '-';
      const slDisplay = (t.sl && t.sl !== '-') ? t.sl : '-';
      const messageClass = t.status === 'error' ? 'error-message' : '';

      return `
        <tr>
          <td>${badge}</td>
          <td>${escape(t.account)}</td>
          <td>${formatActionBadge(t.action)}</td>
          <td>${escape(t.symbol)}</td>
          <td>${t.price ? escape(t.price) : '-'}</td>
          <td>${escape(tpDisplay)}</td>
          <td>${escape(slDisplay)}</td>
          <td>${t.volume ? escape(t.volume) : '-'}</td>
          <td class="${messageClass}">${escape(t.message)}</td>
          <td>${time}</td>
        </tr>`;
    }).join('');
  }

  /**
   * Update account filter options
   */
  updateAccountFilterOptions() {
    const sel = document.getElementById('accountFilter');
    if (!sel) return;

    const current = sel.value || 'all';
    const fromHistory = appState.tradeHistory
      .map(t => String(t.account || '').trim())
      .filter(Boolean);
    const fromWebhook = appState.webhookAccounts
      .map(a => String(a.account || a.id || '').trim())
      .filter(Boolean);
    const all = Array.from(new Set([...fromHistory, ...fromWebhook])).sort((a, b) => a.localeCompare(b));

    const html = ['<option value="all">All Accounts</option>']
      .concat(all.map(acc => `<option value="${escape(acc)}">${escape(acc)}</option>`))
      .join('');
    sel.innerHTML = html;

    if ([...sel.options].some(o => o.value === current)) sel.value = current;
    else sel.value = 'all';
  }
}

// Export singleton
const historyModule = new HistoryModule();
export default historyModule;
export { HistoryModule };

