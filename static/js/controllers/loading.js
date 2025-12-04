/**
 * @file loading.js
 * @description Loading overlay controller
 * @module controllers/loading
 */

/**
 * Loading controller
 */
class LoadingController {
  constructor() {
    this.overlayId = 'loadingOverlay';
  }

  /**
   * Show loading overlay
   */
  show() {
    const overlay = document.getElementById(this.overlayId);
    if (overlay) overlay.classList.add('show');
  }

  /**
   * Hide loading overlay
   */
  hide() {
    const overlay = document.getElementById(this.overlayId);
    if (overlay) overlay.classList.remove('show');
  }

  /**
   * Execute async function with loading indicator
   * @param {Function} asyncFn - Async function to execute
   * @returns {Promise<*>}
   */
  async withLoading(asyncFn) {
    this.show();
    try {
      return await asyncFn();
    } finally {
      this.hide();
    }
  }
}

// Export singleton
const loading = new LoadingController();
export default loading;

// Also export class for testing
export { LoadingController };

