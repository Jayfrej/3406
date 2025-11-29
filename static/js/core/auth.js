/**
 * Authentication Module
 *
 * Handles user authentication:
 * - Login/logout
 * - Session management
 * - Auth state checking
 */

class AuthManager {
    constructor() {
        this.authKey = 'tab-auth';
        this.isAuthenticated = false;
    }

    /**
     * Check if user is authenticated
     * @returns {boolean} True if authenticated
     */
    checkAuth() {
        return sessionStorage.getItem(this.authKey) === '1';
    }

    /**
     * Ensure user is logged in
     * Prompts for login if not authenticated
     * @returns {Promise<void>}
     */
    async ensureLogin() {
        // Check if already authenticated
        if (this.checkAuth()) {
            this.isAuthenticated = true;
            return;
        }

        // Prompt for credentials
        const username = prompt('Username:');
        const password = prompt('Password:');

        // Handle cancellation
        if (!username || !password) {
            location.reload();
            return;
        }

        // Attempt login
        try {
            const response = await fetch('/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });

            if (!response.ok) {
                alert('Login failed. Please check your credentials.');
                location.reload();
                return;
            }

            // Mark as authenticated
            sessionStorage.setItem(this.authKey, '1');
            this.isAuthenticated = true;

            console.log('[AUTH] Login successful');
        } catch (error) {
            console.error('[AUTH] Login error:', error);
            alert('Login failed. Please try again.');
            location.reload();
        }
    }

    /**
     * Login with credentials
     * @param {string} username - Username
     * @param {string} password - Password
     * @returns {Promise<boolean>} True if login successful
     */
    async login(username, password) {
        try {
            const response = await fetch('/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });

            if (response.ok) {
                sessionStorage.setItem(this.authKey, '1');
                this.isAuthenticated = true;
                console.log('[AUTH] Login successful');
                return true;
            } else {
                console.warn('[AUTH] Login failed:', response.status);
                return false;
            }
        } catch (error) {
            console.error('[AUTH] Login error:', error);
            return false;
        }
    }

    /**
     * Logout current user
     */
    logout() {
        sessionStorage.removeItem(this.authKey);
        this.isAuthenticated = false;
        console.log('[AUTH] User logged out');

        // Optionally redirect to login or reload
        location.reload();
    }

    /**
     * Clear authentication state
     */
    clearAuth() {
        sessionStorage.removeItem(this.authKey);
        this.isAuthenticated = false;
    }

    /**
     * Get authentication status
     * @returns {Object} Auth status object
     */
    getStatus() {
        return {
            isAuthenticated: this.checkAuth(),
            timestamp: new Date().toISOString()
        };
    }
}

// Create singleton instance
window.Auth = new AuthManager();

// Export for use in modules
window.AuthManager = AuthManager;

