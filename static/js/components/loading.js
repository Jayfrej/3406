/**
 * Loading Component
 *
 * Handles loading overlay display:
 * - Show/hide loading spinner
 * - Prevent interactions during loading
 */

class Loading {
    constructor() {
        this.overlayId = 'loadingOverlay';
        this.isVisible = false;
    }

    /**
     * Show loading overlay
     */
    show() {
        const overlay = document.getElementById(this.overlayId);
        if (overlay) {
            overlay.classList.add('show');
            this.isVisible = true;
        } else {
            console.warn('[LOADING] Loading overlay not found');
        }
    }

    /**
     * Hide loading overlay
     */
    hide() {
        const overlay = document.getElementById(this.overlayId);
        if (overlay) {
            overlay.classList.remove('show');
            this.isVisible = false;
        }
    }

    /**
     * Toggle loading overlay
     */
    toggle() {
        if (this.isVisible) {
            this.hide();
        } else {
            this.show();
        }
    }

    /**
     * Check if loading is visible
     * @returns {boolean} True if loading is shown
     */
    isShown() {
        return this.isVisible;
    }

    /**
     * Execute function with loading indicator
     * @param {Function} fn - Async function to execute
     * @returns {Promise<*>} Function result
     */
    async withLoading(fn) {
        try {
            this.show();
            const result = await fn();
            return result;
        } finally {
            this.hide();
        }
    }
}

// Create singleton instance
window.Loading = new Loading();

// Export class
window.LoadingClass = Loading;

