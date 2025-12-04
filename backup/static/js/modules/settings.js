/**
 * @file settings.js
 * @description Settings module - Rate limits, Email, Symbol mappings
 * @module modules/settings
 */

import appState from '../config/state.js';
import { SettingsAPI, AccountAPI, fetchWithAuth } from '../services/api.js';
import toast from '../services/toast.js';
import modal from '../services/modal.js';
import loading from '../controllers/loading.js';
import { escape, isValidEmail, isValidRateLimit, generateSecretKey, getFieldValue, setFieldValue } from '../utils/helpers.js';
import { RATE_LIMIT_DEFAULTS } from '../config/constants.js';

/**
 * Settings Module
 */
class SettingsModule {

  // =====================================================
  // LOAD ALL SETTINGS
  // =====================================================

  /**
   * Load all settings
   */
  async loadAllSettings() {
    try {
      const data = await SettingsAPI.getAll();

      // Rate Limit Settings
      if (data.rate_limits) {
        const accountsInput = document.getElementById('accountsRateLimit');
        const webhookInput = document.getElementById('webhookRateLimit');
        const apiInput = document.getElementById('apiRateLimit');
        const commandApiInput = document.getElementById('commandApiRateLimit');

        if (accountsInput && data.rate_limits.accounts) {
          accountsInput.value = data.rate_limits.accounts;
        }
        if (webhookInput && data.rate_limits.webhook) {
          webhookInput.value = data.rate_limits.webhook;
        }
        if (apiInput && data.rate_limits.api) {
          apiInput.value = data.rate_limits.api;
        }
        if (commandApiInput && data.rate_limits.command_api) {
          commandApiInput.value = data.rate_limits.command_api;
        }

        // Update display
        this.updateRateLimitDisplay(data.rate_limits);
      }

      console.log('[SETTINGS] Settings loaded successfully');
    } catch (error) {
      console.error('[SETTINGS] Error loading settings:', error);
      toast.error('Failed to load settings');
    }
  }

  /**
   * Update rate limit display
   */
  updateRateLimitDisplay(rateLimits) {
    const currentAccounts = document.getElementById('currentAccountsLimit');
    const currentWebhook = document.getElementById('currentWebhookLimit');
    const currentApi = document.getElementById('currentApiLimit');
    const currentCommandApi = document.getElementById('currentCommandApiLimit');
    const lastUpdate = document.getElementById('lastConfigUpdate');

    if (currentAccounts) {
      currentAccounts.textContent = rateLimits.accounts || 'Exempt (Unlimited)';
    }
    if (currentWebhook) {
      currentWebhook.textContent = rateLimits.webhook || 'Not set';
    }
    if (currentApi) {
      currentApi.textContent = rateLimits.api || 'Not set';
    }
    if (currentCommandApi) {
      currentCommandApi.textContent = rateLimits.command_api || 'Not set';
    }
    if (lastUpdate && rateLimits.last_updated) {
      lastUpdate.textContent = new Date(rateLimits.last_updated).toLocaleString();
    }
  }

  // =====================================================
  // RATE LIMIT SETTINGS
  // =====================================================

  /**
   * Save rate limit settings
   */
  async saveRateLimitSettings() {
    const accountsLimit = document.getElementById('accountsRateLimit')?.value?.trim();
    const webhookLimit = document.getElementById('webhookRateLimit')?.value?.trim();
    const apiLimit = document.getElementById('apiRateLimit')?.value?.trim();
    const commandApiLimit = document.getElementById('commandApiRateLimit')?.value?.trim();

    // Validate
    if (accountsLimit && !isValidRateLimit(accountsLimit)) {
      toast.warning('Invalid accounts rate limit format. Use: "number per (minute|hour|day)" or "exempt"');
      return;
    }
    if (webhookLimit && !isValidRateLimit(webhookLimit)) {
      toast.warning('Invalid webhook rate limit format. Use: "number per (minute|hour|day)"');
      return;
    }
    if (apiLimit && !isValidRateLimit(apiLimit)) {
      toast.warning('Invalid API rate limit format. Use: "number per (minute|hour|day)"');
      return;
    }
    if (commandApiLimit && !isValidRateLimit(commandApiLimit)) {
      toast.warning('Invalid Command API rate limit format. Use: "number per (minute|hour|day)"');
      return;
    }

    try {
      loading.show();
      await SettingsAPI.saveRateLimits({
        accounts: accountsLimit || null,
        webhook: webhookLimit || null,
        command_api: commandApiLimit || null,
        api: apiLimit || null
      });

      this.updateRateLimitDisplay({
        accounts: accountsLimit || 'Exempt (Unlimited)',
        webhook: webhookLimit || 'Not set',
        api: apiLimit || 'Not set',
        command_api: commandApiLimit || 'Not set',
        last_updated: new Date().toISOString()
      });

      toast.success('Rate limit settings saved! Server restart required.');
      console.log('[SETTINGS] Rate limits saved');
    } catch (error) {
      console.error('[SETTINGS] Error saving rate limits:', error);
      toast.error(error.message || 'Failed to save rate limit settings');
    } finally {
      loading.hide();
    }
  }

  /**
   * Reset rate limit settings to defaults
   */
  async resetRateLimitSettings() {
    const confirmed = await modal.showConfirm(
      'Reset Rate Limits',
      'Reset rate limits to default values?\n\nAccounts: Exempt (Unlimited)\nWebhook: 10/min\nAPI: 100/hr\nCommand API: 60/min'
    );
    if (!confirmed) return;

    try {
      loading.show();

      // Set default values in form
      const accountsInput = document.getElementById('accountsRateLimit');
      const webhookInput = document.getElementById('webhookRateLimit');
      const apiInput = document.getElementById('apiRateLimit');
      const commandApiInput = document.getElementById('commandApiRateLimit');

      if (accountsInput) accountsInput.value = RATE_LIMIT_DEFAULTS.ACCOUNTS;
      if (webhookInput) webhookInput.value = RATE_LIMIT_DEFAULTS.WEBHOOK;
      if (apiInput) apiInput.value = RATE_LIMIT_DEFAULTS.API;
      if (commandApiInput) commandApiInput.value = RATE_LIMIT_DEFAULTS.COMMAND_API;

      // Save defaults
      await SettingsAPI.saveRateLimits({
        accounts: RATE_LIMIT_DEFAULTS.ACCOUNTS,
        webhook: RATE_LIMIT_DEFAULTS.WEBHOOK,
        api: RATE_LIMIT_DEFAULTS.API,
        command_api: RATE_LIMIT_DEFAULTS.COMMAND_API
      });

      this.updateRateLimitDisplay({
        accounts: 'Exempt (Unlimited)',
        webhook: RATE_LIMIT_DEFAULTS.WEBHOOK,
        api: RATE_LIMIT_DEFAULTS.API,
        command_api: RATE_LIMIT_DEFAULTS.COMMAND_API,
        last_updated: new Date().toISOString()
      });

      toast.success('Rate limits reset to default values');
    } catch (error) {
      console.error('[SETTINGS] Error resetting rate limits:', error);
      toast.error('Failed to reset rate limits');
    } finally {
      loading.hide();
    }
  }

  // =====================================================
  // EMAIL SETTINGS
  // =====================================================

  /**
   * Load email settings
   */
  async loadEmailSettings() {
    try {
      const data = await SettingsAPI.getEmailSettings();

      const enabledToggle = document.getElementById('emailEnabled');
      const smtpServer = document.getElementById('smtpServer') || document.getElementById('smtpHost');
      const smtpPort = document.getElementById('smtpPort');
      const smtpUser = document.getElementById('smtpUser');
      const smtpPass = document.getElementById('smtpPass') || document.getElementById('senderPassword');
      const fromEmail = document.getElementById('fromEmail') || document.getElementById('senderEmail');
      const toEmails = document.getElementById('toEmails') || document.getElementById('recipients');

      if (enabledToggle) {
        enabledToggle.checked = data.enabled || false;
        this.toggleEmailConfig();
      }
      if (smtpServer) setFieldValue(smtpServer, data.smtp_server || 'smtp.gmail.com');
      if (smtpPort) setFieldValue(smtpPort, data.smtp_port || 587);
      if (smtpUser) smtpUser.value = data.smtp_user || '';
      if (smtpPass) setFieldValue(smtpPass, data.smtp_pass || '');
      if (fromEmail) setFieldValue(fromEmail, data.from_email || '');
      if (toEmails) setFieldValue(toEmails, (data.to_emails || []).join(', '));

      console.log('[SETTINGS] Email settings loaded successfully');
    } catch (error) {
      console.error('[SETTINGS] Error loading email settings:', error);
    }
  }

  /**
   * Toggle email config visibility
   */
  toggleEmailConfig() {
    const enabled = document.getElementById('emailEnabled')?.checked;
    const configSection = document.querySelector('.email-config-section') || document.getElementById('emailConfigSection');
    if (configSection) {
      configSection.style.display = enabled ? 'block' : 'none';
    }

    const statusBadge = document.getElementById('currentEmailStatus');
    if (statusBadge) {
      statusBadge.textContent = enabled ? 'Enabled' : 'Disabled';
      statusBadge.className = 'status-badge ' + (enabled ? 'online' : 'offline');
    }
  }

  /**
   * Toggle password visibility
   */
  togglePasswordVisibility() {
    const passInput = document.getElementById('smtpPass') || document.getElementById('senderPassword');
    const toggleIcon = document.querySelector('.btn-icon-toggle i') || document.getElementById('passwordToggleIcon');

    if (passInput && toggleIcon) {
      if (passInput.type === 'password') {
        passInput.type = 'text';
        toggleIcon.classList.remove('fa-eye');
        toggleIcon.classList.add('fa-eye-slash');
      } else {
        passInput.type = 'password';
        toggleIcon.classList.remove('fa-eye-slash');
        toggleIcon.classList.add('fa-eye');
      }
    }
  }

  /**
   * Save email settings
   */
  async saveEmailSettings() {
    const enabled = document.getElementById('emailEnabled')?.checked;
    const smtpServerEl = document.getElementById('smtpServer') || document.getElementById('smtpHost');
    const smtpPortEl = document.getElementById('smtpPort');
    const smtpUserEl = document.getElementById('smtpUser');
    const smtpPassEl = document.getElementById('smtpPass') || document.getElementById('senderPassword');
    const fromEmailEl = document.getElementById('fromEmail') || document.getElementById('senderEmail');
    const toEmailsEl = document.getElementById('toEmails') || document.getElementById('recipients');

    const smtpServer = smtpServerEl ? getFieldValue(smtpServerEl) : '';
    const smtpPort = smtpPortEl ? getFieldValue(smtpPortEl) : '';
    const smtpUser = smtpUserEl ? getFieldValue(smtpUserEl) : '';
    const smtpPass = smtpPassEl ? getFieldValue(smtpPassEl) : '';
    const fromEmail = fromEmailEl ? getFieldValue(fromEmailEl) : '';
    const toEmailsRaw = toEmailsEl ? getFieldValue(toEmailsEl) : '';

    if (enabled) {
      if (!smtpServer || !smtpPort || !smtpUser || !fromEmail || !toEmailsRaw) {
        toast.warning('Please fill in all required email configuration fields');
        return;
      }
      if (!isValidEmail(fromEmail)) {
        toast.warning('Invalid sender email format');
        return;
      }
      const toEmailsTmp = toEmailsRaw.split(',').map(e => e.trim()).filter(e => e);
      const invalidEmails = toEmailsTmp.filter(email => !isValidEmail(email));
      if (invalidEmails.length > 0) {
        toast.warning('Invalid recipient email(s): ' + invalidEmails.join(', '));
        return;
      }
    }

    try {
      loading.show();
      const toEmails = toEmailsRaw ? toEmailsRaw.split(',').map(e => e.trim()).filter(e => e) : [];

      await SettingsAPI.saveEmailSettings({
        enabled: enabled,
        smtp_server: smtpServer || 'smtp.gmail.com',
        smtp_port: parseInt(smtpPort) || 587,
        smtp_user: smtpUser,
        smtp_pass: smtpPass,
        from_email: fromEmail,
        to_emails: toEmails
      });

      toast.success('Email settings saved successfully!');
      console.log('[SETTINGS] Email settings saved');
    } catch (error) {
      console.error('[SETTINGS] Error saving email settings:', error);
      toast.error(error.message || 'Failed to save email settings');
    } finally {
      loading.hide();
    }
  }

  /**
   * Test email settings
   */
  async testEmailSettings() {
    const enabled = document.getElementById('emailEnabled')?.checked;
    if (!enabled) {
      toast.warning('Please enable email notifications first');
      return;
    }

    // Save settings first
    await this.saveEmailSettings();

    try {
      loading.show();
      await SettingsAPI.testEmail();
      toast.success('Test email sent! Check your inbox.');
      console.log('[SETTINGS] Test email sent');
    } catch (error) {
      console.error('[SETTINGS] Error sending test email:', error);
      toast.error(error.message || 'Failed to send test email');
    } finally {
      loading.hide();
    }
  }

  // =====================================================
  // GLOBAL SECRET KEY
  // =====================================================

  /**
   * Load global secret key
   */
  async loadGlobalSecret() {
    try {
      const data = await SettingsAPI.getGlobalSecret();
      const input = document.getElementById('globalSecretInput');
      if (input) {
        input.value = data.secret || '';
      }
    } catch (error) {
      console.error('Failed to load global secret:', error);
    }
  }

  /**
   * Generate new global secret
   */
  generateGlobalSecret() {
    const input = document.getElementById('globalSecretInput');
    if (input) {
      input.value = generateSecretKey();
    }
  }

  /**
   * Save global secret key
   */
  async saveGlobalSecret() {
    const secret = document.getElementById('globalSecretInput')?.value?.trim();

    try {
      loading.show();
      await SettingsAPI.saveGlobalSecret(secret);
      toast.success('Global secret key saved successfully');
    } catch (error) {
      console.error('Failed to save global secret:', error);
      toast.error('Failed to save global secret key');
    } finally {
      loading.hide();
    }
  }

  /**
   * Clear global secret key
   */
  async clearGlobalSecret() {
    const confirmed = await modal.showCustomConfirm(
      'Clear Secret Key',
      'Are you sure you want to clear the global secret key? This will disable authentication for all accounts.'
    );
    if (!confirmed) return;

    try {
      loading.show();
      await SettingsAPI.saveGlobalSecret('');
      document.getElementById('globalSecretInput').value = '';
      toast.success('Global secret key cleared successfully');
    } catch (error) {
      console.error('Failed to clear global secret:', error);
      toast.error('Failed to clear global secret key');
    } finally {
      loading.hide();
    }
  }

  // =====================================================
  // SYMBOL MAPPING (Settings Page)
  // =====================================================

  /**
   * Populate symbol mapping account dropdown
   */
  async populateSymbolMappingAccounts() {
    try {
      console.log('[Settings] Loading accounts for Symbol Mapping...');
      const accounts = appState.getAccounts();

      const accountSelect = document.getElementById('symbolMappingAccount');
      if (!accountSelect) {
        console.warn('[Settings] symbolMappingAccount dropdown not found');
        return;
      }

      accountSelect.innerHTML = '<option value="">-- Select Account --</option>';
      accounts.forEach(acc => {
        const option = document.createElement('option');
        option.value = acc.account;
        option.textContent = `${acc.account}${acc.nickname ? ' - ' + acc.nickname : ''}`;
        accountSelect.appendChild(option);
      });

      console.log(`[Settings] Loaded ${accounts.length} accounts for Symbol Mapping`);
    } catch (error) {
      console.error('[Settings] Error populating symbol mapping accounts:', error);
    }
  }

  /**
   * Load symbol mappings for account
   */
  async loadAccountSymbolMappings(accountNumber) {
    if (!accountNumber) {
      const container = document.getElementById('symbolMappingContainer');
      if (container) container.style.display = 'none';
      return;
    }

    try {
      console.log(`[Settings] Loading symbol mappings for account: ${accountNumber}`);
      const container = document.getElementById('symbolMappingContainer');
      if (container) container.style.display = 'block';

      const data = await AccountAPI.getSymbolMappings(accountNumber);
      this.renderSymbolMappingsSettings(data.mappings || {});
    } catch (error) {
      console.error('[Settings] Error loading symbol mappings:', error);
    }
  }

  /**
   * Render symbol mappings in settings
   */
  renderSymbolMappingsSettings(mappings) {
    const listElement = document.getElementById('symbolMappingsList');
    if (!listElement) return;

    const entries = Object.entries(mappings);

    if (!entries.length) {
      listElement.innerHTML = '<p style="color: var(--text-dim);">No custom mappings configured yet.</p>';
      return;
    }

    listElement.innerHTML = entries.map(([from, to]) => `
      <div class="mapping-item" style="display: flex; justify-content: space-between; align-items: center; padding: 10px; background: var(--surface-2); border-radius: 6px; margin-bottom: 8px;">
        <div>
          <strong>${escape(from)}</strong> → <strong>${escape(to)}</strong>
        </div>
        <button class="btn btn-danger btn-sm" onclick="ui.removeSymbolMappingSettings('${escape(from)}')">
          <i class="fas fa-trash"></i>
        </button>
      </div>
    `).join('');
  }

  /**
   * Add symbol mapping from settings page
   */
  async addSymbolMappingSettings() {
    const accountSelect = document.getElementById('symbolMappingAccount');
    const fromInput = document.getElementById('newMappingFrom');
    const toInput = document.getElementById('newMappingTo');

    const accountNumber = accountSelect?.value;
    const from = fromInput?.value.trim().toUpperCase();
    const to = toInput?.value.trim().toUpperCase();

    if (!accountNumber) {
      toast.warning('Please select an account first');
      return;
    }
    if (!from || !to) {
      toast.warning('Please enter both source and target symbols');
      return;
    }

    try {
      loading.show();
      await AccountAPI.addSymbolMapping(accountNumber, from, to);
      toast.success(`Mapping added: ${from} → ${to}`);

      if (fromInput) fromInput.value = '';
      if (toInput) toInput.value = '';

      await this.loadAccountSymbolMappings(accountNumber);
    } catch (error) {
      console.error('[Settings] Error adding symbol mapping:', error);
      toast.error('Failed to add mapping');
    } finally {
      loading.hide();
    }
  }

  /**
   * Remove symbol mapping from settings page
   */
  async removeSymbolMappingSettings(from) {
    const accountSelect = document.getElementById('symbolMappingAccount');
    const accountNumber = accountSelect?.value;
    if (!accountNumber) return;

    const confirmed = await modal.showConfirm('Remove Mapping', `Remove mapping for ${from}?`);
    if (!confirmed) return;

    try {
      loading.show();
      await AccountAPI.deleteSymbolMapping(accountNumber, from);
      toast.success('Mapping removed');
      await this.loadAccountSymbolMappings(accountNumber);
    } catch (error) {
      console.error('[Settings] Error removing symbol mapping:', error);
      toast.error('Failed to remove mapping');
    } finally {
      loading.hide();
    }
  }
}

// Export singleton
const settingsModule = new SettingsModule();
export default settingsModule;
export { SettingsModule };

