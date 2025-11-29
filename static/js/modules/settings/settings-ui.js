/**
 * Settings UI Module
 *
 * Handles settings page UI rendering and interactions:
 * - Rate limit settings form
 * - Email settings form
 * - Symbol mapping management
 */

class SettingsUI {
    constructor() {
        this.manager = window.SettingsManager;
    }

    /**
     * Load and render all settings
     * @returns {Promise<void>}
     */
    async loadAndRenderSettings() {
        this.showLoading();

        try {
            await this.manager.loadAllSettings();
            this.renderRateLimitSettings();
        } catch (error) {
            console.error('Load settings error:', error);
        } finally {
            this.hideLoading();
        }
    }

    /**
     * Render rate limit settings in form
     */
    renderRateLimitSettings() {
        const rateLimits = this.manager.getRateLimits();

        // Populate form inputs
        const accountsInput = document.getElementById('accountsRateLimit');
        const webhookInput = document.getElementById('webhookRateLimit');
        const apiInput = document.getElementById('apiRateLimit');
        const commandApiInput = document.getElementById('commandApiRateLimit');

        if (accountsInput && rateLimits.accounts) {
            accountsInput.value = rateLimits.accounts;
        }
        if (webhookInput && rateLimits.webhook) {
            webhookInput.value = rateLimits.webhook;
        }
        if (apiInput && rateLimits.api) {
            apiInput.value = rateLimits.api;
        }
        if (commandApiInput && rateLimits.command_api) {
            commandApiInput.value = rateLimits.command_api;
        }

        // Update current configuration display
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

    /**
     * Save rate limit settings
     * @returns {Promise<void>}
     */
    async saveRateLimitSettings() {
        const accountsLimit = document.getElementById('accountsRateLimit')?.value?.trim();
        const webhookLimit = document.getElementById('webhookRateLimit')?.value?.trim();
        const apiLimit = document.getElementById('apiRateLimit')?.value?.trim();
        const commandApiLimit = document.getElementById('commandApiRateLimit')?.value?.trim();

        // Validate formats
        if (accountsLimit && !this.manager.validateRateLimitFormat(accountsLimit)) {
            this.showToast('Invalid accounts rate limit format. Use: "number per (minute|hour|day)" or "exempt"', 'warning');
            return;
        }
        if (webhookLimit && !this.manager.validateRateLimitFormat(webhookLimit)) {
            this.showToast('Invalid webhook rate limit format. Use: "number per (minute|hour|day)"', 'warning');
            return;
        }
        if (apiLimit && !this.manager.validateRateLimitFormat(apiLimit)) {
            this.showToast('Invalid API rate limit format. Use: "number per (minute|hour|day)"', 'warning');
            return;
        }
        if (commandApiLimit && !this.manager.validateRateLimitFormat(commandApiLimit)) {
            this.showToast('Invalid Command API rate limit format. Use: "number per (minute|hour|day)"', 'warning');
            return;
        }

        this.showLoading();

        try {
            const result = await this.manager.saveRateLimitSettings({
                accounts: accountsLimit || null,
                webhook: webhookLimit || null,
                api: apiLimit || null,
                command_api: commandApiLimit || null
            });

            if (result.success) {
                this.showToast(result.message, 'success');

                // Update display
                const currentAccounts = document.getElementById('currentAccountsLimit');
                const currentWebhook = document.getElementById('currentWebhookLimit');
                const currentApi = document.getElementById('currentApiLimit');
                const currentCommandApi = document.getElementById('currentCommandApiLimit');
                const lastUpdate = document.getElementById('lastConfigUpdate');

                if (currentAccounts) currentAccounts.textContent = accountsLimit || 'Exempt (Unlimited)';
                if (currentWebhook) currentWebhook.textContent = webhookLimit || 'Not set';
                if (currentApi) currentApi.textContent = apiLimit || 'Not set';
                if (currentCommandApi) currentCommandApi.textContent = commandApiLimit || 'Not set';
                if (lastUpdate) lastUpdate.textContent = new Date().toLocaleString();
            } else {
                this.showToast(result.error, 'error');
            }
        } catch (error) {
            console.error('Save rate limits error:', error);
            this.showToast('Failed to save rate limit settings', 'error');
        } finally {
            this.hideLoading();
        }
    }

    /**
     * Reset rate limit settings to defaults
     * @returns {Promise<void>}
     */
    async resetRateLimitSettings() {
        const confirmed = await this.showConfirmDialog(
            'Reset Rate Limits',
            'Reset rate limits to default values?\n\nAccounts: Exempt (Unlimited)\nWebhook: 10/min\nAPI: 100/hr\nCommand API: 60/min'
        );

        if (!confirmed) return;

        this.showLoading();

        try {
            const result = await this.manager.resetRateLimitSettings();

            if (result.success) {
                // Update form inputs
                const accountsInput = document.getElementById('accountsRateLimit');
                const webhookInput = document.getElementById('webhookRateLimit');
                const apiInput = document.getElementById('apiRateLimit');
                const commandApiInput = document.getElementById('commandApiRateLimit');

                if (accountsInput) accountsInput.value = 'exempt';
                if (webhookInput) webhookInput.value = '10 per minute';
                if (apiInput) apiInput.value = '100 per hour';
                if (commandApiInput) commandApiInput.value = '60 per minute';

                // Update display
                const currentAccounts = document.getElementById('currentAccountsLimit');
                const currentWebhook = document.getElementById('currentWebhookLimit');
                const currentApi = document.getElementById('currentApiLimit');
                const currentCommandApi = document.getElementById('currentCommandApiLimit');
                const lastUpdate = document.getElementById('lastConfigUpdate');

                if (currentAccounts) currentAccounts.textContent = 'Exempt (Unlimited)';
                if (currentWebhook) currentWebhook.textContent = '10 per minute';
                if (currentApi) currentApi.textContent = '100 per hour';
                if (currentCommandApi) currentCommandApi.textContent = '60 per minute';
                if (lastUpdate) lastUpdate.textContent = new Date().toLocaleString();

                this.showToast('Rate limits reset to default values', 'success');
            } else {
                this.showToast(result.error, 'error');
            }
        } catch (error) {
            console.error('Reset rate limits error:', error);
            this.showToast('Failed to reset rate limits', 'error');
        } finally {
            this.hideLoading();
        }
    }

    /**
     * Load and render email settings
     * @returns {Promise<void>}
     */
    async loadEmailSettings() {
        try {
            const emailSettings = await this.manager.loadEmailSettings();

            // Populate form
            const smtpHost = document.getElementById('smtpHost');
            const smtpPort = document.getElementById('smtpPort');
            const smtpUser = document.getElementById('smtpUser');
            const smtpPass = document.getElementById('smtpPassword');
            const emailFrom = document.getElementById('emailFrom');
            const emailTo = document.getElementById('emailTo');
            const enableEmail = document.getElementById('enableEmail');

            if (smtpHost) smtpHost.value = emailSettings.smtp_host || '';
            if (smtpPort) smtpPort.value = emailSettings.smtp_port || '';
            if (smtpUser) smtpUser.value = emailSettings.smtp_user || '';
            if (smtpPass) smtpPass.value = emailSettings.smtp_password || '';
            if (emailFrom) emailFrom.value = emailSettings.email_from || '';
            if (emailTo) emailTo.value = emailSettings.email_to || '';
            if (enableEmail) enableEmail.checked = emailSettings.enabled || false;

        } catch (error) {
            console.error('Load email settings error:', error);
        }
    }

    /**
     * Save email settings
     * @returns {Promise<void>}
     */
    async saveEmailSettings() {
        const smtpHost = document.getElementById('smtpHost')?.value?.trim();
        const smtpPort = document.getElementById('smtpPort')?.value?.trim();
        const smtpUser = document.getElementById('smtpUser')?.value?.trim();
        const smtpPass = document.getElementById('smtpPassword')?.value?.trim();
        const emailFrom = document.getElementById('emailFrom')?.value?.trim();
        const emailTo = document.getElementById('emailTo')?.value?.trim();
        const enableEmail = document.getElementById('enableEmail')?.checked;

        this.showLoading();

        try {
            const result = await this.manager.saveEmailSettings({
                smtp_host: smtpHost,
                smtp_port: parseInt(smtpPort) || 587,
                smtp_user: smtpUser,
                smtp_password: smtpPass,
                email_from: emailFrom,
                email_to: emailTo,
                enabled: enableEmail
            });

            if (result.success) {
                this.showToast(result.message, 'success');
            } else {
                this.showToast(result.error, 'error');
            }
        } catch (error) {
            console.error('Save email settings error:', error);
            this.showToast('Failed to save email settings', 'error');
        } finally {
            this.hideLoading();
        }
    }

    /**
     * Test email settings
     * @returns {Promise<void>}
     */
    async testEmailSettings() {
        const testEmail = document.getElementById('testEmailAddress')?.value?.trim();

        if (!testEmail) {
            this.showToast('Please enter a test email address', 'warning');
            return;
        }

        // Save settings first
        await this.saveEmailSettings();

        this.showLoading();

        try {
            const result = await this.manager.testEmailSettings(testEmail);

            if (result.success) {
                this.showToast(result.message, 'success');
            } else {
                this.showToast(result.error, 'error');
            }
        } catch (error) {
            console.error('Test email error:', error);
            this.showToast('Failed to send test email', 'error');
        } finally {
            this.hideLoading();
        }
    }

    /**
     * Populate symbol mapping accounts dropdown
     * @returns {Promise<void>}
     */
    async populateSymbolMappingAccounts() {
        try {
            const accountSelect = document.getElementById('symbolMappingAccount');
            if (!accountSelect) return;

            // Get accounts from AccountManager if available
            let accounts = [];
            if (window.AccountManager) {
                accounts = window.AccountManager.getAccounts();
            }

            if (!accounts.length) {
                accountSelect.innerHTML = '<option value="">No accounts available</option>';
                return;
            }

            accountSelect.innerHTML = '<option value="">Select Account</option>' +
                accounts.map(acc =>
                    `<option value="${acc.account}">${acc.account} - ${acc.nickname || 'No nickname'}</option>`
                ).join('');

        } catch (error) {
            console.error('Populate symbol mapping accounts error:', error);
        }
    }

    /**
     * Load symbol mappings for selected account
     * @param {string} accountNumber - Account number
     * @returns {Promise<void>}
     */
    async loadAccountSymbolMappings(accountNumber) {
        if (!accountNumber) {
            const container = document.getElementById('symbolMappingContainer');
            if (container) container.style.display = 'none';
            return;
        }

        const container = document.getElementById('symbolMappingContainer');
        if (container) container.style.display = 'block';

        try {
            const mappings = await this.manager.loadSymbolMappings(accountNumber);
            this.renderSymbolMappings(mappings);
        } catch (error) {
            console.error('Load symbol mappings error:', error);
            this.renderSymbolMappings([]);
        }
    }

    /**
     * Render symbol mappings list
     * @param {Array} mappings - Symbol mappings
     */
    renderSymbolMappings(mappings) {
        const listElement = document.getElementById('symbolMappingsList');
        if (!listElement) return;

        if (!mappings.length) {
            listElement.innerHTML = '<p class="text-muted">No symbol mappings configured for this account.</p>';
            return;
        }

        listElement.innerHTML = mappings.map(m => `
            <div class="mapping-item">
                <span><strong>${this.escapeHtml(m.from)}</strong> → ${this.escapeHtml(m.to)}</span>
                <button class="btn btn-danger btn-sm" onclick="window.SettingsUI.removeSymbolMapping('${this.escapeHtml(m.from)}')">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        `).join('');
    }

    /**
     * Add symbol mapping
     * @returns {Promise<void>}
     */
    async addSymbolMapping() {
        const accountSelect = document.getElementById('symbolMappingAccount');
        const fromInput = document.getElementById('newMappingFrom');
        const toInput = document.getElementById('newMappingTo');

        const accountNumber = accountSelect?.value;
        const from = fromInput?.value?.trim();
        const to = toInput?.value?.trim();

        if (!accountNumber) {
            this.showToast('Please select an account', 'warning');
            return;
        }
        if (!from || !to) {
            this.showToast('Please enter both symbols', 'warning');
            return;
        }

        this.showLoading();

        try {
            const result = await this.manager.addSymbolMapping(accountNumber, from, to);

            if (result.success) {
                this.showToast(result.message, 'success');

                // Clear inputs
                if (fromInput) fromInput.value = '';
                if (toInput) toInput.value = '';

                // Reload mappings
                await this.loadAccountSymbolMappings(accountNumber);
            } else {
                this.showToast(result.error, 'error');
            }
        } catch (error) {
            console.error('Add symbol mapping error:', error);
            this.showToast('Failed to add mapping', 'error');
        } finally {
            this.hideLoading();
        }
    }

    /**
     * Remove symbol mapping
     * @param {string} from - Symbol to remove mapping for
     * @returns {Promise<void>}
     */
    async removeSymbolMapping(from) {
        const accountSelect = document.getElementById('symbolMappingAccount');
        const accountNumber = accountSelect?.value;

        if (!accountNumber) return;

        const confirmed = await this.showConfirmDialog(
            'Remove Mapping',
            `Remove symbol mapping for ${from}?`
        );
        if (!confirmed) return;

        this.showLoading();

        try {
            const result = await this.manager.removeSymbolMapping(accountNumber, from);

            if (result.success) {
                this.showToast(result.message, 'success');
                await this.loadAccountSymbolMappings(accountNumber);
            } else {
                this.showToast(result.error, 'error');
            }
        } catch (error) {
            console.error('Remove symbol mapping error:', error);
            this.showToast('Failed to remove mapping', 'error');
        } finally {
            this.hideLoading();
        }
    }

    /**
     * Initialize settings page
     * @returns {Promise<void>}
     */
    async initialize() {
        await this.loadAndRenderSettings();
        await this.loadEmailSettings();
        await this.populateSymbolMappingAccounts();
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
window.SettingsUI = new SettingsUI();

// Export class
window.SettingsUIClass = SettingsUI;

