/**
 * @file helpers.js
 * @description Utility helper functions extracted from app.js
 * @module utils/helpers
 */

// =====================================================
// STRING UTILITIES
// =====================================================

/**
 * Escape HTML entities to prevent XSS
 * @param {*} text - Text to escape
 * @returns {string} Escaped text
 */
export function escape(text) {
  return String(text ?? '').replace(/[&<>"]/g, s => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;'
  }[s]));
}

/**
 * Alternative escape using DOM
 * @param {*} text - Text to escape
 * @returns {string} Escaped text
 */
export function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// =====================================================
// DATE FORMATTING
// =====================================================

/**
 * Format date for display
 * @param {string} dateString - ISO date string
 * @returns {string} Formatted date
 */
export function formatDate(dateString) {
  const date = new Date(dateString);
  if (isNaN(date)) return '-';

  const now = new Date();
  const diff = now - date;
  const day = 1000 * 60 * 60 * 24;
  const d = Math.floor(diff / day);

  if (d === 0) return 'Today ' + date.toLocaleTimeString();
  if (d === 1) return 'Yesterday ' + date.toLocaleTimeString();
  if (d < 7) return `${d} days ago`;
  return date.toLocaleDateString();
}

/**
 * Format relative time (e.g., "5m ago")
 * @param {string} lastSeenStr - ISO date string
 * @returns {string} Formatted relative time
 */
export function formatLastSeen(lastSeenStr) {
  if (!lastSeenStr) return '-';

  const lastSeen = new Date(lastSeenStr);
  const now = new Date();
  const diffSeconds = Math.floor((now - lastSeen) / 1000);

  if (diffSeconds < 10) {
    return 'Just now';
  } else if (diffSeconds < 60) {
    return `${diffSeconds}s ago`;
  } else if (diffSeconds < 3600) {
    const diffMinutes = Math.floor(diffSeconds / 60);
    return `${diffMinutes}m ago`;
  } else if (diffSeconds < 86400) {
    const diffHours = Math.floor(diffSeconds / 3600);
    return `${diffHours}h ago`;
  } else {
    return lastSeen.toLocaleString();
  }
}

/**
 * Format timestamp for system logs
 * @param {string} timestamp - ISO timestamp
 * @returns {string} Formatted timestamp
 */
export function formatLogTimestamp(timestamp) {
  return new Date(timestamp).toLocaleString('en-GB', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });
}

// =====================================================
// NUMBER FORMATTING
// =====================================================

/**
 * Format price with 5 decimal places
 * @param {*} value - Price value
 * @returns {string} Formatted price or '-'
 */
export function formatPrice(value) {
  if (value === '' || value === null || value === undefined) return '-';
  return Number(value).toFixed(5);
}

/**
 * Format volume with 2 decimal places
 * @param {*} value - Volume value
 * @returns {string} Formatted volume or '-'
 */
export function formatVolume(value) {
  if (value === '' || value === null || value === undefined) return '-';
  return Number(value).toFixed(2);
}

// =====================================================
// TOKEN GENERATION
// =====================================================

/**
 * Generate API token for copy trading pairs
 * @returns {string} Generated token
 */
export function generateApiToken() {
  return 'tk_' + Math.random().toString(36).substr(2, 9) + Date.now().toString(36);
}

/**
 * Generate secret key (32 characters)
 * @returns {string} Generated secret key
 */
export function generateSecretKey() {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  let secret = '';
  for (let i = 0; i < 32; i++) {
    secret += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return secret;
}

// =====================================================
// CLIPBOARD UTILITIES
// =====================================================

/**
 * Copy text to clipboard
 * @param {string} text - Text to copy
 * @returns {Promise<boolean>} Success status
 */
export async function copyToClipboard(text) {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return true;
    } else {
      // Fallback for older browsers
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.setAttribute('readonly', '');
      ta.style.position = 'fixed';
      ta.style.left = '-9999px';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.focus();
      ta.select();
      const ok = document.execCommand('copy');
      document.body.removeChild(ta);
      if (!ok) throw new Error('execCommand copy failed');
      return true;
    }
  } catch (err) {
    console.error('Clipboard copy failed:', err);
    return false;
  }
}

// =====================================================
// VALIDATION UTILITIES
// =====================================================

/**
 * Validate email format
 * @param {string} email - Email to validate
 * @returns {boolean} Is valid
 */
export function isValidEmail(email) {
  const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailPattern.test(email);
}

/**
 * Validate rate limit format
 * @param {string} value - Rate limit string
 * @returns {boolean} Is valid
 */
export function isValidRateLimit(value) {
  const rateLimitPattern = /^\d+\s+per\s+(minute|hour|day)$/i;
  const exemptPattern = /^exempt$/i;
  return rateLimitPattern.test(value) || exemptPattern.test(value);
}

// =====================================================
// ACTION BADGE UTILITIES
// =====================================================

/**
 * Get CSS class for action badge
 * @param {string} action - Action type
 * @returns {string} CSS class
 */
export function getActionBadgeClass(action) {
  if (!action) return 'default';

  const actionLower = String(action).toLowerCase().trim();

  const actionMap = {
    'buy': 'buy',
    'sell': 'sell',
    'close': 'close',
    'modify': 'modify',
    'open': 'buy',
    'long': 'buy',
    'short': 'sell',
    'call': 'buy',
    'put': 'sell',
    'close_all': 'close',
    'close-all': 'close',
    'close_symbol': 'close',
    'close-symbol': 'close',
    'buy_stop': 'buy_stop',
    'buy-stop': 'buy-stop',
    'sell_stop': 'sell_stop',
    'sell-stop': 'sell-stop',
    'buy_limit': 'buy_limit',
    'buy-limit': 'buy-limit',
    'sell_limit': 'sell_limit',
    'sell-limit': 'sell-limit'
  };

  return actionMap[actionLower] || 'default';
}

/**
 * Format action as badge HTML
 * @param {string} action - Action type
 * @returns {string} HTML badge
 */
export function formatActionBadge(action) {
  if (!action) return '<span class="action-badge default">-</span>';

  const actionText = String(action).toUpperCase().trim();

  // Pending orders - gray background
  if (actionText.includes('BUY STOP') || actionText.includes('BUY_STOP')) {
    return '<span class="action-badge" style="background-color: #6c757d; color: white;">BUY STOP</span>';
  }
  if (actionText.includes('SELL STOP') || actionText.includes('SELL_STOP')) {
    return '<span class="action-badge" style="background-color: #6c757d; color: white;">SELL STOP</span>';
  }
  if (actionText.includes('BUY LIMIT') || actionText.includes('BUY_LIMIT')) {
    return '<span class="action-badge" style="background-color: #6c757d; color: white;">BUY LIMIT</span>';
  }
  if (actionText.includes('SELL LIMIT') || actionText.includes('SELL_LIMIT')) {
    return '<span class="action-badge" style="background-color: #6c757d; color: white;">SELL LIMIT</span>';
  }

  // Normalize action names
  let normalizedAction = actionText;

  if (normalizedAction.includes('DEAL') || normalizedAction.includes('POSITION') || normalizedAction.includes('ORDER')) {
    if (normalizedAction.includes('CLOSE')) {
      normalizedAction = 'CLOSE';
    } else if (normalizedAction.includes('MODIFY')) {
      normalizedAction = 'MODIFY';
    } else if (normalizedAction.includes('ADD') || normalizedAction.includes('OPEN')) {
      normalizedAction = 'OPEN';
    }
  }

  if (normalizedAction === 'LONG' || normalizedAction === 'CALL') normalizedAction = 'BUY';
  if (normalizedAction === 'SHORT' || normalizedAction === 'PUT') normalizedAction = 'SELL';
  if (normalizedAction.includes('CLOSE_ALL') || normalizedAction.includes('CLOSE_SYMBOL')) normalizedAction = 'CLOSE';

  const badgeClass = getActionBadgeClass(normalizedAction);

  return `<span class="action-badge ${badgeClass}">${escape(normalizedAction)}</span>`;
}

// =====================================================
// FIELD UTILITIES
// =====================================================

/**
 * Get value from form element
 * @param {HTMLElement} el - Form element
 * @returns {string} Element value
 */
export function getFieldValue(el) {
  if (!el) return '';
  const v = (typeof el.value !== 'undefined' && el.value !== null) ? el.value : el.textContent;
  return (v || '').toString().trim();
}

/**
 * Set value on form element
 * @param {HTMLElement} el - Form element
 * @param {*} val - Value to set
 */
export function setFieldValue(el, val) {
  if (!el) return;
  if (typeof el.value !== 'undefined' && el.tagName &&
      (el.tagName === 'INPUT' || el.tagName === 'SELECT' || el.tagName === 'TEXTAREA')) {
    el.value = val;
  } else {
    el.textContent = val;
  }
}

// =====================================================
// URL UTILITIES
// =====================================================

/**
 * Get base URL from webhook URL
 * @param {string} webhookUrl - Webhook URL
 * @returns {string} Base URL
 */
export function getBaseUrl(webhookUrl) {
  if (webhookUrl) {
    try {
      const url = new URL(webhookUrl);
      return `${url.protocol}//${url.host}`;
    } catch (e) {
      // Fall through to default
    }
  }
  return `${window.location.protocol}//${window.location.host}`;
}

/**
 * Get copy trading endpoint from webhook URL
 * @param {string} webhookUrl - Webhook URL
 * @returns {string} Copy trading endpoint
 */
export function getCopyTradingEndpoint(webhookUrl) {
  return `${getBaseUrl(webhookUrl)}/api/copy/trade`;
}

