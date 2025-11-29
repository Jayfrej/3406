/**
 * Core Utilities Module
 *
 * Helper functions used across the application:
 * - Clipboard operations
 * - Date/time formatting
 * - String utilities
 * - Debounce/throttle
 */

/**
 * Copy text to clipboard
 * @param {string} text - Text to copy
 * @param {string} successMsg - Success message to display
 * @param {Function} toastCallback - Optional toast notification callback
 */
function copyToClipboard(text, successMsg = 'Copied to clipboard!', toastCallback = null) {
    try {
        if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(text).then(() => {
                if (toastCallback) {
                    toastCallback(successMsg, 'success');
                } else if (window.app && window.app.showToast) {
                    window.app.showToast(successMsg, 'success');
                }
            }).catch(err => {
                throw err;
            });
        } else {
            // Fallback for non-HTTPS contexts
            const ta = document.createElement('textarea');
            ta.value = text;
            ta.setAttribute('readonly', '');
            ta.style.position = 'fixed';
            ta.style.left = '-9999px';
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            document.body.removeChild(ta);

            if (toastCallback) {
                toastCallback(successMsg, 'success');
            } else if (window.app && window.app.showToast) {
                window.app.showToast(successMsg, 'success');
            }
        }
    } catch (error) {
        console.error('Failed to copy to clipboard:', error);
        if (toastCallback) {
            toastCallback('Failed to copy to clipboard', 'error');
        } else if (window.app && window.app.showToast) {
            window.app.showToast('Failed to copy to clipboard', 'error');
        }
    }
}

/**
 * Format date to localized string
 * @param {string|Date} date - Date to format
 * @returns {string} Formatted date string
 */
function formatDate(date) {
    if (!date) return '-';

    try {
        const d = typeof date === 'string' ? new Date(date) : date;
        if (isNaN(d.getTime())) return '-';

        return d.toLocaleString('en-US', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false
        });
    } catch (error) {
        console.error('Date formatting error:', error);
        return '-';
    }
}

/**
 * Format timestamp to relative time (e.g., "2 minutes ago")
 * @param {string|Date} timestamp - Timestamp to format
 * @returns {string} Relative time string
 */
function formatRelativeTime(timestamp) {
    if (!timestamp) return '-';

    try {
        const date = typeof timestamp === 'string' ? new Date(timestamp) : timestamp;
        const now = new Date();
        const diff = now - date;
        const seconds = Math.floor(diff / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);
        const days = Math.floor(hours / 24);

        if (days > 0) return `${days} day${days > 1 ? 's' : ''} ago`;
        if (hours > 0) return `${hours} hour${hours > 1 ? 's' : ''} ago`;
        if (minutes > 0) return `${minutes} minute${minutes > 1 ? 's' : ''} ago`;
        return `${seconds} second${seconds !== 1 ? 's' : ''} ago`;
    } catch (error) {
        console.error('Relative time formatting error:', error);
        return '-';
    }
}

/**
 * Escape HTML to prevent XSS
 * @param {string} str - String to escape
 * @returns {string} Escaped string
 */
function escapeHtml(str) {
    if (typeof str !== 'string') return '';

    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

/**
 * Debounce function - delay execution until after delay
 * @param {Function} func - Function to debounce
 * @param {number} wait - Delay in milliseconds
 * @returns {Function} Debounced function
 */
function debounce(func, wait = 300) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Throttle function - limit execution rate
 * @param {Function} func - Function to throttle
 * @param {number} limit - Time limit in milliseconds
 * @returns {Function} Throttled function
 */
function throttle(func, limit = 1000) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

/**
 * Generate unique ID
 * @returns {string} Unique ID
 */
function generateId() {
    return Date.now().toString(36) + Math.random().toString(36).substr(2);
}

/**
 * Check if value is empty
 * @param {*} value - Value to check
 * @returns {boolean} True if empty
 */
function isEmpty(value) {
    return value === null ||
           value === undefined ||
           value === '' ||
           (Array.isArray(value) && value.length === 0) ||
           (typeof value === 'object' && Object.keys(value).length === 0);
}

/**
 * Deep clone object
 * @param {Object} obj - Object to clone
 * @returns {Object} Cloned object
 */
function deepClone(obj) {
    if (obj === null || typeof obj !== 'object') return obj;

    try {
        return JSON.parse(JSON.stringify(obj));
    } catch (error) {
        console.error('Deep clone error:', error);
        return obj;
    }
}

/**
 * Get current timestamp in ISO format
 * @returns {string} ISO timestamp
 */
function getCurrentTimestamp() {
    return new Date().toISOString();
}

/**
 * Format file size to human readable
 * @param {number} bytes - Size in bytes
 * @returns {string} Formatted size
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';

    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));

    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

/**
 * Validate email format
 * @param {string} email - Email to validate
 * @returns {boolean} True if valid
 */
function isValidEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
}

/**
 * Sleep/delay function
 * @param {number} ms - Milliseconds to sleep
 * @returns {Promise} Promise that resolves after delay
 */
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// Export functions for use in other modules
window.Utils = {
    copyToClipboard,
    formatDate,
    formatRelativeTime,
    escapeHtml,
    debounce,
    throttle,
    generateId,
    isEmpty,
    deepClone,
    getCurrentTimestamp,
    formatFileSize,
    isValidEmail,
    sleep
};

