/**
 * Settings Module
 *
 * Manages application settings:
 * - Rate limit settings
 * - Email settings
 * - Symbol mappings
 * - General configuration
 */

class SettingsManager {
    constructor() {
        this.settings = {};
        this.emailSettings = {};
        this.rateLimits = {};
    }

    /**
     * Load all settings from server
     * @returns {Promise<Object>} Settings data
     */
    async loadAllSettings() {
        try {
            const response = await window.API.get('/api/settings');

            if (!response.ok) {
                throw new Error('Failed to load settings');
            }

            const data = await response.json();
            this.settings = data;
            this.rateLimits = data.rate_limits || {};

            console.log('[SETTINGS] Settings loaded successfully');
            return data;
        } catch (error) {
            console.error('[SETTINGS] Error loading settings:', error);
            return {};
        }
    }

    /**
     * Save rate limit settings
     * @param {Object} limits - Rate limit configuration
     * @returns {Promise<Object>} Result with success status
     */
    async saveRateLimitSettings(limits) {
        try {
            const response = await window.API.post('/api/settings/rate-limits', limits);

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to save settings');
            }

            const data = await response.json();
            this.rateLimits = limits;

            console.log('[SETTINGS] Rate limits saved:', data);
            return { success: true, message: 'Rate limit settings saved! Server restart required.' };

        } catch (error) {
            console.error('[SETTINGS] Error saving rate limits:', error);
            return { success: false, error: error.message || 'Failed to save rate limit settings' };
        }
    }

    /**
     * Reset rate limits to defaults
     * @returns {Promise<Object>} Result with success status
     */
    async resetRateLimitSettings() {
        const defaults = {
            accounts: 'exempt',
            webhook: '10 per minute',
            api: '100 per hour',
            command_api: '60 per minute'
        };

        return await this.saveRateLimitSettings(defaults);
    }

    /**
     * Load email settings
     * @returns {Promise<Object>} Email settings
     */
    async loadEmailSettings() {
        try {
            const response = await window.API.get('/api/settings/email');

            if (!response.ok) {
                throw new Error('Failed to load email settings');
            }

            const data = await response.json();
            this.emailSettings = data;

            console.log('[SETTINGS] Email settings loaded successfully');
            return data;

        } catch (error) {
            console.error('[SETTINGS] Error loading email settings:', error);
            return {};
        }
    }

    /**
     * Save email settings
     * @param {Object} settings - Email configuration
     * @returns {Promise<Object>} Result with success status
     */
    async saveEmailSettings(settings) {
        try {
            const response = await window.API.post('/api/settings/email', settings);

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to save email settings');
            }

            this.emailSettings = settings;
            console.log('[SETTINGS] Email settings saved');

            return { success: true, message: 'Email settings saved successfully!' };

        } catch (error) {
            console.error('[SETTINGS] Error saving email settings:', error);
            return { success: false, error: error.message || 'Failed to save email settings' };
        }
    }

    /**
     * Test email settings
     * @param {string} testEmail - Email address to send test to
     * @returns {Promise<Object>} Result with success status
     */
    async testEmailSettings(testEmail) {
        try {
            const response = await window.API.post('/api/settings/email/test', {
                test_email: testEmail
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to send test email');
            }

            const data = await response.json();
            console.log('[SETTINGS] Test email sent');

            return { success: true, message: data.message || 'Test email sent successfully!' };

        } catch (error) {
            console.error('[SETTINGS] Error sending test email:', error);
            return { success: false, error: error.message || 'Failed to send test email' };
        }
    }

    /**
     * Load symbol mappings for an account
     * @param {string} accountNumber - Account number
     * @returns {Promise<Array>} Symbol mappings
     */
    async loadSymbolMappings(accountNumber) {
        try {
            const response = await window.API.get(`/api/symbol-mappings/${accountNumber}`);

            if (!response.ok) {
                throw new Error('Failed to load symbol mappings');
            }

            const data = await response.json();
            return data.mappings || [];

        } catch (error) {
            console.error('[SETTINGS] Error loading symbol mappings:', error);
            return [];
        }
    }

    /**
     * Add symbol mapping
     * @param {string} accountNumber - Account number
     * @param {string} from - Symbol to map from
     * @param {string} to - Symbol to map to
     * @returns {Promise<Object>} Result with success status
     */
    async addSymbolMapping(accountNumber, from, to) {
        try {
            const response = await window.API.post('/api/symbol-mappings', {
                account: accountNumber,
                from: from,
                to: to
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to add mapping');
            }

            console.log('[SETTINGS] Symbol mapping added');
            return { success: true, message: 'Symbol mapping added successfully' };

        } catch (error) {
            console.error('[SETTINGS] Error adding symbol mapping:', error);
            return { success: false, error: error.message || 'Failed to add mapping' };
        }
    }

    /**
     * Remove symbol mapping
     * @param {string} accountNumber - Account number
     * @param {string} from - Symbol to remove mapping for
     * @returns {Promise<Object>} Result with success status
     */
    async removeSymbolMapping(accountNumber, from) {
        try {
            const response = await window.API.delete(`/api/symbol-mappings/${accountNumber}/${from}`);

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to remove mapping');
            }

            console.log('[SETTINGS] Symbol mapping removed');
            return { success: true, message: 'Symbol mapping removed successfully' };

        } catch (error) {
            console.error('[SETTINGS] Error removing symbol mapping:', error);
            return { success: false, error: error.message || 'Failed to remove mapping' };
        }
    }

    /**
     * Get current settings
     * @returns {Object} Current settings
     */
    getSettings() {
        return { ...this.settings };
    }

    /**
     * Get rate limits
     * @returns {Object} Rate limits
     */
    getRateLimits() {
        return { ...this.rateLimits };
    }

    /**
     * Get email settings
     * @returns {Object} Email settings
     */
    getEmailSettings() {
        return { ...this.emailSettings };
    }

    /**
     * Validate rate limit format
     * @param {string} value - Rate limit value
     * @returns {boolean} True if valid
     */
    validateRateLimitFormat(value) {
        if (!value) return true; // Empty is valid

        const rateLimitPattern = /^\d+\s+per\s+(minute|hour|day)$/i;
        const exemptPattern = /^exempt$/i;

        return rateLimitPattern.test(value) || exemptPattern.test(value);
    }
}

// Create singleton instance
window.SettingsManager = new SettingsManager();

// Export class
window.SettingsManagerClass = SettingsManager;

