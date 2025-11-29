/**
 * Theme Manager Module
 *
 * Handles theme switching and persistence:
 * - Dark/Light theme toggle
 * - Theme persistence in localStorage
 * - System preference detection
 * - UI updates
 */

class ThemeManager {
    constructor() {
        this.storageKey = 'theme';
        this.currentTheme = 'dark';
    }

    /**
     * Initialize theme on page load
     */
    init() {
        // Check saved theme or system preference
        const savedTheme = localStorage.getItem(this.storageKey);
        const systemPreference = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';

        // Use saved theme, fall back to system preference, default to dark
        const theme = savedTheme || systemPreference || 'dark';
        this.setTheme(theme);

        // Setup event listener for theme toggle button
        this.setupToggleButton();

        // Listen for system preference changes
        this.watchSystemPreference();
    }

    /**
     * Set theme
     * @param {string} theme - Theme name ('dark' or 'light')
     */
    setTheme(theme) {
        // Validate theme
        if (theme !== 'dark' && theme !== 'light') {
            console.warn(`[THEME] Invalid theme: ${theme}. Defaulting to 'dark'.`);
            theme = 'dark';
        }

        // Apply theme to document
        document.documentElement.setAttribute('data-theme', theme);

        // Save to localStorage
        localStorage.setItem(this.storageKey, theme);

        // Update current theme
        this.currentTheme = theme;

        // Update UI
        this.updateToggleUI();

        console.log(`[THEME] Theme set to: ${theme}`);
    }

    /**
     * Toggle between dark and light theme
     */
    toggleTheme() {
        const currentTheme = this.getTheme();
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        this.setTheme(newTheme);
    }

    /**
     * Get current theme
     * @returns {string} Current theme name
     */
    getTheme() {
        return document.documentElement.getAttribute('data-theme') || 'dark';
    }

    /**
     * Setup theme toggle button
     */
    setupToggleButton() {
        const btn = document.getElementById('themeToggleBtn');
        if (btn) {
            btn.addEventListener('click', () => this.toggleTheme());
        }
    }

    /**
     * Update theme toggle button UI
     */
    updateToggleUI() {
        const btn = document.getElementById('themeToggleBtn');
        if (!btn) return;

        const theme = this.getTheme();

        if (theme === 'dark') {
            // Dark theme active - show sun icon (to switch to light)
            btn.innerHTML = '<i class="fas fa-sun"></i>';
            btn.classList.remove('btn-primary');
            btn.classList.add('btn-secondary');
            btn.setAttribute('title', 'Switch to Light Mode');
        } else {
            // Light theme active - show moon icon (to switch to dark)
            btn.innerHTML = '<i class="fas fa-moon"></i>';
            btn.classList.remove('btn-secondary');
            btn.classList.add('btn-primary');
            btn.setAttribute('title', 'Switch to Dark Mode');
        }
    }

    /**
     * Watch for system preference changes
     */
    watchSystemPreference() {
        const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');

        // Only auto-switch if user hasn't manually set a theme
        mediaQuery.addEventListener('change', (e) => {
            const savedTheme = localStorage.getItem(this.storageKey);
            if (!savedTheme) {
                // No saved preference, follow system
                const newTheme = e.matches ? 'dark' : 'light';
                this.setTheme(newTheme);
            }
        });
    }

    /**
     * Reset theme to system preference
     */
    resetToSystem() {
        localStorage.removeItem(this.storageKey);
        const systemPreference = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
        this.setTheme(systemPreference);
    }

    /**
     * Get theme info
     * @returns {Object} Theme information
     */
    getInfo() {
        const systemPreference = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
        return {
            current: this.getTheme(),
            saved: localStorage.getItem(this.storageKey),
            systemPreference: systemPreference
        };
    }
}

// Create singleton instance
window.Theme = new ThemeManager();

// Export for use in modules
window.ThemeManager = ThemeManager;

