/**
 * @file accounts.js
 * @description Account management module
 * @module modules/accounts
 */

import appState from '../config/state.js';
import { AccountAPI, WebhookAPI } from '../services/api.js';
import toast from '../services/toast.js';
import modal from '../services/modal.js';
import loading from '../controllers/loading.js';
import { escape, formatLastSeen } from '../utils/helpers.js';

/**
 * Account Management Module
 */
class AccountsModule {

  // =====================================================
  // DATA LOADING
  // =====================================================

  /**
   * Load all data (accounts, webhook URL, webhook accounts)
   */
  async loadData() {
    try {
      loading.show();

      const [accountsResponse, webhookUrlResponse, webhookAccountsResponse] = await Promise.all([
        AccountAPI.getAll().catch(() => null),
        WebhookAPI.getUrl().catch(() => null),
        WebhookAPI.getAccounts().catch(() => null)
      ]);

      if (accountsResponse) {
        appState.setAccounts(accountsResponse.accounts || []);
        this.renderAccountsTableAM();
        this.updateStatsAM();
      }

      if (webhookAccountsResponse) {
        appState.setWebhookAccounts(webhookAccountsResponse.accounts || []);
      } else {
        // Fallback to localStorage
        const saved = localStorage.getItem('mt5_webhook_accounts');
        appState.setWebhookAccounts(saved ? JSON.parse(saved) : []);
      }

      this.renderAccountsTable();
      this.updateStats();

      if (webhookUrlResponse) {
        appState.setWebhookUrl(webhookUrlResponse.url || '');
        this.updateWebhookDisplay();
      }

      this.updateLastUpdateTime();
    } catch (error) {
      console.error('Failed to load data:', error);
      toast.error('Failed to load data');
    } finally {
      loading.hide();
    }
  }

  /**
   * Load Account Management page data
   */
  async loadAccountManagementData() {
    try {
      const data = await AccountAPI.getAll();
      appState.setAccounts(data.accounts || []);
      this.renderAccountsTableAM();
      this.updateStatsAM();
      this.loadAccountOptions();
      await this.loadGlobalSecret();
    } catch (error) {
      console.error('Failed to load account management data:', error);
    }
  }

  // =====================================================
  // ACCOUNT MANAGEMENT (AM) PAGE
  // =====================================================

  /**
   * Add account from Account Management page
   */
  async addAccountAM() {
    const formData = new FormData(document.getElementById('addAccountFormAM'));
    const account = String(formData.get('account') || '').trim();
    const nickname = String(formData.get('nickname') || '').trim();

    if (!account) {
      toast.warning('Please enter account number');
      return;
    }

    try {
      loading.show();
      await AccountAPI.add(account, nickname);
      toast.success('Account added successfully');
      document.getElementById('addAccountFormAM').reset();
      await this.loadAccountManagementData();
      await this.loadData();
    } catch (error) {
      console.error('Failed to add account:', error);
      toast.error(error.message || 'Failed to add account');
    } finally {
      loading.hide();
    }
  }

  /**
   * Render accounts table for Account Management page
   */
  renderAccountsTableAM() {
    const tbody = document.getElementById('accountsTableBodyAM');
    if (!tbody) return;

    const accounts = appState.getAccounts();

    if (!accounts.length) {
      tbody.innerHTML = `
        <tr class="no-data">
          <td colspan="6">
            <div class="no-data-message">
              <i class="fas fa-inbox"></i>
              <p>No accounts found. Add your first account above.</p>
            </div>
          </td>
        </tr>`;
      return;
    }

    tbody.innerHTML = accounts.map(account => {
      const statusClass = (account.status || 'Wait for Activate').toLowerCase().replace(/ /g, '-');
      const lastSeenText = formatLastSeen(account.last_seen);

      return `
        <tr data-account="${account.account}">
          <td>
            <span class="status-badge ${statusClass}">
              <i class="fas fa-circle"></i>
              ${account.status}
            </span>
          </td>
          <td><strong>${account.account}</strong></td>
          <td>${account.nickname || '-'}</td>
          <td>${account.broker || '-'}</td>
          <td title="${account.last_seen || ''}">${lastSeenText}</td>
          <td>
            <div class="action-buttons">
              <button class="btn btn-info btn-sm"
                      onclick="ui.showSymbolMappingModal('${account.account}')"
                      title="View Symbol Mappings">
                <i class="fas fa-exchange-alt"></i>
              </button>
              ${account.status === 'Online' ? `
              <button class="btn btn-warning btn-sm"
                      onclick="ui.performAccountActionAM('${account.account}', 'pause')"
                      title="Pause Account">
                <i class="fas fa-pause"></i>
              </button>
              ` : account.status === 'PAUSE' ? `
              <button class="btn btn-success btn-sm"
                      onclick="ui.performAccountActionAM('${account.account}', 'resume')"
                      title="Resume Account">
                <i class="fas fa-play"></i>
              </button>
              ` : ''}
              <button class="btn btn-secondary btn-sm"
                      onclick="ui.performAccountActionAM('${account.account}', 'delete')"
                      title="Delete">
                <i class="fas fa-trash"></i>
              </button>
            </div>
          </td>
        </tr>`;
    }).join('');
  }

  /**
   * Update stats for Account Management page
   */
  updateStatsAM() {
    const accounts = appState.getAccounts();
    const total = accounts.length;
    const online = accounts.filter(acc => acc.status === 'Online').length;
    const offline = total - online;

    const totalEl = document.getElementById('totalAccountsAM');
    const onlineEl = document.getElementById('onlineAccountsAM');
    const offlineEl = document.getElementById('offlineAccountsAM');

    if (totalEl) totalEl.textContent = total;
    if (onlineEl) onlineEl.textContent = online;
    if (offlineEl) offlineEl.textContent = offline;
  }

  /**
   * Perform account action (delete, pause, resume)
   * @param {string} account
   * @param {string} action
   */
  async performAccountActionAM(account, action) {
    const confirmMessages = {
      delete: 'Are you sure you want to delete this account? This action cannot be undone.',
      pause: 'Pause this account? The account will not receive any signals until resumed.',
      resume: 'Resume this account? The account will start receiving signals again.'
    };

    const confirmTitles = {
      delete: 'Confirm Delete',
      pause: 'Confirm Pause',
      resume: 'Confirm Resume'
    };

    if (!await modal.showConfirm(confirmTitles[action], confirmMessages[action])) {
      return;
    }

    try {
      loading.show();

      if (action === 'delete') {
        const data = await AccountAPI.delete(account);

        if (data.ok) {
          const deletedPairs = data.deleted_pairs || 0;
          const cleanupMsg = deletedPairs > 0
            ? `Account deleted (removed ${deletedPairs} copy pair(s))`
            : 'Account deleted successfully';

          toast.success(cleanupMsg);

          // Comprehensive cleanup
          await this.loadAccountManagementData();
          await this.loadData();

          // Filter deleted account from master/slave arrays
          appState.filterMasterAccounts(a => String(a.accountNumber) !== String(account));
          appState.filterSlaveAccounts(a => String(a.accountNumber) !== String(account));

          console.log(`[DELETE_ACCOUNT] Account ${account} deleted, ${deletedPairs} pairs removed`);
        } else {
          toast.error(data.error || 'Failed to delete account');
        }
      } else if (action === 'pause') {
        const data = await AccountAPI.pause(account);
        toast.success('Account paused successfully');
        await this.loadAccountManagementData();
        await this.loadData();
      } else if (action === 'resume') {
        const data = await AccountAPI.resume(account);
        toast.success('Account resumed successfully');
        await this.loadAccountManagementData();
        await this.loadData();
      }
    } catch (error) {
      console.error(`Failed to ${action} account:`, error);
      toast.error(`Failed to ${action} account`);
    } finally {
      loading.hide();
    }
  }

  /**
   * Filter accounts table (AM)
   * @param {string} searchTerm
   */
  filterTableAM(searchTerm) {
    const rows = document.querySelectorAll('#accountsTableBodyAM tr:not(.no-data)');
    const term = String(searchTerm || '').toLowerCase();
    rows.forEach(row => {
      const text = row.textContent.toLowerCase();
      row.style.display = text.includes(term) ? '' : 'none';
    });
  }

  // =====================================================
  // WEBHOOK PAGE
  // =====================================================

  /**
   * Add account from Webhook page
   */
  async addAccount() {
    const formData = new FormData(document.getElementById('addAccountForm'));
    const account = String(formData.get('account') || '').trim();
    const nickname = String(formData.get('nickname') || '').trim();

    if (!account) {
      toast.warning('Please enter account number');
      return;
    }

    try {
      loading.show();

      // Save to Account Management
      await AccountAPI.add(account, nickname);

      // Also save to Webhook accounts
      try {
        await WebhookAPI.addAccount({ account, nickname, enabled: true });

        const webhookAccounts = appState.getWebhookAccounts();
        if (!webhookAccounts.some(a => (a.account || a.id) === account)) {
          webhookAccounts.push({
            account,
            nickname,
            enabled: true,
            status: 'Wait for Activate',
            created: new Date().toISOString()
          });
          appState.setWebhookAccounts(webhookAccounts);
        }
      } catch (webhookError) {
        console.error('Failed to add to webhook accounts:', webhookError);
      }

      toast.success('Account added successfully');
      document.getElementById('addAccountForm').reset();
      await this.loadData();
      this.renderAccountsTable();
    } catch (error) {
      console.error('Failed to add account:', error);
      toast.error(error.message || 'Failed to add account');
    } finally {
      loading.hide();
    }
  }

  /**
   * Render accounts table for Webhook page
   */
  renderAccountsTable() {
    const tbody = document.getElementById('accountsTableBody');
    if (!tbody) return;

    const list = appState.getWebhookAccounts();
    const accounts = appState.getAccounts();

    if (!list.length) {
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

    tbody.innerHTML = list.map(webhookAccount => {
      const accNumber = webhookAccount.account || webhookAccount.id || '';

      // Find server account data
      const serverAccount = accounts.find(a => String(a.account) === String(accNumber));

      const status = serverAccount?.status || 'Unknown';
      const pid = serverAccount?.pid || '-';
      const created = serverAccount?.created || webhookAccount.created || '-';
      const nickname = serverAccount?.nickname || webhookAccount.nickname || '-';

      const statusClass = status.toLowerCase();
      const createdDate = created !== '-' ? new Date(created).toLocaleString() : '-';

      return `
        <tr data-account="${escape(accNumber)}">
          <td>
            <span class="status-badge ${escape(statusClass)}">
              <i class="fas fa-circle"></i>
              ${escape(status)}
            </span>
          </td>
          <td><strong>${escape(accNumber)}</strong></td>
          <td>${escape(nickname)}</td>
          <td>${escape(pid)}</td>
          <td title="${escape(createdDate)}">${escape(createdDate || '-')}</td>
          <td>
            <div class="action-buttons">
              <button class="btn btn-secondary btn-sm" onclick="ui.performAccountAction('${escape(accNumber)}', 'delete')" title="Remove from Webhook">
                <i class="fas fa-trash"></i>
              </button>
            </div>
          </td>
        </tr>`;
    }).join('');
  }

  /**
   * Update stats for Webhook page
   */
  updateStats() {
    const list = appState.getWebhookAccounts();
    const total = list.length;
    const online = list.filter(acc => acc.status === 'Online').length;
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
   * Perform account action on Webhook page
   * @param {string} account
   * @param {string} action
   */
  async performAccountAction(account, action) {
    if (action === 'delete') {
      const confirmMessage = 'Remove this account from the webhook page? (Account will remain on the server)';
      if (!await modal.showConfirm('Confirm Action', confirmMessage)) return;
    }

    try {
      loading.show();

      if (action === 'delete') {
        // Remove from Webhook Management only
        appState.filterWebhookAccounts(acc => (acc.account || acc.id) !== account);

        // Persist delete
        try {
          await WebhookAPI.deleteAccount(account);
        } catch (e) {
          localStorage.setItem('mt5_webhook_accounts', JSON.stringify(appState.getWebhookAccounts()));
        }

        this.renderAccountsTable();
        this.updateStats();
        toast.success('Account removed from webhook page');
      } else {
        // For other actions, call the server
        const response = await fetch(`/accounts/${account}/${action}`, { method: 'POST' });
        const data = await response.json();

        if (response.ok) {
          toast.success(`Account ${action} successful`);
          await this.loadData();
        } else {
          toast.error(data.error || `Failed to ${action} account`);
        }
      }
    } catch (error) {
      console.error(`Failed to ${action} account:`, error);
      toast.error(`Failed to ${action} account`);
    } finally {
      loading.hide();
    }
  }

  /**
   * Filter accounts table (Webhook)
   * @param {string} searchTerm
   */
  filterTable(searchTerm) {
    const rows = document.querySelectorAll('#accountsTableBody tr:not(.no-data)');
    const term = String(searchTerm || '').toLowerCase();
    rows.forEach(row => {
      const text = row.textContent.toLowerCase();
      row.style.display = text.includes(term) ? '' : 'none';
    });
  }

  // =====================================================
  // COMMON FUNCTIONS
  // =====================================================

  /**
   * Update webhook URL display
   */
  updateWebhookDisplay() {
    const webhookUrl = appState.webhookUrl;
    const webhookElement = document.getElementById('webhookUrl');
    const webhookElementAM = document.getElementById('webhookUrlAM');
    const webhookEndpointElement = document.getElementById('webhookEndpoint');
    const webhookEndpointSystemElement = document.getElementById('webhookEndpointSystem');

    if (webhookElement && webhookUrl) webhookElement.value = webhookUrl;
    if (webhookElementAM && webhookUrl) webhookElementAM.value = webhookUrl;
    if (webhookEndpointElement && webhookUrl) webhookEndpointElement.textContent = webhookUrl;
    if (webhookEndpointSystemElement && webhookUrl) webhookEndpointSystemElement.textContent = webhookUrl;

    // Update Copy Trading Endpoint
    const copyTradingEndpointSystemElement = document.getElementById('copyTradingEndpointSystem');
    if (copyTradingEndpointSystemElement) {
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
  }

  /**
   * Update last update time display
   */
  updateLastUpdateTime() {
    const now = new Date();
    const timeString = now.toLocaleTimeString();
    const fullTimeString = now.toLocaleString();

    const lastUpdateEl = document.getElementById('lastUpdate');
    const lastUpdateAMEl = document.getElementById('lastUpdateAM');
    const healthCheckEl = document.getElementById('lastHealthCheck');
    const healthCheckSystemEl = document.getElementById('lastHealthCheckSystem');

    if (lastUpdateEl) lastUpdateEl.textContent = timeString;
    if (lastUpdateAMEl) lastUpdateAMEl.textContent = timeString;
    if (healthCheckEl) healthCheckEl.textContent = fullTimeString;
    if (healthCheckSystemEl) healthCheckSystemEl.textContent = fullTimeString;
  }

  /**
   * Load account options for dropdowns
   */
  loadAccountOptions() {
    const secretSelect = document.getElementById('secretAccountSelect');

    if (secretSelect) {
      secretSelect.innerHTML = '<option value="">-- Select Account --</option>';
      appState.getAccounts().forEach(acc => {
        const option = document.createElement('option');
        option.value = acc.account;
        option.textContent = `${acc.account}${acc.nickname ? ' (' + acc.nickname + ')' : ''}`;
        secretSelect.appendChild(option);
      });
    }
  }

  /**
   * Load global secret key
   */
  async loadGlobalSecret() {
    try {
      const data = await AccountAPI.getSecret('global').catch(() => ({ secret: '' }));
      const input = document.getElementById('globalSecretInput');
      if (input) {
        input.value = data.secret || '';
      }
    } catch (error) {
      console.error('Failed to load global secret:', error);
    }
  }

  /**
   * Update account filter options
   */
  updateAccountFilterOptions() {
    const sel = document.getElementById('accountFilter');
    if (!sel) return;

    const current = sel.value || 'all';
    const fromHistory = appState.getTradeHistory()
      .map(t => String(t.account || '').trim())
      .filter(Boolean);
    const fromWebhook = appState.getWebhookAccounts()
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
const accountsModule = new AccountsModule();
export default accountsModule;

// Also export class for testing
export { AccountsModule };

