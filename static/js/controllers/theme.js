/**
 * @file theme.js
 * @description Theme controller for dark/light mode
 * @module controllers/theme
 */

/**
 * Theme controller
 */
class ThemeController {
  constructor() {
    this.storageKey = 'theme';
  }

  /**
   * Initialize theme based on saved preference or system preference
   */
  init() {
    const saved = localStorage.getItem(this.storageKey);
    const pref = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    this.set(saved || pref || 'dark');
  }

  /**
   * Set theme
   * @param {string} theme - 'dark' or 'light'
   */
  set(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem(this.storageKey, theme);
    this.updateToggleUI();
  }

  /**
   * Get current theme
   * @returns {string}
   */
  get() {
    return document.documentElement.getAttribute('data-theme') || 'dark';
  }

  /**
   * Toggle between dark and light theme
   */
  toggle() {
    const current = this.get();
    this.set(current === 'dark' ? 'light' : 'dark');
  }

  /**
   * Update theme toggle button UI
   */
  updateToggleUI() {
    const btn = document.getElementById('themeToggleBtn');
    if (!btn) return;

    const theme = this.get();
    if (theme === 'dark') {
      btn.innerHTML = '<i class="fas fa-sun"></i>';
      btn.classList.remove('btn-primary');
      btn.classList.add('btn-secondary');
    } else {
      btn.innerHTML = '<i class="fas fa-moon"></i>';
      btn.classList.remove('btn-secondary');
      btn.classList.add('btn-primary');
    }
  }
}

// Export singleton
const themeController = new ThemeController();
export default themeController;

// Also export class for testing
export { ThemeController };

