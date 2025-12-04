/**
 * @file copyTrading.js
 * @description Copy Trading module - Master/Slave account management
 * @module modules/copyTrading
 */

import appState from '../config/state.js';
import { CopyTradingAPI } from '../services/api.js';
import toast from '../services/toast.js';
import modal from '../services/modal.js';
import loading from '../controllers/loading.js';
import { escape, formatPrice, formatVolume, formatActionBadge } from '../utils/helpers.js';
import { UI_CONFIG } from '../config/constants.js';

/**
 * Copy Trading Module
 */
class CopyTradingModule {

  // =====================================================
  // DATA LOADING
  // =====================================================

  /**
   * Load all copy pairs from server
   */
  async loadCopyPairs() {
    try {
      const data = await CopyTradingAPI.getPairs();
      appState.setCopyPairs(data.pairs || []);

      // Sync with plans for legacy UI
      const plans = (appState.copyPairs || []).map(pair => ({
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
      appState.setPlans(plans);

      // Auto-cleanup deleted accounts
      await this.cleanupDeletedAccounts();

      // Update UI
      this.renderCopyPairs();
      this.renderPlans();
      this.renderActivePairsTable();
    } catch (e) {
      console.error('Load pairs error:', e);
      toast.error('Failed to load copy trading pairs');
    }
  }

  /**
   * Load master accounts from server
   */
  async loadMasterAccounts() {
    try {
      const data = await CopyTradingAPI.getMasterAccounts();
      const accounts = (data.accounts || []).map(acc => ({
        id: acc.id,
        accountNumber: acc.account,
        nickname: acc.nickname || ''
      }));
      appState.setMasterAccounts(accounts);
      console.log('[LOAD] Master accounts loaded:', accounts.length);
    } catch (error) {
      console.error('[LOAD] Failed to load master accounts:', error);
      appState.setMasterAccounts([]);
    }
  }

  /**
   * Load slave accounts from server
   */
  async loadSlaveAccounts() {
    try {
      const data = await CopyTradingAPI.getSlaveAccounts();
      const accounts = (data.accounts || []).map(acc => ({
        id: acc.id,
        accountNumber: acc.account,
        nickname: acc.nickname || ''
      }));
      appState.setSlaveAccounts(accounts);
      console.log('[LOAD] Slave accounts loaded:', accounts.length);
    } catch (error) {
      console.error('[LOAD] Failed to load slave accounts:', error);
      appState.setSlaveAccounts([]);
    }
  }

  /**
   * Load copy history
   */
  async loadCopyHistory() {
    try {
      const data = await CopyTradingAPI.getHistory(100);
      appState.setCopyHistory(data.history || []);
      this.renderCopyHistory();
    } catch (e) {
      console.error('Load history error:', e);
    }
  }

  /**
   * Cleanup deleted accounts from master/slave lists
   */
  async cleanupDeletedAccounts() {
    try {
      const accounts = appState.getAccounts();
      const serverAccountNumbers = new Set(accounts.map(a => String(a.account)));

      // Check Master Accounts
      let masterChanged = false;
      const validMasters = appState.masterAccounts.filter(m => {
        const exists = serverAccountNumbers.has(String(m.accountNumber));
        if (!exists) {
          console.log(`[CLEANUP] Removing deleted master account: ${m.accountNumber}`);
          masterChanged = true;
        }
        return exists;
      });

      if (masterChanged) {
        appState.setMasterAccounts(validMasters);
        this.renderMasterAccounts();
      }

      // Check Slave Accounts
      let slaveChanged = false;
      const validSlaves = appState.slaveAccounts.filter(s => {
        const exists = serverAccountNumbers.has(String(s.accountNumber));
        if (!exists) {
          console.log(`[CLEANUP] Removing deleted slave account: ${s.accountNumber}`);
          slaveChanged = true;
        }
        return exists;
      });

      if (slaveChanged) {
        appState.setSlaveAccounts(validSlaves);
        this.renderSlaveAccounts();
      }

      if (masterChanged || slaveChanged) {
        this.updatePairCount();
        console.log('[CLEANUP] Removed deleted accounts from Copy Trading page');
      }
    } catch (e) {
      console.error('[CLEANUP] Error during account cleanup:', e);
    }
  }

  // =====================================================
  // MASTER/SLAVE ACCOUNT MANAGEMENT
  // =====================================================

  /**
   * Add master account
   */
  async addMasterAccount() {
    const accountNumber = document.getElementById('masterAccountNumber')?.value?.trim();
    const nickname = document.getElementById('masterNickname')?.value?.trim();

    if (!accountNumber) {
      toast.warning('Please enter master account number');
      return;
    }

    try {
      loading.show();
      const data = await CopyTradingAPI.addMasterAccount(accountNumber, nickname);

      appState.masterAccounts.push({
        id: data.account.id,
        accountNumber: data.account.account,
        nickname: data.account.nickname || ''
      });

      this.renderMasterAccounts();
      this.updatePairCount();

      document.getElementById('masterAccountNumber').value = '';
      document.getElementById('masterNickname').value = '';

      toast.success('Master account added successfully');
    } catch (error) {
      console.error('Failed to add master account:', error);
      toast.error(error.message || 'Failed to add master account');
    } finally {
      loading.hide();
    }
  }

  /**
   * Add slave account
   */
  async addSlaveAccount() {
    const accountNumber = document.getElementById('slaveAccountNumber')?.value?.trim();
    const nickname = document.getElementById('slaveNickname')?.value?.trim();

    if (!accountNumber) {
      toast.warning('Please enter slave account number');
      return;
    }

    try {
      loading.show();
      const data = await CopyTradingAPI.addSlaveAccount(accountNumber, nickname);

      appState.slaveAccounts.push({
        id: data.account.id,
        accountNumber: data.account.account,
        nickname: data.account.nickname || ''
      });

      this.renderSlaveAccounts();
      this.updatePairCount();

      document.getElementById('slaveAccountNumber').value = '';
      document.getElementById('slaveNickname').value = '';

      toast.success('Slave account added successfully');
    } catch (error) {
      console.error('Failed to add slave account:', error);
      toast.error(error.message || 'Failed to add slave account');
    } finally {
      loading.hide();
    }
  }

  /**
   * Delete master account
   */
  async deleteMasterAccount(accountId) {
    const confirmed = await modal.showConfirm(
      'Remove Master Account',
      'Remove this account from Copy Trading? This cannot be undone.'
    );
    if (!confirmed) return;

    try {
      loading.show();
      await CopyTradingAPI.deleteMasterAccount(accountId);

      await this.loadCopyPairs();
      await this.loadMasterAccounts();
      await this.loadSlaveAccounts();
      await this.loadCopyHistory();

      this.renderMasterAccounts();
      this.renderSlaveAccounts();
      this.renderCopyPairs();
      this.updatePairCount();

      toast.success('Master account removed successfully');
    } catch (error) {
      console.error('Failed to delete master account:', error);
      toast.error(error.message || 'Failed to delete master account');
    } finally {
      loading.hide();
    }
  }

  /**
   * Delete slave account
   */
  async deleteSlaveAccount(accountId) {
    const confirmed = await modal.showConfirm(
      'Remove Slave Account',
      'Remove this account from Copy Trading? This cannot be undone.'
    );
    if (!confirmed) return;

    try {
      loading.show();
      await CopyTradingAPI.deleteSlaveAccount(accountId);

      await this.loadCopyPairs();
      await this.loadMasterAccounts();
      await this.loadSlaveAccounts();
      await this.loadCopyHistory();

      this.renderMasterAccounts();
      this.renderSlaveAccounts();
      this.renderCopyPairs();
      this.updatePairCount();

      toast.success('Slave account removed successfully');
    } catch (error) {
      console.error('Failed to delete slave account:', error);
      toast.error(error.message || 'Failed to delete slave account');
    } finally {
      loading.hide();
    }
  }

  // =====================================================
  // PAIR MANAGEMENT
  // =====================================================

  /**
   * Show create pair modal
   */
  showCreatePairModal() {
    if (appState.masterAccounts.length === 0) {
      toast.warning('Please add master accounts first');
      return;
    }

    if (appState.slaveAccounts.length === 0) {
      toast.warning('Please add slave accounts first');
      return;
    }

    const modalHtml = `
      <div id="createPairModal" class="modal-overlay show">
        <div class="modal" style="max-width: 700px;">
          <div class="modal-header">
            <h4><i class="fas fa-plus-circle"></i> Create Copy Trading Pair</h4>
            <button class="modal-close" onclick="ui.closeCreatePairModal()">
              <i class="fas fa-times"></i>
            </button>
          </div>
          <div class="modal-body" style="max-height: 600px; overflow-y: auto;">
            <div class="pair-modal-section">
              <h5 class="pair-modal-section-title">Select Accounts</h5>
              <div class="pair-modal-grid">
                <div class="form-group">
                  <label>Master Account</label>
                  <select id="pairMasterAccount" class="form-input">
                    <option value="">Select master account</option>
                    ${appState.masterAccounts.map(acc => `
                      <option value="${escape(acc.accountNumber)}">
                        ${escape(acc.accountNumber)}${acc.nickname ? ' - ' + escape(acc.nickname) : ''}
                      </option>
                    `).join('')}
                  </select>
                </div>
                <div class="form-group">
                  <label>Slave Account</label>
                  <select id="pairSlaveAccount" class="form-input">
                    <option value="">Select slave account</option>
                    ${appState.slaveAccounts.map(acc => `
                      <option value="${escape(acc.accountNumber)}">
                        ${escape(acc.accountNumber)}${acc.nickname ? ' - ' + escape(acc.nickname) : ''}
                      </option>
                    `).join('')}
                  </select>
                </div>
              </div>
            </div>
            <div class="pair-modal-section">
              <h5 class="pair-modal-section-title"><i class="fas fa-cog"></i> Copy Settings</h5>
              <div class="pair-modal-settings">
                <div class="pair-modal-setting-item">
                  <div class="pair-modal-setting-info">
                    <div class="pair-modal-setting-label">Auto Mapping Symbol</div>
                    <div class="pair-modal-setting-desc">Automatically map symbols between accounts</div>
                  </div>
                  <label class="toggle-switch">
                    <input type="checkbox" id="pairAutoMapSymbol" checked>
                    <span class="toggle-slider"></span>
                  </label>
                </div>
                <div class="pair-modal-setting-item">
                  <div class="pair-modal-setting-info">
                    <div class="pair-modal-setting-label">Auto Mapping Volume</div>
                    <div class="pair-modal-setting-desc">Automatically adjust volume based on settings</div>
                  </div>
                  <label class="toggle-switch">
                    <input type="checkbox" id="pairAutoMapVolume" checked>
                    <span class="toggle-slider"></span>
                  </label>
                </div>
                <div class="pair-modal-setting-item">
                  <div class="pair-modal-setting-info">
                    <div class="pair-modal-setting-label">Copy TP/SL</div>
                    <div class="pair-modal-setting-desc">Copy take profit and stop loss values</div>
                  </div>
                  <label class="toggle-switch">
                    <input type="checkbox" id="pairCopyPSL" checked>
                    <span class="toggle-slider"></span>
                  </label>
                </div>
              </div>
            </div>
            <div class="pair-modal-section">
              <h5 class="pair-modal-section-title">Volume Configuration</h5>
              <div class="pair-modal-grid">
                <div class="form-group">
                  <label>Volume Mode</label>
                  <select id="pairVolumeMode" class="form-input">
                    <option value="multiply">Volume Multiply</option>
                    <option value="fixed">Fixed Volume</option>
                    <option value="percent">Percent of Balance</option>
                  </select>
                </div>
                <div class="form-group">
                  <label>Multiplier</label>
                  <input type="number" id="pairMultiplier" class="form-input" value="2" min="0.01" step="0.01">
                </div>
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" onclick="ui.closeCreatePairModal()">Cancel</button>
            <button class="btn btn-success" onclick="ui.confirmCreatePair()">
              <i class="fas fa-check"></i> Create Pair
            </button>
          </div>
        </div>
      </div>
    `;

    document.getElementById('createPairModal')?.remove();
    document.body.insertAdjacentHTML('beforeend', modalHtml);
  }

  /**
   * Close create pair modal
   */
  closeCreatePairModal() {
    document.getElementById('createPairModal')?.remove();
  }

  /**
   * Confirm create pair
   */
  async confirmCreatePair() {
    const masterAccount = document.getElementById('pairMasterAccount')?.value;
    const slaveAccount = document.getElementById('pairSlaveAccount')?.value;
    const autoMapSymbol = document.getElementById('pairAutoMapSymbol')?.checked;
    const autoMapVolume = document.getElementById('pairAutoMapVolume')?.checked;
    const copyPSL = document.getElementById('pairCopyPSL')?.checked;
    const volumeMode = document.getElementById('pairVolumeMode')?.value || 'multiply';
    const multiplier = parseFloat(document.getElementById('pairMultiplier')?.value || '2');

    if (!masterAccount) { toast.warning('Please select master account'); return; }
    if (!slaveAccount) { toast.warning('Please select slave account'); return; }
    if (masterAccount === slaveAccount) { toast.warning('Master and slave accounts must be different'); return; }

    try {
      loading.show();
      const data = await CopyTradingAPI.createPair({
        master_account: String(masterAccount),
        slave_account: String(slaveAccount),
        settings: {
          auto_map_symbol: !!autoMapSymbol,
          auto_map_volume: !!autoMapVolume,
          copy_psl: !!copyPSL,
          volume_mode: volumeMode,
          multiplier: multiplier
        }
      });

      const pair = data.pair || data.data || data;
      const apiKey = pair.api_key || pair.apiKey || 'N/A';
      toast.success(`Pair created successfully! API Key: ${apiKey.substring(0, 16)}...`);

      this.closeCreatePairModal();
      await this.loadCopyPairs();
      this.renderPlans();
      this.renderActivePairsTable();
    } catch (e) {
      console.error(e);
      toast.error('Create pair failed');
    } finally {
      loading.hide();
    }
  }

  /**
   * Toggle pair status
   */
  async togglePlanStatus(planId) {
    const plan = appState.plans.find(p => p.id === planId);
    if (!plan) {
      toast.error('Pair not found');
      return;
    }

    const currentStatus = plan.status || 'inactive';
    const newStatus = currentStatus === 'active' ? 'inactive' : 'active';
    const actionText = newStatus === 'active' ? 'activate' : 'deactivate';

    const confirmed = await modal.showConfirm(
      `${newStatus === 'active' ? 'Activate' : 'Deactivate'} Copy Pair`,
      `Are you sure you want to ${actionText} this copy trading pair?`
    );
    if (!confirmed) return;

    try {
      loading.show();
      await CopyTradingAPI.togglePair(planId);
      toast.success(`Pair ${newStatus === 'active' ? 'activated' : 'deactivated'} successfully`);
      await this.loadCopyPairs();
      this.renderPlans();
      this.renderActivePairsTable();
    } catch (error) {
      console.error('Toggle plan status error:', error);
      toast.error(error.message || 'Failed to toggle pair status');
    } finally {
      loading.hide();
    }
  }

  /**
   * Delete pair
   */
  async deletePlan(planId) {
    const confirmed = await modal.showConfirm(
      'Delete Copy Trading Pair',
      'Are you sure you want to delete this copy trading pair? This action cannot be undone.'
    );
    if (!confirmed) return;

    try {
      loading.show();
      await CopyTradingAPI.deletePair(planId);

      appState.plans = appState.plans.filter(p => p.id !== planId);
      await this.loadCopyPairs();

      toast.success('Copy trading pair deleted successfully');
    } catch (error) {
      console.error('Delete plan error:', error);
      toast.error(`Failed to delete pair: ${error.message}`);
    } finally {
      loading.hide();
    }
  }

  /**
   * Clear copy history
   */
  async clearCopyHistory() {
    const ok = await modal.showConfirm(
      'Clear Copy History',
      'Delete all copy trading history? This cannot be undone.'
    );
    if (!ok) return;

    try {
      await CopyTradingAPI.clearHistory();
      appState.setCopyHistory([]);
      this.renderCopyHistory();
      await this.loadCopyHistory();
      toast.success('Copy history cleared successfully');
    } catch (e) {
      console.error(e);
      toast.error(`Clear failed: ${e.message}`);
    }
  }

  // =====================================================
  // RENDERING
  // =====================================================

  /**
   * Render master accounts list
   */
  renderMasterAccounts() {
    const container = document.getElementById('masterAccountsList');
    if (!container) return;

    if (!appState.masterAccounts.length) {
      container.innerHTML = `
        <div class="empty-state-small">
          <i class="fas fa-user"></i>
          <p>No master accounts</p>
        </div>`;
      return;
    }

    container.innerHTML = appState.masterAccounts.map(account => {
      const serverAccount = appState.accounts.find(a => String(a.account) === String(account.accountNumber));
      const status = serverAccount?.status || 'Offline';
      const statusClass = status.toLowerCase();

      return `
        <div class="account-card">
          <div class="account-card-info">
            <div class="account-card-number">
              ${escape(account.accountNumber)}
              <span class="status-badge ${statusClass}" style="margin-left: 8px; font-size: 0.75rem;">
                <i class="fas fa-circle"></i> ${status}
              </span>
            </div>
            <div class="account-card-nickname">${escape(account.nickname) || '-'}</div>
          </div>
          <div class="account-card-actions">
            <button class="btn btn-secondary btn-sm" onclick="ui.deleteMasterAccount('${account.id}')" title="Delete">
              <i class="fas fa-trash"></i>
            </button>
          </div>
        </div>
      `;
    }).join('');
  }

  /**
   * Render slave accounts list
   */
  renderSlaveAccounts() {
    const container = document.getElementById('slaveAccountsList');
    if (!container) return;

    if (!appState.slaveAccounts.length) {
      container.innerHTML = `
        <div class="empty-state-small">
          <i class="fas fa-user"></i>
          <p>No slave accounts</p>
        </div>`;
      return;
    }

    container.innerHTML = appState.slaveAccounts.map(account => {
      const serverAccount = appState.accounts.find(a => String(a.account) === String(account.accountNumber));
      const status = serverAccount?.status || 'Offline';
      const statusClass = status.toLowerCase();

      return `
        <div class="account-card">
          <div class="account-card-info">
            <div class="account-card-number">
              ${escape(account.accountNumber)}
              <span class="status-badge ${statusClass}" style="margin-left: 8px; font-size: 0.75rem;">
                <i class="fas fa-circle"></i> ${status}
              </span>
            </div>
            <div class="account-card-nickname">${escape(account.nickname) || '-'}</div>
          </div>
          <div class="account-card-actions">
            <button class="btn btn-secondary btn-sm" onclick="ui.deleteSlaveAccount('${account.id}')" title="Delete">
              <i class="fas fa-trash"></i>
            </button>
          </div>
        </div>
      `;
    }).join('');
  }

  /**
   * Render copy pairs
   */
  renderCopyPairs() {
    const container = document.getElementById('copyPairsList');
    const countBadge = document.getElementById('pairCount');

    if (!container) return;
    if (countBadge) countBadge.textContent = `${appState.copyPairs.length} pairs`;

    if (!appState.copyPairs.length) {
      container.innerHTML = `
        <div class="empty-state">
          <i class="fas fa-clipboard-list"></i>
          <p>No Copy Trading Pairs</p>
          <p class="empty-subtitle">Add your first Copy Trading pair above</p>
        </div>`;
      return;
    }

    container.innerHTML = appState.copyPairs.map(pair => {
      const statusClass = pair.status === 'active' ? 'online' : 'offline';
      const statusText = pair.status === 'active' ? 'Active' : 'Stopped';
      const toggleIcon = pair.status === 'active' ? 'fa-stop' : 'fa-play';
      const toggleText = pair.status === 'active' ? 'Stop' : 'Start';
      const toggleClass = pair.status === 'active' ? 'btn-danger' : 'btn-success';

      return `
        <div class="copy-pair-card">
          <div class="pair-header">
            <span class="status-badge ${statusClass}">${statusText}</span>
            <div class="pair-actions">
              <button class="btn ${toggleClass} btn-sm" onclick="ui.toggleCopyPair('${pair.id}', '${pair.status}')">
                <i class="fas ${toggleIcon}"></i> ${toggleText}
              </button>
              <button class="btn btn-secondary btn-sm" onclick="ui.deletePair('${pair.id}')">
                <i class="fas fa-trash"></i>
              </button>
            </div>
          </div>
          <div class="pair-content">
            <div class="account-info">
              <h5>Master</h5>
              <div class="info-grid">
                <div><strong>Login:</strong> ${escape(pair.master?.login || pair.master_account)}</div>
                <div><strong>Server:</strong> ${escape(pair.master?.server || '-')}</div>
              </div>
            </div>
            <div class="copy-arrow"><i class="fas fa-arrow-right"></i></div>
            <div class="account-info">
              <h5>Slave</h5>
              <div class="info-grid">
                <div><strong>Login:</strong> ${escape(pair.slave?.login || pair.slave_account)}</div>
                <div><strong>Server:</strong> ${escape(pair.slave?.server || '-')}</div>
              </div>
            </div>
          </div>
        </div>`;
    }).join('');
  }

  /**
   * Render plans list
   */
  renderPlans() {
    const container = document.getElementById('plansList');
    if (!container) return;

    if (!appState.plans.length) {
      container.innerHTML = `
        <div class="empty-state-small">
          <i class="fas fa-layer-group"></i>
          <p>No copy trading pairs yet</p>
          <p style="font-size: 0.85rem; color: var(--text-dim); margin-top: 8px;">
            Create your first pair to start copy trading
          </p>
        </div>`;
      return;
    }

    container.innerHTML = appState.plans.map(plan => {
      const statusClass = plan.status === 'active' ? 'online' : 'offline';
      const statusText = plan.status === 'active' ? 'Active' : 'Inactive';

      return `
        <div class="plan-item-card" data-plan-id="${escape(plan.id)}">
          <div class="plan-item-header">
            <div class="plan-item-accounts">
              <div class="plan-item-account master">
                <div class="plan-item-account-info">
                  <div class="plan-item-account-number">${escape(plan.masterAccount)}</div>
                  ${plan.masterNickname ? `<div class="plan-item-account-nickname">${escape(plan.masterNickname)}</div>` : ''}
                </div>
              </div>
              <div class="plan-item-arrow"><i class="fas fa-arrow-right"></i></div>
              <div class="plan-item-account slave">
                <i class="fas fa-user"></i>
                <div class="plan-item-account-info">
                  <div class="plan-item-account-number">${escape(plan.slaveAccount)}</div>
                  ${plan.slaveNickname ? `<div class="plan-item-account-nickname">${escape(plan.slaveNickname)}</div>` : ''}
                </div>
              </div>
            </div>
            <span class="status-badge ${statusClass}">${statusText}</span>
          </div>
          <div class="plan-item-details">
            <div class="plan-item-detail">
              <i class="fas fa-cog"></i>
              <span>${plan.settings.volumeMode || 'multiply'}: ${plan.settings.multiplier}x</span>
            </div>
            <div class="plan-item-detail">
              <i class="fas fa-check-circle" style="color: ${plan.settings.autoMapSymbol ? 'var(--success-color)' : 'var(--text-dim)'}"></i>
              <span>Auto Symbol</span>
            </div>
            <div class="plan-item-detail">
              <i class="fas fa-check-circle" style="color: ${plan.settings.copyPSL ? 'var(--success-color)' : 'var(--text-dim)'}"></i>
              <span>Copy TP/SL</span>
            </div>
          </div>
          <div class="plan-item-token">
            <i class="fas fa-key"></i>
            <code>${escape(plan.apiToken)}</code>
            <button class="btn-icon-small" onclick="ui.copyToClipboard('${escape(plan.apiToken)}', 'Token copied!')" title="Copy Token">
              <i class="fas fa-copy"></i>
            </button>
          </div>
          <div class="plan-item-actions">
            <button class="btn btn-success btn-sm" onclick="ui.showAddAccountModal('${plan.id}')" title="Add Account to Pair">
              <i class="fas fa-plus"></i>
            </button>
            <button class="btn btn-${plan.status === 'active' ? 'warning' : 'success'} btn-sm" onclick="ui.togglePlanStatus('${plan.id}')" title="${plan.status === 'active' ? 'Deactivate' : 'Activate'}">
              <i class="fas fa-${plan.status === 'active' ? 'pause' : 'play'}"></i>
            </button>
            <button class="btn btn-info btn-sm" onclick="ui.editPlan('${plan.id}')" title="Edit">
              <i class="fas fa-edit"></i>
            </button>
            <button class="btn btn-danger btn-sm" onclick="ui.deletePlan('${plan.id}')" title="Delete">
              <i class="fas fa-trash"></i>
            </button>
          </div>
        </div>
      `;
    }).join('');

    this.renderActivePairsTable();
  }

  /**
   * Render active pairs table
   */
  renderActivePairsTable() {
    const tbody = document.getElementById('activePairsTableBody');
    const countBadge = document.getElementById('activePairsCount');

    if (!tbody) return;

    const activePlans = appState.plans.filter(p => p.status === 'active');

    if (countBadge) {
      countBadge.textContent = `${activePlans.length} active pair${activePlans.length !== 1 ? 's' : ''}`;
    }

    if (!activePlans.length) {
      tbody.innerHTML = `
        <tr class="no-data"><td colspan="7">
          <div class="no-data-message">
            <i class="fas fa-link"></i>
            <p>No active copy trading pairs</p>
            <p class="empty-subtitle">Create and activate a pair above to see it here</p>
          </div>
        </td></tr>`;
      return;
    }

    tbody.innerHTML = activePlans.map(plan => {
      const masterServerAccount = appState.accounts.find(a => String(a.account) === String(plan.masterAccount));
      const slaveServerAccount = appState.accounts.find(a => String(a.account) === String(plan.slaveAccount));

      const masterStatus = masterServerAccount?.status || 'Unknown';
      const slaveStatus = slaveServerAccount?.status || 'Unknown';
      const masterStatusClass = masterStatus.toLowerCase();
      const slaveStatusClass = slaveStatus.toLowerCase();

      const masterInfo = `${escape(plan.masterAccount)}${plan.masterNickname ? ' (' + escape(plan.masterNickname) + ')' : ''}`;
      const slaveInfo = `${escape(plan.slaveAccount)}${plan.slaveNickname ? ' (' + escape(plan.slaveNickname) + ')' : ''}`;

      return `
        <tr>
          <td>
            <div class="pair-table-cell">
              <div class="pair-table-master"><strong>${masterInfo}</strong>
                <span class="status-badge ${masterStatusClass}" style="margin-left: 8px; font-size: 0.7rem;">
                  <i class="fas fa-circle"></i> ${masterStatus}
                </span>
              </div>
              <div class="pair-table-arrow">
                <i class="fas fa-arrow-right" style="color: var(--primary-color);"></i>
              </div>
              <div class="pair-table-slave"><strong>${slaveInfo}</strong>
                <span class="status-badge ${slaveStatusClass}" style="margin-left: 8px; font-size: 0.7rem;">
                  <i class="fas fa-circle"></i> ${slaveStatus}
                </span>
              </div>
            </div>
          </td>
          <td>
            <div class="pair-table-toggle">
              <label class="toggle-switch-small">
                <input type="checkbox" ${plan.settings.autoMapSymbol ? 'checked' : ''} disabled>
                <span class="toggle-slider-small"></span>
              </label>
              <span class="toggle-label">${plan.settings.autoMapSymbol ? 'ON' : 'OFF'}</span>
            </div>
          </td>
          <td>
            <div class="pair-table-toggle">
              <label class="toggle-switch-small">
                <input type="checkbox" ${plan.settings.autoMapVolume ? 'checked' : ''} disabled>
                <span class="toggle-slider-small"></span>
              </label>
              <span class="toggle-label">${plan.settings.autoMapVolume ? 'ON' : 'OFF'}</span>
            </div>
          </td>
          <td>
            <div class="pair-table-toggle">
              <label class="toggle-switch-small">
                <input type="checkbox" ${plan.settings.copyPSL ? 'checked' : ''} disabled>
                <span class="toggle-slider-small"></span>
              </label>
              <span class="toggle-label">${plan.settings.copyPSL ? 'ON' : 'OFF'}</span>
            </div>
          </td>
          <td>
            <span class="volume-mode-badge">
              ${escape(plan.settings.volumeMode || 'multiply')} ×${plan.settings.multiplier}
            </span>
          </td>
          <td>
            <div class="api-token-cell">
              <code>${escape(plan.apiToken)}</code>
              <button class="btn-icon-small" onclick="ui.copyToClipboard('${escape(plan.apiToken)}', 'Token copied!')" title="Copy Token">
                <i class="fas fa-copy"></i>
              </button>
            </div>
          </td>
          <td>
            <div class="action-buttons">
              <button class="btn btn-info btn-sm" onclick="ui.editPlan('${plan.id}')" title="Settings">
                <i class="fas fa-cog"></i>
              </button>
              <button class="btn btn-danger btn-sm" onclick="ui.togglePlanStatus('${plan.id}')" title="Deactivate">
                <i class="fas fa-power-off"></i>
              </button>
            </div>
          </td>
        </tr>`;
    }).join('');
  }

  /**
   * Render copy history
   */
  renderCopyHistory() {
    const tbody = document.getElementById('copyHistoryTableBody');
    if (!tbody) return;

    const statusFilter = document.getElementById('copyHistoryFilter')?.value || 'all';
    const accountFilter = document.getElementById('copyAccountFilter')?.value || 'all';

    const list = appState.copyHistory.filter(item => {
      if (statusFilter === 'success' && item.status !== 'success') return false;
      if (statusFilter === 'error' && item.status !== 'error') return false;
      if (accountFilter !== 'all') {
        if (item.master !== accountFilter && item.slave !== accountFilter) return false;
      }
      return true;
    });

    if (!list.length) {
      tbody.innerHTML = `
        <tr class="no-data">
          <td colspan="11">
            <div class="no-data-message">
              <i class="fas fa-clock-rotate-left"></i>
              <p>No Copy Trading history yet</p>
              <p class="empty-subtitle">History will appear when pairs are active</p>
            </div>
          </td>
        </tr>`;
      return;
    }

    tbody.innerHTML = list.map(item => {
      const badge = item.status === 'success' ? 'online' : 'offline';
      const time = new Date(item.timestamp).toLocaleString();
      const price = formatPrice(item.price);
      const tp = formatPrice(item.tp);
      const sl = formatPrice(item.sl);
      const volume = formatVolume(item.volume);

      let displayMessage = '-';
      if (item.message) {
        const cleanMessage = String(item.message).replace(/[✅❌⚠️🔥]/g, '').trim();
        if (item.status === 'error') {
          displayMessage = `<span class="error-message">${escape(cleanMessage)}</span>`;
        } else {
          displayMessage = escape(cleanMessage);
        }
      }

      return `
        <tr>
          <td><span class="status-badge ${badge}">${item.status}</span></td>
          <td>${escape(item.master)}</td>
          <td>${escape(item.slave)}</td>
          <td>${formatActionBadge(item.action)}</td>
          <td>${escape(item.symbol)}</td>
          <td>${price}</td>
          <td>${tp}</td>
          <td>${sl}</td>
          <td>${volume}</td>
          <td>${displayMessage}</td>
          <td>${escape(time)}</td>
        </tr>`;
    }).join('');
  }

  /**
   * Update pair count badge
   */
  updatePairCount() {
    const badge = document.getElementById('pairCount');
    if (badge) {
      const total = appState.masterAccounts.length + appState.slaveAccounts.length;
      badge.textContent = `${total} accounts`;
    }
  }

  /**
   * Update copy account filter options
   */
  updateCopyAccountFilterOptions() {
    const sel = document.getElementById('copyAccountFilter');
    if (!sel) return;

    const current = sel.value || 'all';
    const masters = appState.copyHistory.map(h => h.master).filter(a => a && a !== '-');
    const slaves = appState.copyHistory.map(h => h.slave).filter(a => a && a !== '-');
    const allAccounts = Array.from(new Set([...masters, ...slaves])).sort();

    const html = ['<option value="all">All Accounts</option>']
      .concat(allAccounts.map(acc => `<option value="${escape(acc)}">${escape(acc)}</option>`))
      .join('');

    sel.innerHTML = html;
    if ([...sel.options].some(o => o.value === current)) {
      sel.value = current;
    } else {
      sel.value = 'all';
    }
  }

  /**
   * Add copy event to history
   */
  addCopyToHistory(item) {
    const norm = {
      id: item.id || String(Date.now()),
      status: (item.status || '').toLowerCase() === 'error' ? 'error' : 'success',
      master: item.master || '-',
      slave: item.slave || '-',
      action: item.action || '-',
      symbol: item.symbol || '-',
      volume: item.volume ?? '',
      price: item.price ?? '',
      tp: item.tp ?? '',
      sl: item.sl ?? '',
      message: item.message || '',
      timestamp: item.timestamp || new Date().toISOString()
    };

    appState.addToCopyHistory(norm);
    appState.trimCopyHistory(UI_CONFIG.MAX_COPY_HISTORY);
    this.updateCopyAccountFilterOptions();
    this.renderCopyHistory();
  }

  // =====================================================
  // EDIT PAIR FUNCTIONS
  // =====================================================

  /**
   * Edit a plan
   */
  editPlan(planId) {
    const plan = appState.plans.find(p => p.id === planId);
    if (!plan) return;
    this.showEditPairModal(plan);
  }

  /**
   * Show edit pair modal
   */
  showEditPairModal(plan) {
    const modalHtml = `
      <div id="editPairModal" class="modal-overlay show">
        <div class="modal" style="max-width: 700px;">
          <div class="modal-header">
            <h4><i class="fas fa-edit"></i> Edit Copy Trading Pair</h4>
            <button class="modal-close" onclick="ui.closeEditPairModal()">
              <i class="fas fa-times"></i>
            </button>
          </div>
          <div class="modal-body" style="max-height: 600px; overflow-y: auto;">
            <div class="pair-modal-section">
              <h5 class="pair-modal-section-title">Select Accounts</h5>
              <div class="pair-modal-grid">
                <div class="form-group">
                  <label>Master Account</label>
                  <select id="editPairMasterAccount" class="form-input">
                    <option value="">Select master account</option>
                    ${appState.masterAccounts.map(acc => `
                      <option value="${escape(acc.accountNumber)}" ${acc.accountNumber === plan.masterAccount ? 'selected' : ''}>
                        ${escape(acc.accountNumber)}${acc.nickname ? ' - ' + escape(acc.nickname) : ''}
                      </option>
                    `).join('')}
                  </select>
                </div>
                <div class="form-group">
                  <label>Slave Account</label>
                  <select id="editPairSlaveAccount" class="form-input">
                    <option value="">Select slave account</option>
                    ${appState.slaveAccounts.map(acc => `
                      <option value="${escape(acc.accountNumber)}" ${acc.accountNumber === plan.slaveAccount ? 'selected' : ''}>
                        ${escape(acc.accountNumber)}${acc.nickname ? ' - ' + escape(acc.nickname) : ''}
                      </option>
                    `).join('')}
                  </select>
                </div>
              </div>
            </div>
            <div class="pair-modal-section">
              <h5 class="pair-modal-section-title"><i class="fas fa-cog"></i> Copy Settings</h5>
              <div class="pair-modal-settings">
                <div class="pair-modal-setting-item">
                  <div class="pair-modal-setting-info">
                    <div class="pair-modal-setting-label">Auto Mapping Symbol</div>
                    <div class="pair-modal-setting-desc">Automatically map symbols between accounts</div>
                  </div>
                  <label class="toggle-switch">
                    <input type="checkbox" id="editPairAutoMapSymbol" ${plan.settings.autoMapSymbol ? 'checked' : ''}>
                    <span class="toggle-slider"></span>
                  </label>
                </div>
                <div class="pair-modal-setting-item">
                  <div class="pair-modal-setting-info">
                    <div class="pair-modal-setting-label">Auto Mapping Volume</div>
                    <div class="pair-modal-setting-desc">Automatically adjust volume based on settings</div>
                  </div>
                  <label class="toggle-switch">
                    <input type="checkbox" id="editPairAutoMapVolume" ${plan.settings.autoMapVolume ? 'checked' : ''}>
                    <span class="toggle-slider"></span>
                  </label>
                </div>
                <div class="pair-modal-setting-item">
                  <div class="pair-modal-setting-info">
                    <div class="pair-modal-setting-label">Copy TP/SL</div>
                    <div class="pair-modal-setting-desc">Copy take profit and stop loss values</div>
                  </div>
                  <label class="toggle-switch">
                    <input type="checkbox" id="editPairCopyPSL" ${plan.settings.copyPSL ? 'checked' : ''}>
                    <span class="toggle-slider"></span>
                  </label>
                </div>
              </div>
            </div>
            <div class="pair-modal-section">
              <h5 class="pair-modal-section-title">Volume Configuration</h5>
              <div class="pair-modal-grid">
                <div class="form-group">
                  <label>Volume Mode</label>
                  <select id="editPairVolumeMode" class="form-input">
                    <option value="multiply" ${plan.settings.volumeMode === 'multiply' ? 'selected' : ''}>Volume Multiply</option>
                    <option value="fixed" ${plan.settings.volumeMode === 'fixed' ? 'selected' : ''}>Fixed Volume</option>
                    <option value="percent" ${plan.settings.volumeMode === 'percent' ? 'selected' : ''}>Percent of Balance</option>
                  </select>
                </div>
                <div class="form-group">
                  <label>Multiplier</label>
                  <input type="number" id="editPairMultiplier" class="form-input" value="${plan.settings.multiplier || 2}" min="0.01" step="0.01">
                </div>
              </div>
            </div>
            <div class="pair-modal-section">
              <h5 class="pair-modal-section-title" style="color: var(--success-color);">
                <i class="fas fa-check-circle"></i> API Token
              </h5>
              <div class="form-group">
                <div class="token-input-group">
                  <input type="text" id="editPairApiToken" class="form-input" readonly value="${escape(plan.apiToken)}" style="font-family: monospace;">
                  <button class="btn btn-info btn-sm" onclick="ui.copyToClipboard(document.getElementById('editPairApiToken').value, 'Token copied!')" title="Copy Token">
                    <i class="fas fa-copy"></i>
                  </button>
                </div>
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" onclick="ui.closeEditPairModal()">Cancel</button>
            <button class="btn btn-success" onclick="ui.confirmEditPair('${plan.id}')">
              <i class="fas fa-check"></i> Save Changes
            </button>
          </div>
        </div>
      </div>
    `;

    document.getElementById('editPairModal')?.remove();
    document.body.insertAdjacentHTML('beforeend', modalHtml);
  }

  /**
   * Close edit pair modal
   */
  closeEditPairModal() {
    const modal = document.getElementById('editPairModal');
    if (modal) modal.remove();
  }

  /**
   * Confirm edit pair
   */
  confirmEditPair(planId) {
    const masterAccount = document.getElementById('editPairMasterAccount')?.value;
    const slaveAccount = document.getElementById('editPairSlaveAccount')?.value;
    const autoMapSymbol = document.getElementById('editPairAutoMapSymbol')?.checked;
    const autoMapVolume = document.getElementById('editPairAutoMapVolume')?.checked;
    const copyPSL = document.getElementById('editPairCopyPSL')?.checked;
    const volumeMode = document.getElementById('editPairVolumeMode')?.value;
    const multiplier = document.getElementById('editPairMultiplier')?.value;

    if (!masterAccount) { toast.warning('Please select master account'); return; }
    if (!slaveAccount) { toast.warning('Please select slave account'); return; }
    if (masterAccount === slaveAccount) { toast.warning('Master and slave accounts must be different'); return; }

    const planIndex = appState.plans.findIndex(p => p.id === planId);
    if (planIndex === -1) { toast.error('Plan not found'); return; }

    const masterDetails = appState.masterAccounts.find(a => a.accountNumber === masterAccount);
    const slaveDetails = appState.slaveAccounts.find(a => a.accountNumber === slaveAccount);

    appState.plans[planIndex] = {
      ...appState.plans[planIndex],
      masterAccount,
      slaveAccount,
      masterNickname: masterDetails?.nickname || '',
      slaveNickname: slaveDetails?.nickname || '',
      settings: {
        autoMapSymbol: !!autoMapSymbol,
        autoMapVolume: !!autoMapVolume,
        copyPSL: !!copyPSL,
        volumeMode: volumeMode || 'multiply',
        multiplier: parseFloat(multiplier) || 2
      }
    };

    this.savePlans();
    this.renderPlans();
    this.renderActivePairsTable();
    this.closeEditPairModal();
    toast.success('Copy trading pair updated successfully!');
  }

  /**
   * Save plans to localStorage
   */
  savePlans() {
    localStorage.setItem('mt5_plans', JSON.stringify(appState.plans));
  }

  /**
   * Load plans from localStorage
   */
  loadPlans() {
    const saved = localStorage.getItem('mt5_plans');
    if (saved) {
      try {
        appState.setPlans(JSON.parse(saved));
      } catch (e) {
        console.error('Failed to load plans from localStorage:', e);
      }
    }
  }

  // =====================================================
  // ADD ACCOUNT TO PAIR FUNCTIONS
  // =====================================================

  /**
   * Show add account modal
   */
  showAddAccountModal(pairId) {
    const pair = appState.copyPairs.find(p => p.id === pairId);
    if (!pair) {
      toast.error('Pair not found');
      return;
    }

    const modal = document.createElement('div');
    modal.id = 'addAccountModal';
    modal.className = 'modal-overlay';
    modal.innerHTML = `
      <div class="modal" style="max-width: 500px;">
        <div class="modal-header">
          <h3><i class="fas fa-user-plus"></i> Add Account to Pair</h3>
          <button class="modal-close" onclick="ui.closeAddAccountModal()">
            <i class="fas fa-times"></i>
          </button>
        </div>
        <div class="modal-body">
          <div style="text-align: center; margin-bottom: 20px;">
            <p style="color: var(--text-dim); margin-bottom: 15px;">
              Current API Key: <strong>${pair.apiKey || pair.api_key}</strong>
            </p>
          </div>
          <div class="button-group" style="display: flex; gap: 15px; flex-direction: column;">
            <button class="btn btn-success btn-lg" onclick="ui.showAddMasterToPair('${pairId}')" 
                    style="padding: 20px; display: flex; align-items: center; gap: 15px; text-align: left;">
              <div style="flex: 1;">
                <div style="font-size: 1.1rem; font-weight: 600; margin-bottom: 5px;">Add Master Account</div>
                <div style="font-size: 0.85rem; opacity: 0.9;">Add another master to this pair</div>
              </div>
            </button>
            <button class="btn btn-primary btn-lg" onclick="ui.showAddSlaveToPair('${pairId}')" 
                    style="padding: 20px; display: flex; align-items: center; gap: 15px; text-align: left;">
              <div style="flex: 1;">
                <div style="font-size: 1.1rem; font-weight: 600; margin-bottom: 5px;">Add Slave Account</div>
                <div style="font-size: 0.85rem; opacity: 0.9;">Add slave with settings configuration</div>
              </div>
            </button>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
    setTimeout(() => modal.classList.add('show'), 10);
  }

  /**
   * Close add account modal
   */
  closeAddAccountModal() {
    const modal = document.getElementById('addAccountModal');
    if (modal) {
      modal.classList.remove('show');
      setTimeout(() => modal.remove(), 300);
    }
  }

  /**
   * Show add master to pair modal
   */
  showAddMasterToPair(pairId) {
    this.closeAddAccountModal();

    const modal = document.createElement('div');
    modal.id = 'addMasterModal';
    modal.className = 'modal-overlay';
    modal.innerHTML = `
      <div class="modal" style="max-width: 500px;">
        <div class="modal-header">
          <h3>Add Master to Pair</h3>
          <button class="modal-close" onclick="ui.closeAddMasterModal()">
            <i class="fas fa-times"></i>
          </button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label>Select Master Account</label>
            <select id="addMasterSelect" class="form-input">
              <option value="">-- Select Account --</option>
              ${appState.masterAccounts.map(acc => `
                <option value="${acc.accountNumber}">
                  ${acc.accountNumber} ${acc.nickname ? '(' + acc.nickname + ')' : ''}
                </option>
              `).join('')}
            </select>
          </div>
          <div class="modal-actions">
            <button class="btn btn-secondary" onclick="ui.closeAddMasterModal()">Cancel</button>
            <button class="btn btn-success" onclick="ui.confirmAddMaster('${pairId}')">
              <i class="fas fa-plus"></i> Add Master
            </button>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
    setTimeout(() => modal.classList.add('show'), 10);
  }

  /**
   * Close add master modal
   */
  closeAddMasterModal() {
    const modal = document.getElementById('addMasterModal');
    if (modal) {
      modal.classList.remove('show');
      setTimeout(() => modal.remove(), 300);
    }
  }

  /**
   * Confirm add master to pair
   */
  async confirmAddMaster(pairId) {
    const masterAccount = document.getElementById('addMasterSelect')?.value;

    if (!masterAccount) {
      toast.warning('Please select a master account');
      return;
    }

    try {
      loading.show();
      await CopyTradingAPI.addMaster(pairId, masterAccount);
      toast.success('Master account added successfully');
      this.closeAddMasterModal();
      await this.loadCopyPairs();
      this.renderPlans();
      this.renderActivePairsTable();
    } catch (error) {
      console.error('Add master error:', error);
      toast.error('Failed to add master account');
    } finally {
      loading.hide();
    }
  }

  /**
   * Show add slave to pair modal
   */
  showAddSlaveToPair(pairId) {
    this.closeAddAccountModal();

    const pair = appState.copyPairs.find(p => p.id === pairId);
    const settings = pair?.settings || {};

    const modal = document.createElement('div');
    modal.id = 'addSlaveModal';
    modal.className = 'modal-overlay';
    modal.innerHTML = `
      <div class="modal" style="max-width: 600px;">
        <div class="modal-header">
          <h3>Add Slave to Pair</h3>
          <button class="modal-close" onclick="ui.closeAddSlaveModal()">
            <i class="fas fa-times"></i>
          </button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label>Select Slave Account</label>
            <select id="addSlaveSelect" class="form-input">
              <option value="">-- Select Account --</option>
              ${appState.slaveAccounts.map(acc => `
                <option value="${acc.accountNumber}">
                  ${acc.accountNumber} ${acc.nickname ? '(' + acc.nickname + ')' : ''}
                </option>
              `).join('')}
            </select>
          </div>
          <div class="settings-section" style="background: var(--surface-2); padding: 15px; border-radius: 8px; margin-top: 20px;">
            <h4 style="margin-bottom: 15px; font-size: 0.95rem;"><i class="fas fa-cog"></i> Copy Settings</h4>
            <div class="form-group">
              <label class="checkbox-label">
                <input type="checkbox" id="addSlaveAutoMapSymbol" ${settings.auto_map_symbol !== false ? 'checked' : ''}>
                <span>Auto Map Symbol</span>
              </label>
            </div>
            <div class="form-group">
              <label class="checkbox-label">
                <input type="checkbox" id="addSlaveAutoMapVolume" ${settings.auto_map_volume !== false ? 'checked' : ''}>
                <span>Auto Map Volume</span>
              </label>
            </div>
            <div class="form-group">
              <label class="checkbox-label">
                <input type="checkbox" id="addSlaveCopyPSL" ${settings.copy_psl !== false ? 'checked' : ''}>
                <span>Copy TP/SL</span>
              </label>
            </div>
            <div class="form-group">
              <label>Volume Mode</label>
              <select id="addSlaveVolumeMode" class="form-input">
                <option value="multiply" ${settings.volume_mode === 'multiply' ? 'selected' : ''}>Multiply</option>
                <option value="fixed" ${settings.volume_mode === 'fixed' ? 'selected' : ''}>Fixed</option>
                <option value="percent" ${settings.volume_mode === 'percent' ? 'selected' : ''}>Percent</option>
              </select>
            </div>
            <div class="form-group">
              <label>Multiplier / Fixed Volume / Percent</label>
              <input type="number" id="addSlaveMultiplier" class="form-input" value="${settings.multiplier || 2}" step="0.01" min="0.01">
            </div>
          </div>
          <div class="modal-actions" style="margin-top: 20px;">
            <button class="btn btn-secondary" onclick="ui.closeAddSlaveModal()">Cancel</button>
            <button class="btn btn-success" onclick="ui.confirmAddSlave('${pairId}')">
              <i class="fas fa-plus"></i> Add Slave
            </button>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
    setTimeout(() => modal.classList.add('show'), 10);
  }

  /**
   * Close add slave modal
   */
  closeAddSlaveModal() {
    const modal = document.getElementById('addSlaveModal');
    if (modal) {
      modal.classList.remove('show');
      setTimeout(() => modal.remove(), 300);
    }
  }

  /**
   * Confirm add slave to pair
   */
  async confirmAddSlave(pairId) {
    const slaveAccount = document.getElementById('addSlaveSelect')?.value;

    if (!slaveAccount) {
      toast.warning('Please select a slave account');
      return;
    }

    const settings = {
      auto_map_symbol: document.getElementById('addSlaveAutoMapSymbol')?.checked ?? true,
      auto_map_volume: document.getElementById('addSlaveAutoMapVolume')?.checked ?? true,
      copy_psl: document.getElementById('addSlaveCopyPSL')?.checked ?? true,
      volume_mode: document.getElementById('addSlaveVolumeMode')?.value || 'multiply',
      multiplier: parseFloat(document.getElementById('addSlaveMultiplier')?.value || '2')
    };

    try {
      loading.show();
      await CopyTradingAPI.addSlave(pairId, slaveAccount, settings);
      toast.success('Slave account added successfully');
      this.closeAddSlaveModal();
      await this.loadCopyPairs();
      this.renderPlans();
      this.renderActivePairsTable();
    } catch (error) {
      console.error('Add slave error:', error);
      toast.error('Failed to add slave account');
    } finally {
      loading.hide();
    }
  }

  // =====================================================
  // FILTER FUNCTIONS
  // =====================================================

  /**
   * Filter pairs by search
   */
  filterPairsBySearch() {
    const searchInput = document.getElementById('pairSearchInput');
    const searchTerm = (searchInput?.value || '').toLowerCase().trim();

    if (!searchTerm) {
      this.renderPlans();
      return;
    }

    const filteredPairs = appState.plans.filter(plan => {
      const masterMatch = (plan.masterAccount || '').toLowerCase().includes(searchTerm);
      const slaveMatch = (plan.slaveAccount || '').toLowerCase().includes(searchTerm);
      const masterNicknameMatch = (plan.masterNickname || '').toLowerCase().includes(searchTerm);
      const slaveNicknameMatch = (plan.slaveNickname || '').toLowerCase().includes(searchTerm);
      return masterMatch || slaveMatch || masterNicknameMatch || slaveNicknameMatch;
    });

    this.renderPlansFiltered(filteredPairs);
  }

  /**
   * Render filtered plans
   */
  renderPlansFiltered(filteredPairs) {
    const container = document.getElementById('plansList');
    if (!container) return;

    if (!filteredPairs.length) {
      container.innerHTML = `
        <div class="empty-state-small">
          <i class="fas fa-search"></i>
          <p>No matching pairs found</p>
        </div>`;
      return;
    }

    // Reuse the same rendering logic but with filtered list
    container.innerHTML = filteredPairs.map(plan => {
      const statusClass = plan.status === 'active' ? 'online' : 'offline';
      const statusText = plan.status === 'active' ? 'Active' : 'Inactive';

      return `
        <div class="plan-item-card" data-plan-id="${escape(plan.id)}">
          <div class="plan-item-header">
            <div class="plan-item-accounts">
              <div class="plan-item-account master">
                <div class="plan-item-account-info">
                  <div class="plan-item-account-number">${escape(plan.masterAccount)}</div>
                  ${plan.masterNickname ? `<div class="plan-item-account-nickname">${escape(plan.masterNickname)}</div>` : ''}
                </div>
              </div>
              <div class="plan-item-arrow"><i class="fas fa-arrow-right"></i></div>
              <div class="plan-item-account slave">
                <i class="fas fa-user"></i>
                <div class="plan-item-account-info">
                  <div class="plan-item-account-number">${escape(plan.slaveAccount)}</div>
                  ${plan.slaveNickname ? `<div class="plan-item-account-nickname">${escape(plan.slaveNickname)}</div>` : ''}
                </div>
              </div>
            </div>
            <span class="status-badge ${statusClass}">${statusText}</span>
          </div>
          <div class="plan-item-actions">
            <button class="btn btn-${plan.status === 'active' ? 'warning' : 'success'} btn-sm" onclick="ui.togglePlanStatus('${plan.id}')">
              <i class="fas fa-${plan.status === 'active' ? 'pause' : 'play'}"></i>
            </button>
            <button class="btn btn-info btn-sm" onclick="ui.editPlan('${plan.id}')">
              <i class="fas fa-edit"></i>
            </button>
            <button class="btn btn-danger btn-sm" onclick="ui.deletePlan('${plan.id}')">
              <i class="fas fa-trash"></i>
            </button>
          </div>
        </div>
      `;
    }).join('');
  }
}

// Export singleton
const copyTradingModule = new CopyTradingModule();
export default copyTradingModule;
export { CopyTradingModule };

