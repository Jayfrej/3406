/**
 * @file toast.js
 * @description Toast notification service
 * @module services/toast
 */

import { TOAST_ICONS, TOAST_TITLES } from '../config/constants.js';
import { UI_CONFIG } from '../config/constants.js';

/**
 * Toast notification service
 */
class ToastService {
  constructor() {
    this.containerId = 'toastContainer';
  }

  /**
   * Get toast container element
   * @returns {HTMLElement|null}
   */
  getContainer() {
    return document.getElementById(this.containerId);
  }

  /**
   * Show toast notification
   * @param {string} message - Message to display
   * @param {string} type - Type: success, error, warning, info
   * @param {number} duration - Duration in ms (default 5000)
   */
  show(message, type = 'info', duration = UI_CONFIG.TOAST_DURATION) {
    const container = this.getContainer();
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    const icon = TOAST_ICONS[type] || 'info-circle';
    const title = TOAST_TITLES[type] || 'Information';

    toast.innerHTML = `
      <div class="toast-icon"><i class="fas fa-${icon}"></i></div>
      <div class="toast-content">
        <div class="toast-title">${title}</div>
        <div class="toast-message">${message}</div>
      </div>
      <button class="toast-close" onclick="this.parentElement.remove()">
        <i class="fas fa-times"></i>
      </button>
    `;

    container.appendChild(toast);

    // Auto remove after duration
    setTimeout(() => {
      if (toast.parentElement) {
        toast.remove();
      }
    }, duration);
  }

  /**
   * Show success toast
   * @param {string} message
   */
  success(message) {
    this.show(message, 'success');
  }

  /**
   * Show error toast
   * @param {string} message
   */
  error(message) {
    this.show(message, 'error');
  }

  /**
   * Show warning toast
   * @param {string} message
   */
  warning(message) {
    this.show(message, 'warning');
  }

  /**
   * Show info toast
   * @param {string} message
   */
  info(message) {
    this.show(message, 'info');
  }
}

// Export singleton instance
const toast = new ToastService();
export default toast;

// Also export the class for testing
export { ToastService };

