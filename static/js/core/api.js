/**
 * API Client Module
 *
 * HTTP client for making authenticated API requests
 * - Handles authentication
 * - Automatic retry on 401
 * - Error handling
 * - Request/response logging
 */

class ApiClient {
    constructor() {
        this.baseUrl = window.location.origin;
        this.defaultHeaders = {
            'Content-Type': 'application/json'
        };
    }

    /**
     * Make authenticated fetch request
     * @param {string} url - API endpoint URL
     * @param {Object} options - Fetch options
     * @returns {Promise<Response>} Fetch response
     */
    async fetchWithAuth(url, options = {}) {
        try {
            const response = await fetch(url, {
                ...options,
                headers: {
                    ...this.defaultHeaders,
                    ...options.headers
                }
            });

            // If 401, re-authenticate and retry
            if (response.status === 401) {
                console.warn('[API] Session expired, attempting re-authentication...');

                // Clear auth state
                sessionStorage.removeItem('tab-auth');

                // Trigger re-authentication if auth module is available
                if (window.Auth) {
                    await window.Auth.ensureLogin();
                }

                // Retry the request
                const retryResponse = await fetch(url, {
                    ...options,
                    headers: {
                        ...this.defaultHeaders,
                        ...options.headers
                    }
                });
                return retryResponse;
            }

            return response;
        } catch (error) {
            console.error('[API] Fetch error:', error);
            throw error;
        }
    }

    /**
     * GET request
     * @param {string} url - API endpoint
     * @returns {Promise<Response>} Response
     */
    async get(url) {
        return this.fetchWithAuth(url, {
            method: 'GET'
        });
    }

    /**
     * POST request
     * @param {string} url - API endpoint
     * @param {Object} data - Request body data
     * @returns {Promise<Response>} Response
     */
    async post(url, data) {
        return this.fetchWithAuth(url, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    /**
     * PUT request
     * @param {string} url - API endpoint
     * @param {Object} data - Request body data
     * @returns {Promise<Response>} Response
     */
    async put(url, data) {
        return this.fetchWithAuth(url, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }

    /**
     * DELETE request
     * @param {string} url - API endpoint
     * @returns {Promise<Response>} Response
     */
    async delete(url) {
        return this.fetchWithAuth(url, {
            method: 'DELETE'
        });
    }

    /**
     * GET request and parse JSON
     * @param {string} url - API endpoint
     * @returns {Promise<Object>} Parsed JSON response
     */
    async getJson(url) {
        const response = await this.get(url);
        if (!response.ok) {
            throw new Error(`API request failed: ${response.status} ${response.statusText}`);
        }
        return response.json();
    }

    /**
     * POST request and parse JSON
     * @param {string} url - API endpoint
     * @param {Object} data - Request body data
     * @returns {Promise<Object>} Parsed JSON response
     */
    async postJson(url, data) {
        const response = await this.post(url, data);
        if (!response.ok) {
            throw new Error(`API request failed: ${response.status} ${response.statusText}`);
        }
        return response.json();
    }

    /**
     * PUT request and parse JSON
     * @param {string} url - API endpoint
     * @param {Object} data - Request body data
     * @returns {Promise<Object>} Parsed JSON response
     */
    async putJson(url, data) {
        const response = await this.put(url, data);
        if (!response.ok) {
            throw new Error(`API request failed: ${response.status} ${response.statusText}`);
        }
        return response.json();
    }

    /**
     * DELETE request and parse JSON
     * @param {string} url - API endpoint
     * @returns {Promise<Object>} Parsed JSON response
     */
    async deleteJson(url) {
        const response = await this.delete(url);
        if (!response.ok) {
            throw new Error(`API request failed: ${response.status} ${response.statusText}`);
        }
        return response.json();
    }

    /**
     * Handle API error response
     * @param {Response} response - Fetch response
     * @returns {Promise<Error>} Error with response data
     */
    async handleError(response) {
        let errorMessage = `HTTP ${response.status}`;

        try {
            const data = await response.json();
            errorMessage = data.error || data.message || errorMessage;
        } catch (e) {
            // Response is not JSON
            errorMessage = await response.text() || errorMessage;
        }

        throw new Error(errorMessage);
    }
}

// Create singleton instance
window.ApiClient = new ApiClient();

// Export for use in modules
window.API = window.ApiClient;

