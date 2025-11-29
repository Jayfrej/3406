/**
 * Toast Notification Component
 *
 * Handles toast/notification display:
 * - Success, error, warning, info types
 * - Auto-dismiss with configurable duration
 * - Icon and title per type
 */

class Toast {
    constructor() {
        this.defaultDuration = 5000;
        this.icons = {
            success: 'check-circle',
            error: 'exclamation-circle',
            warning: 'exclamation-triangle',
            info: 'info-circle'
        };
        this.titles = {
            success: 'Success',
            error: 'Error',
            warning: 'Warning',
            info: 'Information'
        };
    }

    /**
     * Show toast notification
     * @param {string} message - Toast message
     * @param {string} type - Toast type (success, error, warning, info)
     * @param {number} duration - Display duration in milliseconds
     */
    show(message, type = 'info', duration = this.defaultDuration) {
        const container = document.getElementById('toastContainer');
        if (!container) {
            console.warn('[TOAST] Toast container not found');
            return;
        }

        const toast = document.createElement('div');
        toast.className = `toast ${type}`;

        const icon = this.icons[type] || this.icons.info;
        const title = this.titles[type] || this.titles.info;

        toast.innerHTML = `
            <div class="toast-icon"><i class="fas fa-${icon}"></i></div>
            <div class="toast-content">
                <div class="toast-title">${title}</div>
                <div class="toast-message">${this.escapeHtml(message)}</div>
            </div>
            <button class="toast-close" onclick="this.parentElement.remove()">
                <i class="fas fa-times"></i>
            </button>`;

        container.appendChild(toast);

        // Auto-remove after duration
        setTimeout(() => {
            if (toast.parentElement) {
                toast.remove();
            }
        }, duration);
    }

    /**
     * Show success toast
     * @param {string} message - Success message
     * @param {number} duration - Display duration
     */
    success(message, duration) {
        this.show(message, 'success', duration);
    }

    /**
     * Show error toast
     * @param {string} message - Error message
     * @param {number} duration - Display duration
     */
    error(message, duration) {
        this.show(message, 'error', duration);
    }

    /**
     * Show warning toast
     * @param {string} message - Warning message
     * @param {number} duration - Display duration
     */
    warning(message, duration) {
        this.show(message, 'warning', duration);
    }

    /**
     * Show info toast
     * @param {string} message - Info message
     * @param {number} duration - Display duration
     */
    info(message, duration) {
        this.show(message, 'info', duration);
    }

    /**
     * Escape HTML to prevent XSS
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
     * Clear all toasts
     */
    clearAll() {
        const container = document.getElementById('toastContainer');
        if (container) {
            container.innerHTML = '';
        }
    }
}

// Create singleton instance
window.Toast = new Toast();

// Export class
window.ToastClass = Toast;

