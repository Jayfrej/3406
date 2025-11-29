/**
 * Modal Component
 *
 * Handles modal dialogs:
 * - Confirmation dialogs
 * - Custom modals
 * - Modal lifecycle management
 */

class Modal {
    constructor() {
        this.currentAction = null;
    }

    /**
     * Show confirmation dialog
     * @param {string} title - Dialog title
     * @param {string} message - Dialog message
     * @returns {Promise<boolean>} True if confirmed
     */
    showConfirmDialog(title, message) {
        return new Promise((resolve) => {
            const modal = document.getElementById('modalOverlay');
            if (!modal) {
                console.warn('[MODAL] Modal overlay not found');
                resolve(false);
                return;
            }

            const titleEl = document.getElementById('modalTitle');
            const messageEl = document.getElementById('modalMessage');

            if (titleEl) titleEl.textContent = title;
            if (messageEl) messageEl.textContent = message;

            modal.classList.add('show');

            const confirmBtn = document.getElementById('modalConfirmBtn');

            const handler = () => {
                resolve(true);
                cleanup();
            };

            const cleanup = () => {
                if (confirmBtn) {
                    confirmBtn.removeEventListener('click', handler);
                }
                this.close();
            };

            if (confirmBtn) {
                confirmBtn.addEventListener('click', handler, { once: true });
            }

            this.currentAction = (ok) => {
                resolve(!!ok);
                cleanup();
            };
        });
    }

    /**
     * Show custom confirm with custom styling
     * @param {string} title - Dialog title
     * @param {string} message - Dialog message
     * @returns {Promise<boolean>} True if confirmed
     */
    showCustomConfirm(title, message) {
        return new Promise((resolve) => {
            const modal = document.createElement('div');
            modal.className = 'custom-confirm-modal';
            modal.innerHTML = `
                <div class="custom-confirm-content">
                    <div class="custom-confirm-header">
                        <h4>${this.escapeHtml(title)}</h4>
                    </div>
                    <div class="custom-confirm-body">
                        <p>${this.escapeHtml(message)}</p>
                    </div>
                    <div class="custom-confirm-footer">
                        <button class="btn btn-secondary" id="customConfirmCancel">Cancel</button>
                        <button class="btn btn-danger" id="customConfirmOk">OK</button>
                    </div>
                </div>
            `;

            document.body.appendChild(modal);

            const cleanup = () => {
                modal.classList.remove('show');
                setTimeout(() => {
                    if (modal.parentElement) {
                        document.body.removeChild(modal);
                    }
                }, 300);
            };

            const handleOk = () => {
                cleanup();
                resolve(true);
            };

            const handleCancel = () => {
                cleanup();
                resolve(false);
            };

            const okBtn = modal.querySelector('#customConfirmOk');
            const cancelBtn = modal.querySelector('#customConfirmCancel');

            if (okBtn) okBtn.addEventListener('click', handleOk);
            if (cancelBtn) cancelBtn.addEventListener('click', handleCancel);

            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    handleCancel();
                }
            });

            setTimeout(() => {
                modal.classList.add('show');
            }, 10);
        });
    }

    /**
     * Show generic modal
     * @param {string} title - Modal title
     * @param {string} content - Modal content (HTML)
     * @param {Function} onConfirm - Callback on confirm
     * @param {string} confirmText - Confirm button text
     * @returns {Promise<boolean>} True if confirmed
     */
    show(title, content, onConfirm, confirmText = 'Confirm') {
        return new Promise((resolve) => {
            const modal = document.getElementById('modalOverlay');
            if (!modal) {
                resolve(false);
                return;
            }

            const titleEl = document.getElementById('modalTitle');
            const messageEl = document.getElementById('modalMessage');
            const confirmBtn = document.getElementById('modalConfirmBtn');

            if (titleEl) titleEl.textContent = title;
            if (messageEl) messageEl.innerHTML = content;
            if (confirmBtn) confirmBtn.textContent = confirmText;

            modal.classList.add('show');

            const handler = () => {
                resolve(true);
                if (onConfirm) onConfirm();
                cleanup();
            };

            const cleanup = () => {
                if (confirmBtn) {
                    confirmBtn.removeEventListener('click', handler);
                }
                this.close();
            };

            if (confirmBtn) {
                confirmBtn.addEventListener('click', handler, { once: true });
            }

            this.currentAction = (ok) => {
                resolve(!!ok);
                if (ok && onConfirm) onConfirm();
                cleanup();
            };
        });
    }

    /**
     * Close current modal
     */
    close() {
        const modal = document.getElementById('modalOverlay');
        if (modal) {
            modal.classList.remove('show');
        }
        if (this.currentAction) {
            this.currentAction(false);
            this.currentAction = null;
        }
    }

    /**
     * Confirm current action
     */
    confirm() {
        if (this.currentAction) {
            this.currentAction(true);
            this.currentAction = null;
        }
        this.close();
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
}

// Create singleton instance
window.Modal = new Modal();

// Export class
window.ModalClass = Modal;

