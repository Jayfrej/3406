/**
 * @file app-modular.js
 * @description Main entry point for modular MT5 Trading Bot UI
 * @version 2.0.0
 *
 * This file replaces the monolithic app.js with a modular architecture.
 * All business logic is imported from separate modules.
 */

// =====================================================
// IMPORTS
// =====================================================

// Config
import appState from './config/state.js';
import { UI_CONFIG, JSON_EXAMPLES, PAGES } from './config/constants.js';

// Services
import { ensureLogin, fetchWithAuth } from './services/api.js';
import toast from './services/toast.js';
import modal from './services/modal.js';
import sseService from './services/sse.js';

// Controllers
import themeController from './controllers/theme.js';
import loading from './controllers/loading.js';
import navigation from './controllers/navigation.js';

// Modules
import accountsModule from './modules/accounts.js';
import copyTradingModule from './modules/copyTrading.js';
import settingsModule from './modules/settings.js';
import systemLogsModule from './modules/systemLogs.js';
import historyModule from './modules/history.js';

// Utils
import { escape, copyToClipboard, generateSecretKey } from './utils/helpers.js';

// =====================================================
// TRADING BOT UI CLASS
// =====================================================

class TradingBotUI {
  constructor() {
    this.currentExampleIndex = 0;
    this.init();
  }

  // =====================================================
  // INITIALIZATION
  // =====================================================

  async init() {
    // Initialize theme
    themeController.init();

    // Setup event listeners
    this.setupEventListeners();

    // Ensure login
    await ensureLogin();

    // Set default page
    appState.setCurrentPage(PAGES.ACCOUNTS);

    // Navigate to default page
    await navigation.switchTo(PAGES.ACCOUNTS);

    // Load initial data
    await accountsModule.loadData();

    // Start auto-refresh
    this.startAutoRefresh();

    // Update last update time
    accountsModule.updateLastUpdateTime();

    // Show first JSON example
    this.showExample(0);

    // Render history
    historyModule.renderHistory();

    // Load initial history and subscribe to events
    await historyModule.loadInitialHistory();
    historyModule.updateAccountFilterOptions();
    this.subscribeTradeEvents();

    // Load Copy Trading data
    await copyTradingModule.loadCopyPairs();
    await copyTradingModule.loadCopyHistory();
    this.subscribeCopyEvents();
    await copyTradingModule.loadMasterAccounts();
    await copyTradingModule.loadSlaveAccounts();
    copyTradingModule.renderMasterAccounts();
    copyTradingModule.renderSlaveAccounts();

    // Load System Logs
    await systemLogsModule.loadSystemLogs();
    this.subscribeSystemLogs();
  }

  // =====================================================
  // EVENT LISTENERS SETUP
  // =====================================================

  setupEventListeners() {
    // Theme toggle
    const themeBtn = document.getElementById('themeToggleBtn');
    if (themeBtn) themeBtn.addEventListener('click', () => themeController.toggle());

    // Navigation setup
    navigation.setupListeners();

    // Register page initializers
    navigation.registerInitializer(PAGES.ACCOUNTS, async () => {
      await accountsModule.loadAccountManagementData();
    });

    navigation.registerInitializer(PAGES.WEBHOOK, async () => {
      // loadData already handles this
    });

    navigation.registerInitializer(PAGES.COPYTRADING, async () => {
      await accountsModule.loadData();
      await copyTradingModule.loadCopyPairs();
      await copyTradingModule.loadCopyHistory();
      copyTradingModule.renderMasterAccounts();
      copyTradingModule.renderSlaveAccounts();
    });

    navigation.registerInitializer(PAGES.SYSTEM, async () => {
      accountsModule.updateWebhookDisplay();
      accountsModule.updateLastUpdateTime();
      systemLogsModule.renderSystemLogs();
    });

    navigation.registerInitializer(PAGES.SETTINGS, async () => {
      await settingsModule.loadAllSettings();
      await settingsModule.loadEmailSettings();
      await settingsModule.populateSymbolMappingAccounts();
    });

    // Account Management form
    const addFormAM = document.getElementById('addAccountFormAM');
    if (addFormAM) {
      addFormAM.addEventListener('submit', (e) => {
        e.preventDefault();
        accountsModule.addAccountAM();
      });
    }

    // Webhook page form
    const addForm = document.getElementById('addAccountForm');
    if (addForm) {
      addForm.addEventListener('submit', (e) => {
        e.preventDefault();
        accountsModule.addAccount();
      });
    }

    // Refresh button
    const refreshBtn = document.getElementById('refreshBtn');
    if (refreshBtn) refreshBtn.addEventListener('click', () => accountsModule.loadData());

    // Webhook URL copy
    const webhookBtn = document.getElementById('webhookBtn');
    if (webhookBtn) webhookBtn.addEventListener('click', () => this.copyWebhookUrl());

    // Search inputs
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
      searchInput.addEventListener('input', (e) => accountsModule.filterTable(e.target.value));
    }

    const searchInputAM = document.getElementById('searchInputAM');
    if (searchInputAM) {
      searchInputAM.addEventListener('input', (e) => accountsModule.filterTableAM(e.target.value));
    }

    // Modal events
    document.addEventListener('click', (e) => {
      if (e.target.classList.contains('modal-overlay')) modal.close();
      if (e.target.id === 'symbolMappingModal') this.closeSymbolMappingOverview();
    });

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        modal.close();
        this.closeSymbolMappingOverview();
      }
    });

    // Visibility change
    document.addEventListener('visibilitychange', () => {
      if (!document.hidden) {
        accountsModule.loadData();
        if (appState.currentPage === PAGES.COPYTRADING) {
          copyTradingModule.loadCopyPairs();
        }
      }
    });

    // Online/offline events
    window.addEventListener('online', () => {
      toast.success('Connection restored');
      accountsModule.loadData();
    });

    window.addEventListener('offline', () => {
      toast.warning('Connection lost');
    });

    // History filters
    const historyFilter = document.getElementById('historyFilter');
    if (historyFilter) historyFilter.addEventListener('change', () => historyModule.renderHistory());

    const accountFilter = document.getElementById('accountFilter');
    if (accountFilter) accountFilter.addEventListener('change', () => historyModule.renderHistory());

    // Copy history filters
    const copyHistoryFilter = document.getElementById('copyHistoryFilter');
    if (copyHistoryFilter) copyHistoryFilter.addEventListener('change', () => copyTradingModule.renderCopyHistory());

    const copyAccountFilter = document.getElementById('copyAccountFilter');
    if (copyAccountFilter) copyAccountFilter.addEventListener('change', () => copyTradingModule.renderCopyHistory());

    // Copy endpoint buttons
    const copyEndpointBtn = document.getElementById('copyEndpointBtn');
    if (copyEndpointBtn) {
      copyEndpointBtn.addEventListener('click', () => this.copyCopyTradingEndpoint());
    }
    const copyEndpointBtnSystem = document.getElementById('copyEndpointBtnSystem');
    if (copyEndpointBtnSystem) {
      copyEndpointBtnSystem.addEventListener('click', () => this.copyCopyTradingEndpoint());
    }

    // Secret key listeners
    this.setupSecretAndMappingListeners();
  }

  setupSecretAndMappingListeners() {
    // Global Secret Key Form
    const globalSecretForm = document.getElementById('globalSecretForm');
    const saveGlobalSecretBtn = document.getElementById('saveGlobalSecretBtn');
    const generateGlobalSecretBtn = document.getElementById('generateGlobalSecretBtn');
    const clearGlobalSecretBtn = document.getElementById('clearGlobalSecretBtn');

    if (globalSecretForm) {
      globalSecretForm.addEventListener('submit', (e) => {
        e.preventDefault();
        settingsModule.saveGlobalSecret();
      });
    }
    if (saveGlobalSecretBtn) {
      saveGlobalSecretBtn.addEventListener('click', () => settingsModule.saveGlobalSecret());
    }
    if (generateGlobalSecretBtn) {
      generateGlobalSecretBtn.addEventListener('click', () => settingsModule.generateGlobalSecret());
    }
    if (clearGlobalSecretBtn) {
      clearGlobalSecretBtn.addEventListener('click', () => settingsModule.clearGlobalSecret());
    }

    // Per-Account Secret Key Form
    const secretForm = document.getElementById('secretKeyForm');
    const secretAccountSelect = document.getElementById('secretAccountSelect');
    const generateSecretBtn = document.getElementById('generateSecretBtn');
    const clearSecretBtn = document.getElementById('clearSecretBtn');

    if (secretForm) {
      secretForm.addEventListener('submit', (e) => {
        e.preventDefault();
        this.saveSecretKey();
      });
    }
    if (secretAccountSelect) {
      secretAccountSelect.addEventListener('change', (e) => this.loadSecretKey(e.target.value));
    }
    if (generateSecretBtn) {
      generateSecretBtn.addEventListener('click', () => this.generateSecretKey());
    }
    if (clearSecretBtn) {
      clearSecretBtn.addEventListener('click', () => this.clearSecretKey());
    }

    // View all mappings button
    const viewAllMappingsBtn = document.getElementById('viewAllMappingsBtn');
    const closeMappingOverviewBtn = document.getElementById('closeMappingOverviewBtn');

    if (viewAllMappingsBtn) {
      viewAllMappingsBtn.addEventListener('click', () => this.showMappingOverview());
    }
    if (closeMappingOverviewBtn) {
      closeMappingOverviewBtn.addEventListener('click', () => this.closeMappingOverview());
    }

    // Close modal when clicking outside
    const mappingOverviewModal = document.getElementById('mappingOverviewModal');
    if (mappingOverviewModal) {
      mappingOverviewModal.addEventListener('click', (e) => {
        if (e.target === mappingOverviewModal) this.closeMappingOverview();
      });
    }
  }

  // =====================================================
  // SSE SUBSCRIPTIONS
  // =====================================================

  subscribeTradeEvents() {
    sseService.subscribeTradeEvents(
      (data) => historyModule.addTradeToHistory(data),
      () => historyModule.onHistoryCleared(),
      (account) => historyModule.onAccountDeleted(account)
    );
  }

  subscribeCopyEvents() {
    sseService.subscribeCopyEvents(
      (data) => copyTradingModule.addCopyToHistory(data),
      () => {
        appState.setCopyHistory([]);
        copyTradingModule.renderCopyHistory();
      }
    );
  }

  subscribeSystemLogs() {
    sseService.subscribeSystemLogs(
      (type, message, timestamp) => systemLogsModule.addSystemLog(type, message, timestamp),
      async (data) => {
        console.log('[SSE] Account deleted event:', data);
        await Promise.all([
          accountsModule.loadAccountManagementData(),
          accountsModule.loadData(),
          copyTradingModule.loadCopyPairs(),
          copyTradingModule.loadMasterAccounts(),
          copyTradingModule.loadSlaveAccounts()
        ]);
        toast.info(`Account ${data.account} deleted (${data.deleted_pairs || 0} pair(s) removed)`);
      },
      async (data) => {
        console.log('[SSE] Pair deleted event:', data);
        await copyTradingModule.loadCopyPairs();
      }
    );
  }

  // =====================================================
  // AUTO REFRESH
  // =====================================================

  startAutoRefresh() {
    const intervalId = setInterval(() => {
      if (!document.hidden) {
        accountsModule.loadData();
        if (appState.currentPage === PAGES.COPYTRADING) {
          copyTradingModule.loadCopyPairs();
        }
      }
    }, UI_CONFIG.AUTO_REFRESH_INTERVAL);
    appState.setRefreshInterval(intervalId);
  }

  stopAutoRefresh() {
    appState.clearRefreshInterval();
  }

  // =====================================================
  // JSON EXAMPLES
  // =====================================================

  showExample(index) {
    this.currentExampleIndex = index;
    const example = JSON_EXAMPLES[index];
    document.querySelectorAll('.example-nav-btn').forEach((btn, i) => {
      btn.classList.toggle('active', i === index);
    });
    const titleEl = document.getElementById('exampleTitle');
    const codeEl = document.getElementById('jsonCode');
    if (titleEl) titleEl.textContent = example.title;
    if (codeEl) codeEl.textContent = example.json;
  }

  copyExample() {
    const jsonCode = document.getElementById('jsonCode');
    if (jsonCode) {
      this.copyToClipboard(jsonCode.textContent, 'JSON example copied to clipboard!');
    }
  }

  // =====================================================
  // CLIPBOARD HELPERS
  // =====================================================

  async copyToClipboard(text, successMsg = 'Copied to clipboard!') {
    const success = await copyToClipboard(text);
    if (success) {
      toast.success(successMsg);
    } else {
      toast.error('Failed to copy to clipboard');
    }
  }

  async copyWebhookUrl() {
    if (!appState.webhookUrl) {
      toast.warning('Webhook URL not available');
      return;
    }
    await this.copyToClipboard(appState.webhookUrl, 'Webhook URL copied to clipboard!');
  }

  async copyCopyTradingEndpoint() {
    try {
      let baseUrl = '';
      if (appState.webhookUrl) {
        const url = new URL(appState.webhookUrl);
        baseUrl = `${url.protocol}//${url.host}`;
      } else {
        baseUrl = `${window.location.protocol}//${window.location.host}`;
      }
      const copyTradingEndpoint = `${baseUrl}/api/copy/trade`;
      await this.copyToClipboard(copyTradingEndpoint, 'Copy Trading Endpoint copied to clipboard!');
    } catch (error) {
      console.error('Failed to copy endpoint:', error);
      toast.error('Failed to copy endpoint');
    }
  }

  // =====================================================
  // SECRET KEY MANAGEMENT (Per-Account)
  // =====================================================

  async loadSecretKey(account) {
    if (!account) {
      document.getElementById('secretKeyInput').value = '';
      return;
    }
    try {
      const response = await fetch(`/accounts/${account}/secret`);
      if (response.ok) {
        const data = await response.json();
        document.getElementById('secretKeyInput').value = data.secret || '';
      }
    } catch (error) {
      console.error('Failed to load secret key:', error);
    }
  }

  generateSecretKey() {
    document.getElementById('secretKeyInput').value = generateSecretKey();
  }

  async saveSecretKey() {
    const account = document.getElementById('secretAccountSelect').value;
    const secret = document.getElementById('secretKeyInput').value.trim();

    if (!account) {
      toast.warning('Please select an account');
      return;
    }

    try {
      loading.show();
      const response = await fetch(`/accounts/${account}/secret`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ secret })
      });
      const data = await response.json();
      if (response.ok) {
        toast.success(data.message || 'Secret key saved successfully');
      } else {
        toast.error(data.error || 'Failed to save secret key');
      }
    } catch (error) {
      console.error('Failed to save secret key:', error);
      toast.error('Failed to save secret key');
    } finally {
      loading.hide();
    }
  }

  async clearSecretKey() {
    const account = document.getElementById('secretAccountSelect').value;
    if (!account) {
      toast.warning('Please select an account');
      return;
    }

    if (!confirm(`Are you sure you want to clear the secret key for account ${account}?`)) {
      return;
    }

    try {
      loading.show();
      const response = await fetch(`/accounts/${account}/secret`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ secret: '' })
      });
      const data = await response.json();
      if (response.ok) {
        document.getElementById('secretKeyInput').value = '';
        toast.success('Secret key cleared successfully');
      } else {
        toast.error(data.error || 'Failed to clear secret key');
      }
    } catch (error) {
      console.error('Failed to clear secret key:', error);
      toast.error('Failed to clear secret key');
    } finally {
      loading.hide();
    }
  }

  // =====================================================
  // SYMBOL MAPPING MODAL (from Account Management)
  // =====================================================

  async showSymbolMappingModal(accountNumber) {
    try {
      loading.show();
      const accounts = appState.getAccounts();

      // Load mappings
      const mappingsResponse = await fetch(`/accounts/${accountNumber}/symbols`, {
        credentials: 'include'
      });
      let savedMappings = [];
      if (mappingsResponse.ok) {
        const mappingsData = await mappingsResponse.json();
        const mappings = mappingsData.mappings || {};
        if (typeof mappings === 'object' && !Array.isArray(mappings)) {
          savedMappings = Object.entries(mappings).map(([from, to]) => ({from, to}));
        } else if (Array.isArray(mappings)) {
          savedMappings = mappings;
        }
      }
      loading.hide();

      if (accounts.length === 0) {
        toast.warning('No accounts found. Please add an account first.');
        return;
      }

      const modalEl = document.createElement('div');
      modalEl.id = 'symbolMappingModal';
      modalEl.className = 'modal-overlay';
      modalEl.innerHTML = `
        <div class="modal" style="max-width: 800px;">
          <div class="modal-header">
            <h3><i class="fas fa-exchange-alt"></i> Symbol Mapping - Account ${escape(accountNumber)}</h3>
            <button class="modal-close" onclick="ui.closeSymbolMappingModal()">
              <i class="fas fa-times"></i>
            </button>
          </div>
          <div class="modal-body">
            <div class="form-group" style="margin-bottom: 25px;">
              <label>Select Account</label>
              <select id="symbolMappingAccountSelect" class="form-input" onchange="ui.changeSymbolMappingAccount(this.value)">
                ${accounts.map(acc => `
                  <option value="${escape(acc.account)}" ${acc.account === accountNumber ? 'selected' : ''}>
                    ${escape(acc.account)}${acc.nickname ? ' - ' + escape(acc.nickname) : ''}
                  </option>
                `).join('')}
              </select>
            </div>
            <div style="margin-bottom: 20px;">
              <h4 style="margin-bottom: 15px; font-size: 1rem;">
                <i class="fas fa-list"></i> Custom Symbol Mappings
              </h4>
              <div class="table-container" style="max-height: 400px; overflow-y: auto;">
                <table class="accounts-table">
                  <thead>
                    <tr>
                      <th>From Symbol (TradingView)</th>
                      <th>To Symbol (Broker)</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody id="symbolMappingTableBody">
                    ${savedMappings.length === 0 ? `
                      <tr class="no-data">
                        <td colspan="3">
                          <div class="no-data-message">
                            <i class="fas fa-exchange-alt"></i>
                            <p>No custom mappings yet</p>
                          </div>
                        </td>
                      </tr>
                    ` : savedMappings.map(mapping => `
                      <tr>
                        <td>${escape(mapping.from)}</td>
                        <td>${escape(mapping.to)}</td>
                        <td>
                          <button class="btn btn-danger btn-sm" onclick="ui.deleteSymbolMappingByIndex('${escape(accountNumber)}', '${escape(mapping.from)}')">
                            <i class="fas fa-trash"></i>
                          </button>
                        </td>
                      </tr>
                    `).join('')}
                  </tbody>
                </table>
              </div>
            </div>
            <div style="background: var(--surface-2); padding: 20px; border-radius: 8px;">
              <h4 style="margin-bottom: 15px; font-size: 0.95rem;">
                <i class="fas fa-plus"></i> Add New Mapping
              </h4>
              <div class="pair-modal-grid">
                <div class="form-group">
                  <label>From Symbol (e.g. XAUUSD)</label>
                  <input type="text" id="mappingFromSymbol" class="form-input" placeholder="Enter TradingView symbol">
                </div>
                <div class="form-group">
                  <label>To Symbol (e.g. GOLD)</label>
                  <input type="text" id="mappingToSymbol" class="form-input" placeholder="Enter broker symbol">
                </div>
              </div>
              <button class="btn btn-success" onclick="ui.addSymbolMapping()" style="margin-top: 10px;">
                <i class="fas fa-plus"></i> Add Mapping
              </button>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" onclick="ui.closeSymbolMappingModal()">Close</button>
          </div>
        </div>
      `;

      document.body.appendChild(modalEl);
      setTimeout(() => modalEl.classList.add('show'), 10);
    } catch (error) {
      console.error('Error showing symbol mapping modal:', error);
      toast.error('Failed to load symbol mappings');
      loading.hide();
    }
  }

  closeSymbolMappingModal() {
    const modalEl = document.getElementById('symbolMappingModal');
    if (modalEl) {
      modalEl.classList.remove('show');
      setTimeout(() => modalEl.remove(), 300);
    }
  }

  changeSymbolMappingAccount(newAccount) {
    this.closeSymbolMappingModal();
    setTimeout(() => this.showSymbolMappingModal(newAccount), 100);
  }

  async addSymbolMapping() {
    const fromSymbol = document.getElementById('mappingFromSymbol')?.value?.trim().toUpperCase();
    const toSymbol = document.getElementById('mappingToSymbol')?.value?.trim().toUpperCase();

    if (!fromSymbol || !toSymbol) {
      toast.warning('Please enter both symbols');
      return;
    }

    const accountNumber = document.getElementById('symbolMappingAccountSelect')?.value;
    if (!accountNumber) {
      toast.warning('Please select an account');
      return;
    }

    try {
      loading.show();
      const response = await fetch(`/accounts/${accountNumber}/symbols`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ from_symbol: fromSymbol, to_symbol: toSymbol })
      });
      const data = await response.json();

      if (response.ok) {
        document.getElementById('mappingFromSymbol').value = '';
        document.getElementById('mappingToSymbol').value = '';
        this.closeSymbolMappingModal();
        setTimeout(() => this.showSymbolMappingModal(accountNumber), 100);
        toast.success('Symbol mapping added successfully');
      } else {
        toast.error(data.error || 'Failed to add symbol mapping');
      }
    } catch (error) {
      console.error('Add symbol mapping error:', error);
      toast.error('Failed to add symbol mapping');
    } finally {
      loading.hide();
    }
  }

  async deleteSymbolMappingByIndex(accountNumber, fromSymbol) {
    if (!accountNumber || !fromSymbol) return;

    try {
      loading.show();
      const response = await fetch(
        `/accounts/${encodeURIComponent(accountNumber)}/symbols/${encodeURIComponent(fromSymbol)}`,
        { method: 'DELETE', credentials: 'include' }
      );

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Failed to delete mapping');
      }

      toast.success('Symbol mapping deleted successfully');
      this.closeSymbolMappingModal();
      setTimeout(() => this.showSymbolMappingModal(accountNumber), 300);
    } catch (error) {
      console.error('Delete mapping error:', error);
      toast.error(`Failed to delete: ${error.message}`);
    } finally {
      loading.hide();
    }
  }

  // =====================================================
  // MAPPING OVERVIEW
  // =====================================================

  async showMappingOverview() {
    try {
      loading.show();
      const response = await fetchWithAuth('/accounts/symbols/overview');
      const data = await response.json();

      if (!response.ok) {
        toast.error(data.error || 'Failed to load mapping overview');
        return;
      }

      const modalEl = document.getElementById('mappingOverviewModal');
      const content = document.getElementById('mappingOverviewContent');

      if (!data.data || Object.keys(data.data).length === 0) {
        content.innerHTML = `
          <div style="text-align: center; padding: 40px; color: var(--text-muted);">
            <i class="fas fa-inbox" style="font-size: 48px; margin-bottom: 16px; opacity: 0.5;"></i>
            <p>No symbol mappings configured yet</p>
          </div>
        `;
      } else {
        let html = '<div style="display: grid; gap: 16px;">';
        for (const [account, info] of Object.entries(data.data)) {
          html += `
            <div class="card">
              <div class="card-header" style="padding: 12px 16px;">
                <h4 style="margin: 0; font-size: 16px;">
                  <i class="fas fa-user"></i> ${account}
                  ${info.nickname ? `<span style="color: var(--text-muted); font-weight: normal;"> (${info.nickname})</span>` : ''}
                </h4>
              </div>
              <div class="card-body" style="padding: 12px 16px;">
                <div style="display: grid; gap: 8px;">
          `;
          for (const mapping of info.mappings) {
            html += `
              <div style="display: flex; align-items: center; gap: 12px; padding: 8px 12px; background: var(--card-background); border: 1px solid var(--border-color); border-radius: 6px;">
                <code style="flex: 1; font-size: 14px; color: var(--text-primary);">${mapping.from}</code>
                <i class="fas fa-arrow-right" style="color: var(--text-muted);"></i>
                <code style="flex: 1; font-size: 14px; color: var(--success-color);">${mapping.to}</code>
              </div>
            `;
          }
          html += '</div></div></div>';
        }
        html += '</div>';
        content.innerHTML = html;
      }

      if (modalEl) modalEl.style.display = 'flex';
    } catch (error) {
      console.error('Failed to show mapping overview:', error);
      toast.error('Failed to load mapping overview');
    } finally {
      loading.hide();
    }
  }

  closeMappingOverview() {
    const modalEl = document.getElementById('mappingOverviewModal');
    if (modalEl) modalEl.style.display = 'none';
  }

  closeSymbolMappingOverview() {
    const modalEl = document.getElementById('symbolMappingModal');
    if (modalEl) {
      modalEl.classList.remove('show');
      setTimeout(() => modalEl.remove(), 300);
    }
  }

  // =====================================================
  // MODAL HELPERS
  // =====================================================

  closeModal() { modal.close(); }
  confirmAction() { modal.confirm(); }
  showLoading() { loading.show(); }
  hideLoading() { loading.hide(); }

  showToast(message, type = 'info', duration = 5000) {
    toast.show(message, type, duration);
  }

  async showConfirmDialog(title, message) {
    return modal.showConfirm(title, message);
  }

  // =====================================================
  // DELEGATE TO MODULES
  // =====================================================

  // Account Management
  async loadData() { return accountsModule.loadData(); }
  async loadAccountManagementData() { return accountsModule.loadAccountManagementData(); }
  async addAccountAM() { return accountsModule.addAccountAM(); }
  async addAccount() { return accountsModule.addAccount(); }
  async performAccountActionAM(account, action) { return accountsModule.performAccountActionAM(account, action); }
  async performAccountAction(account, action) { return accountsModule.performAccountAction(account, action); }
  filterTableAM(searchTerm) { return accountsModule.filterTableAM(searchTerm); }
  filterTable(searchTerm) { return accountsModule.filterTable(searchTerm); }
  updateAccountFilterOptions() { return accountsModule.updateAccountFilterOptions(); }
  async addAccountFromServer() { return accountsModule.addAccountFromServer?.(); }

  // Copy Trading
  async loadCopyPairs() { return copyTradingModule.loadCopyPairs(); }
  async loadMasterAccounts() { return copyTradingModule.loadMasterAccounts(); }
  async loadSlaveAccounts() { return copyTradingModule.loadSlaveAccounts(); }
  async loadCopyHistory() { return copyTradingModule.loadCopyHistory(); }
  async addMasterAccount() { return copyTradingModule.addMasterAccount(); }
  async addSlaveAccount() { return copyTradingModule.addSlaveAccount(); }
  async deleteMasterAccount(id) { return copyTradingModule.deleteMasterAccount(id); }
  async deleteSlaveAccount(id) { return copyTradingModule.deleteSlaveAccount(id); }
  showCreatePairModal() { return copyTradingModule.showCreatePairModal(); }
  closeCreatePairModal() { return copyTradingModule.closeCreatePairModal(); }
  async confirmCreatePair() { return copyTradingModule.confirmCreatePair(); }
  async togglePlanStatus(id) { return copyTradingModule.togglePlanStatus(id); }
  async deletePlan(id) { return copyTradingModule.deletePlan(id); }
  async clearCopyHistory() { return copyTradingModule.clearCopyHistory(); }
  renderMasterAccounts() { return copyTradingModule.renderMasterAccounts(); }
  renderSlaveAccounts() { return copyTradingModule.renderSlaveAccounts(); }
  renderCopyPairs() { return copyTradingModule.renderCopyPairs(); }
  renderPlans() { return copyTradingModule.renderPlans(); }
  renderActivePairsTable() { return copyTradingModule.renderActivePairsTable(); }
  renderCopyHistory() { return copyTradingModule.renderCopyHistory(); }
  updatePairCount() { return copyTradingModule.updatePairCount(); }
  addPlan() { return copyTradingModule.showCreatePairModal(); }

  // Edit Pair Functions
  editPlan(id) { return copyTradingModule.editPlan(id); }
  showEditPairModal(plan) { return copyTradingModule.showEditPairModal(plan); }
  closeEditPairModal() { return copyTradingModule.closeEditPairModal(); }
  confirmEditPair(id) { return copyTradingModule.confirmEditPair(id); }

  // Add Account to Pair Functions
  showAddAccountModal(pairId) { return copyTradingModule.showAddAccountModal(pairId); }
  closeAddAccountModal() { return copyTradingModule.closeAddAccountModal(); }
  showAddMasterToPair(pairId) { return copyTradingModule.showAddMasterToPair(pairId); }
  closeAddMasterModal() { return copyTradingModule.closeAddMasterModal(); }
  async confirmAddMaster(pairId) { return copyTradingModule.confirmAddMaster(pairId); }
  showAddSlaveToPair(pairId) { return copyTradingModule.showAddSlaveToPair(pairId); }
  closeAddSlaveModal() { return copyTradingModule.closeAddSlaveModal(); }
  async confirmAddSlave(pairId) { return copyTradingModule.confirmAddSlave(pairId); }

  // Filter Functions
  filterPairsBySearch() { return copyTradingModule.filterPairsBySearch(); }

  async toggleCopyPair(id, status) {
    const action = status === 'active' ? 'stop' : 'start';
    try {
      const res = await fetch(`/api/pairs/${id}/${action}`, { method: 'POST' });
      if (res.ok) {
        toast.success(`Copy pair ${action}ed successfully`);
        copyTradingModule.loadCopyPairs();
      }
    } catch (e) {
      toast.error(`Failed to ${action} copy pair`);
    }
  }
  async deletePair(id) { return copyTradingModule.deletePlan(id); }

  // History
  renderHistory() { return historyModule.renderHistory(); }
  async clearHistory() { return historyModule.clearHistory(); }

  // Settings
  async loadAllSettings() { return settingsModule.loadAllSettings(); }
  async loadEmailSettings() { return settingsModule.loadEmailSettings(); }
  toggleEmailConfig() { return settingsModule.toggleEmailConfig(); }
  togglePasswordVisibility() { return settingsModule.togglePasswordVisibility(); }
  async saveEmailSettings() { return settingsModule.saveEmailSettings(); }
  async testEmailSettings() { return settingsModule.testEmailSettings(); }
  async saveRateLimitSettings() { return settingsModule.saveRateLimitSettings(); }
  async resetRateLimitSettings() { return settingsModule.resetRateLimitSettings(); }
  toggleEmailFields() { return settingsModule.toggleEmailConfig(); }
  sendTestEmail() { return settingsModule.testEmailSettings(); }

  // System Logs
  async loadSystemLogs() { return systemLogsModule.loadSystemLogs(); }
  renderSystemLogs() { return systemLogsModule.renderSystemLogs(); }
  async clearSystemLogs() { return systemLogsModule.clearSystemLogs(); }

  // Navigation
  switchPage(page) { return navigation.switchTo(page); }

  // Escape helper
  escape(text) { return escape(text); }

  // =====================================================
  // CLEANUP
  // =====================================================

  cleanup() {
    appState.cleanup();
    sseService.unsubscribeAll();
  }
}

// =====================================================
// GLOBAL HELPER FUNCTIONS
// =====================================================

function showExample(i) { if (window.ui) window.ui.showExample(i); }
function copyExample() { if (window.ui) window.ui.copyExample(); }
function copyWebhookUrl() { if (window.ui) window.ui.copyWebhookUrl(); }
function closeModal() { if (window.ui) window.ui.closeModal(); }
function confirmAction() { if (window.ui) window.ui.confirmAction(); }

// =====================================================
// INITIALIZATION
// =====================================================

document.addEventListener('DOMContentLoaded', () => {
  window.ui = new TradingBotUI();
});

window.addEventListener('beforeunload', () => {
  if (window.ui) window.ui.cleanup();
});

// Export for ES modules
export { TradingBotUI };
export default TradingBotUI;

