/**
 * @file api.js
 * @description HTTP API service with authentication support
 * @module services/api
 */

import { API_ENDPOINTS } from '../config/constants.js';

// =====================================================
// AUTH STATE
// =====================================================

const AUTH_KEY = 'tab-auth';

/**
 * Check if user is authenticated (per-tab)
 * @returns {boolean}
 */
function isAuthenticated() {
  return sessionStorage.getItem(AUTH_KEY) === '1';
}

/**
 * Set authentication state
 * @param {boolean} authenticated
 */
function setAuthenticated(authenticated) {
  if (authenticated) {
    sessionStorage.setItem(AUTH_KEY, '1');
  } else {
    sessionStorage.removeItem(AUTH_KEY);
  }
}

// =====================================================
// LOGIN FLOW
// =====================================================

/**
 * Ensure user is logged in (prompt if not)
 * @returns {Promise<void>}
 */
export async function ensureLogin() {
  if (isAuthenticated()) return;

  const u = prompt('Username:');
  const p = prompt('Password:');
  if (!u || !p) {
    location.reload();
    return;
  }

  const res = await fetch(API_ENDPOINTS.LOGIN, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: u, password: p }),
    credentials: 'include'
  });

  if (!res.ok) {
    alert('Login failed');
    location.reload();
    return;
  }

  setAuthenticated(true);
}

// =====================================================
// FETCH WITH AUTH
// =====================================================

/**
 * Fetch with automatic auth handling and retry on 401
 * @param {string} url - URL to fetch
 * @param {RequestInit} options - Fetch options
 * @returns {Promise<Response>}
 */
export async function fetchWithAuth(url, options = {}) {
  try {
    const fetchOptions = {
      ...options,
      credentials: 'include'
    };

    const response = await fetch(url, fetchOptions);

    // If 401, re-authenticate and retry
    if (response.status === 401) {
      console.warn('[AUTH] Session expired, attempting re-login...');
      setAuthenticated(false);
      await ensureLogin();

      // Retry the request
      const retryResponse = await fetch(url, fetchOptions);
      return retryResponse;
    }

    return response;
  } catch (error) {
    console.error('[FETCH] Error:', error);
    throw error;
  }
}

// =====================================================
// API HELPER METHODS
// =====================================================

/**
 * GET request with auth
 * @param {string} url
 * @returns {Promise<Response>}
 */
export async function get(url) {
  return fetchWithAuth(url);
}

/**
 * POST request with auth and JSON body
 * @param {string} url
 * @param {object} data
 * @returns {Promise<Response>}
 */
export async function post(url, data) {
  return fetchWithAuth(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
}

/**
 * DELETE request with auth
 * @param {string} url
 * @returns {Promise<Response>}
 */
export async function del(url) {
  return fetchWithAuth(url, { method: 'DELETE' });
}

/**
 * POST request without body (for action endpoints)
 * @param {string} url
 * @returns {Promise<Response>}
 */
export async function postAction(url) {
  return fetchWithAuth(url, { method: 'POST' });
}

// =====================================================
// JSON HELPERS
// =====================================================

/**
 * Fetch and parse JSON response
 * @param {string} url
 * @returns {Promise<object>}
 */
export async function getJson(url) {
  const response = await get(url);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${await response.text()}`);
  }
  return response.json();
}

/**
 * POST JSON and parse response
 * @param {string} url
 * @param {object} data
 * @returns {Promise<object>}
 */
export async function postJson(url, data) {
  const response = await post(url, data);
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error(errorData.error || `HTTP ${response.status}`);
  }
  return response.json();
}

// =====================================================
// ACCOUNT API
// =====================================================

export const AccountAPI = {
  /**
   * Get all accounts
   * @returns {Promise<{accounts: Array}>}
   */
  async getAll() {
    return getJson(API_ENDPOINTS.ACCOUNTS);
  },

  /**
   * Add new account
   * @param {string} account - Account number
   * @param {string} nickname - Account nickname
   * @returns {Promise<object>}
   */
  async add(account, nickname) {
    return postJson(API_ENDPOINTS.ACCOUNTS, { account, nickname });
  },

  /**
   * Delete account
   * @param {string} account - Account number
   * @returns {Promise<object>}
   */
  async delete(account) {
    const response = await del(`${API_ENDPOINTS.ACCOUNTS}/${account}`);
    return response.json();
  },

  /**
   * Pause account
   * @param {string} account
   * @returns {Promise<object>}
   */
  async pause(account) {
    const response = await postAction(`${API_ENDPOINTS.ACCOUNTS}/${account}/pause`);
    return response.json();
  },

  /**
   * Resume account
   * @param {string} account
   * @returns {Promise<object>}
   */
  async resume(account) {
    const response = await postAction(`${API_ENDPOINTS.ACCOUNTS}/${account}/resume`);
    return response.json();
  },

  /**
   * Get account secret key
   * @param {string} account
   * @returns {Promise<{secret: string}>}
   */
  async getSecret(account) {
    return getJson(`${API_ENDPOINTS.ACCOUNTS}/${account}/secret`);
  },

  /**
   * Set account secret key
   * @param {string} account
   * @param {string} secret
   * @returns {Promise<object>}
   */
  async setSecret(account, secret) {
    return postJson(`${API_ENDPOINTS.ACCOUNTS}/${account}/secret`, { secret });
  },

  /**
   * Get symbol mappings for account
   * @param {string} account
   * @returns {Promise<{mappings: object}>}
   */
  async getSymbolMappings(account) {
    const response = await fetchWithAuth(`${API_ENDPOINTS.ACCOUNTS}/${account}/symbols`);
    if (!response.ok) return { mappings: {} };
    return response.json();
  },

  /**
   * Add symbol mapping
   * @param {string} account
   * @param {string} fromSymbol
   * @param {string} toSymbol
   * @returns {Promise<object>}
   */
  async addSymbolMapping(account, fromSymbol, toSymbol) {
    return postJson(`${API_ENDPOINTS.ACCOUNTS}/${account}/symbols`, {
      from_symbol: fromSymbol,
      to_symbol: toSymbol
    });
  },

  /**
   * Delete symbol mapping
   * @param {string} account
   * @param {string} fromSymbol
   * @returns {Promise<object>}
   */
  async deleteSymbolMapping(account, fromSymbol) {
    const response = await del(
      `${API_ENDPOINTS.ACCOUNTS}/${encodeURIComponent(account)}/symbols/${encodeURIComponent(fromSymbol)}`
    );
    return response.json();
  }
};

// =====================================================
// WEBHOOK ACCOUNTS API
// =====================================================

export const WebhookAPI = {
  /**
   * Get webhook URL
   * @returns {Promise<{url: string}>}
   */
  async getUrl() {
    return getJson(API_ENDPOINTS.WEBHOOK_URL);
  },

  /**
   * Get webhook accounts
   * @returns {Promise<{accounts: Array}>}
   */
  async getAccounts() {
    const response = await fetchWithAuth(API_ENDPOINTS.WEBHOOK_ACCOUNTS);
    if (!response.ok) return { accounts: [] };
    return response.json();
  },

  /**
   * Add webhook account
   * @param {object} accountData
   * @returns {Promise<object>}
   */
  async addAccount(accountData) {
    return postJson(API_ENDPOINTS.WEBHOOK_ACCOUNTS, accountData);
  },

  /**
   * Delete webhook account
   * @param {string} account
   * @returns {Promise<Response>}
   */
  async deleteAccount(account) {
    return del(`${API_ENDPOINTS.WEBHOOK_ACCOUNTS}/${encodeURIComponent(account)}`);
  }
};

// =====================================================
// COPY TRADING API
// =====================================================

export const CopyTradingAPI = {
  /**
   * Get all pairs
   * @returns {Promise<{pairs: Array}>}
   */
  async getPairs() {
    return getJson(API_ENDPOINTS.PAIRS);
  },

  /**
   * Create pair
   * @param {object} pairData
   * @returns {Promise<object>}
   */
  async createPair(pairData) {
    return postJson(API_ENDPOINTS.PAIRS, pairData);
  },

  /**
   * Delete pair
   * @param {string} pairId
   * @returns {Promise<Response>}
   */
  async deletePair(pairId) {
    return del(`${API_ENDPOINTS.PAIRS}/${encodeURIComponent(pairId)}`);
  },

  /**
   * Toggle pair status
   * @param {string} pairId
   * @returns {Promise<object>}
   */
  async togglePair(pairId) {
    const response = await postAction(`${API_ENDPOINTS.PAIRS}/${pairId}/toggle`);
    return response.json();
  },

  /**
   * Start pair
   * @param {string} pairId
   * @returns {Promise<Response>}
   */
  async startPair(pairId) {
    return postAction(`${API_ENDPOINTS.PAIRS}/${pairId}/start`);
  },

  /**
   * Stop pair
   * @param {string} pairId
   * @returns {Promise<Response>}
   */
  async stopPair(pairId) {
    return postAction(`${API_ENDPOINTS.PAIRS}/${pairId}/stop`);
  },

  /**
   * Add master to pair
   * @param {string} pairId
   * @param {string} masterAccount
   * @returns {Promise<object>}
   */
  async addMaster(pairId, masterAccount) {
    return postJson(`${API_ENDPOINTS.PAIRS}/${pairId}/add-master`, {
      master_account: masterAccount
    });
  },

  /**
   * Add slave to pair
   * @param {string} pairId
   * @param {string} slaveAccount
   * @param {object} settings
   * @returns {Promise<object>}
   */
  async addSlave(pairId, slaveAccount, settings) {
    return postJson(`${API_ENDPOINTS.PAIRS}/${pairId}/add-slave`, {
      slave_account: slaveAccount,
      settings
    });
  },

  /**
   * Get copy history
   * @param {number} limit
   * @returns {Promise<{history: Array}>}
   */
  async getHistory(limit = 100) {
    return getJson(`${API_ENDPOINTS.COPY_HISTORY}?limit=${limit}`);
  },

  /**
   * Clear copy history
   * @returns {Promise<Response>}
   */
  async clearHistory() {
    return fetchWithAuth(`${API_ENDPOINTS.COPY_HISTORY}/clear?confirm=1`, {
      method: 'POST',
      credentials: 'include'
    });
  },

  /**
   * Get master accounts
   * @returns {Promise<{accounts: Array}>}
   */
  async getMasterAccounts() {
    return getJson(API_ENDPOINTS.MASTER_ACCOUNTS);
  },

  /**
   * Add master account
   * @param {string} account
   * @param {string} nickname
   * @returns {Promise<{account: object}>}
   */
  async addMasterAccount(account, nickname) {
    return postJson(API_ENDPOINTS.MASTER_ACCOUNTS, { account, nickname });
  },

  /**
   * Delete master account
   * @param {string} accountId
   * @returns {Promise<Response>}
   */
  async deleteMasterAccount(accountId) {
    return del(`${API_ENDPOINTS.MASTER_ACCOUNTS}/${accountId}`);
  },

  /**
   * Get slave accounts
   * @returns {Promise<{accounts: Array}>}
   */
  async getSlaveAccounts() {
    return getJson(API_ENDPOINTS.SLAVE_ACCOUNTS);
  },

  /**
   * Add slave account
   * @param {string} account
   * @param {string} nickname
   * @returns {Promise<{account: object}>}
   */
  async addSlaveAccount(account, nickname) {
    return postJson(API_ENDPOINTS.SLAVE_ACCOUNTS, { account, nickname });
  },

  /**
   * Delete slave account
   * @param {string} accountId
   * @returns {Promise<Response>}
   */
  async deleteSlaveAccount(accountId) {
    return del(`${API_ENDPOINTS.SLAVE_ACCOUNTS}/${accountId}`);
  }
};

// =====================================================
// TRADES API
// =====================================================

export const TradesAPI = {
  /**
   * Get trade history
   * @param {number} limit
   * @returns {Promise<{trades: Array}>}
   */
  async getHistory(limit = 100) {
    return getJson(`${API_ENDPOINTS.TRADES}?limit=${limit}`);
  },

  /**
   * Clear trade history
   * @returns {Promise<Response>}
   */
  async clearHistory() {
    return fetchWithAuth(`${API_ENDPOINTS.TRADES_CLEAR}?confirm=1`, { method: 'POST' });
  }
};

// =====================================================
// SETTINGS API
// =====================================================

export const SettingsAPI = {
  /**
   * Get all settings
   * @returns {Promise<object>}
   */
  async getAll() {
    return getJson(API_ENDPOINTS.SETTINGS);
  },

  /**
   * Save rate limits
   * @param {object} rateLimits
   * @returns {Promise<object>}
   */
  async saveRateLimits(rateLimits) {
    return postJson(API_ENDPOINTS.RATE_LIMITS, rateLimits);
  },

  /**
   * Get email settings
   * @returns {Promise<object>}
   */
  async getEmailSettings() {
    return getJson(API_ENDPOINTS.EMAIL_SETTINGS);
  },

  /**
   * Save email settings
   * @param {object} emailSettings
   * @returns {Promise<object>}
   */
  async saveEmailSettings(emailSettings) {
    return postJson(API_ENDPOINTS.EMAIL_SETTINGS, emailSettings);
  },

  /**
   * Send test email
   * @returns {Promise<object>}
   */
  async testEmail() {
    return postJson(API_ENDPOINTS.EMAIL_TEST, {});
  },

  /**
   * Get global secret
   * @returns {Promise<{secret: string}>}
   */
  async getGlobalSecret() {
    return getJson(API_ENDPOINTS.GLOBAL_SECRET);
  },

  /**
   * Save global secret
   * @param {string} secret
   * @returns {Promise<object>}
   */
  async saveGlobalSecret(secret) {
    return postJson(API_ENDPOINTS.GLOBAL_SECRET, { secret });
  }
};

// =====================================================
// SYSTEM API
// =====================================================

export const SystemAPI = {
  /**
   * Get system logs
   * @param {number} limit
   * @returns {Promise<{logs: Array}>}
   */
  async getLogs(limit = 300) {
    return getJson(`${API_ENDPOINTS.SYSTEM_LOGS}?limit=${limit}`);
  },

  /**
   * Clear system logs
   * @returns {Promise<Response>}
   */
  async clearLogs() {
    return fetchWithAuth(API_ENDPOINTS.SYSTEM_LOGS_CLEAR, { method: 'POST' });
  }
};

