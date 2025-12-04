/**
 * @file modal.js
 * @description Modal dialog service
 * @module services/modal
 */

import { escape } from '../utils/helpers.js';
import { UI_CONFIG } from '../config/constants.js';

/**
 * Modal service for dialogs and confirmations
 */
class ModalService {
  constructor() {
    this.currentAction = null;
  }

  /**
   * Show confirm dialog
   * @param {string} title - Dialog title
   * @param {string} message - Dialog message
   * @returns {Promise<boolean>} User's choice
   */
  showConfirm(title, message) {
    return new Promise((resolve) => {
      const modal = document.getElementById('modalOverlay');
      if (!modal) {
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
        if (confirmBtn) confirmBtn.removeEventListener('click', handler);
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
   * Show modal with custom confirm text
   * @param {string} title
   * @param {string} message
   * @param {Function} onConfirm - Callback on confirm
   * @param {string} confirmText - Button text
   * @returns {Promise<boolean>}
   */
  show(title, message, onConfirm, confirmText = 'Confirm') {
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
      if (messageEl) messageEl.textContent = message;
      if (confirmBtn) confirmBtn.textContent = confirmText;

      modal.classList.add('show');

      const handler = () => {
        resolve(true);
        if (onConfirm) onConfirm();
        cleanup();
      };

      const cleanup = () => {
        if (confirmBtn) confirmBtn.removeEventListener('click', handler);
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
   * Close modal
   */
  close() {
    const modal = document.getElementById('modalOverlay');
    if (modal) modal.classList.remove('show');
    if (this.currentAction) {
      this.currentAction(false);
      this.currentAction = null;
    }
  }

  /**
   * Confirm action (for modal confirm button)
   */
  confirm() {
    if (this.currentAction) {
      this.currentAction(true);
      this.currentAction = null;
    }
    this.close();
  }

  /**
   * Show custom confirm dialog with styled buttons
   * @param {string} title
   * @param {string} message
   * @returns {Promise<boolean>}
   */
  showCustomConfirm(title, message) {
    return new Promise((resolve) => {
      const modal = document.createElement('div');
      modal.className = 'custom-confirm-modal';
      modal.innerHTML = `
        <div class="custom-confirm-content">
          <div class="custom-confirm-header">
            <h4>${escape(title)}</h4>
          </div>
          <div class="custom-confirm-body">
            <p>${escape(message)}</p>
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
        }, UI_CONFIG.MODAL_CLOSE_DELAY);
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
}

// Export singleton instance
const modal = new ModalService();
export default modal;

// Also export class for testing
export { ModalService };

