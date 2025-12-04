/**
 * @file constants.js
 * @description Global constants and configuration for MT5 Trading Bot UI
 * @module config/constants
 */

// =====================================================
// API ENDPOINTS
// =====================================================
export const API_ENDPOINTS = {
  // Account Management
  ACCOUNTS: '/accounts',
  WEBHOOK_ACCOUNTS: '/webhook-accounts',
  WEBHOOK_URL: '/webhook-url',

  // Copy Trading
  PAIRS: '/api/pairs',
  COPY_HISTORY: '/api/copy/history',
  COPY_TRADE: '/api/copy/trade',
  MASTER_ACCOUNTS: '/api/copy/master-accounts',
  SLAVE_ACCOUNTS: '/api/copy/slave-accounts',

  // Settings
  SETTINGS: '/api/settings',
  RATE_LIMITS: '/api/settings/rate-limits',
  EMAIL_SETTINGS: '/api/settings/email',
  EMAIL_TEST: '/api/settings/email/test',
  GLOBAL_SECRET: '/settings/secret',

  // System
  SYSTEM_LOGS: '/api/system/logs',
  SYSTEM_LOGS_CLEAR: '/api/system/logs/clear',

  // Trades
  TRADES: '/trades',
  TRADES_CLEAR: '/trades/clear',

  // Auth
  LOGIN: '/login',

  // SSE Events
  EVENTS_TRADES: '/events/trades',
  EVENTS_COPY: '/events/copy-trades',
  EVENTS_SYSTEM: '/events/system-logs'
};

// =====================================================
// UI CONFIGURATION
// =====================================================
export const UI_CONFIG = {
  // Auto-refresh intervals (in milliseconds)
  AUTO_REFRESH_INTERVAL: 30000,         // 30 seconds - matches heartbeat
  COPY_HISTORY_REFRESH: 5000,           // 5 seconds

  // History limits
  MAX_HISTORY_ITEMS: 100,
  MAX_COPY_HISTORY: 100,
  MAX_SYSTEM_LOGS: 300,

  // Toast duration
  TOAST_DURATION: 5000,                 // 5 seconds

  // Animation delays
  MODAL_CLOSE_DELAY: 300,               // ms
  HIGHLIGHT_DURATION: 2000              // ms
};

// =====================================================
// PAGES
// =====================================================
export const PAGES = {
  ACCOUNTS: 'accounts',
  WEBHOOK: 'webhook',
  COPYTRADING: 'copytrading',
  SYSTEM: 'system',
  SETTINGS: 'settings'
};

// =====================================================
// JSON EXAMPLES (for Webhook page)
// =====================================================
export const JSON_EXAMPLES = [
  {
    title: "Market:",
    json: `{
  "account_number": "1123456",
  "symbol": "XAUUSD",
  "action": "BUY",
  "volume": 0.01,
  "take_profit": 2450.0,
  "stop_loss": 2400.0,
  "secret": "XXX"
}`
  },
  {
    title: "Market 2:",
    json: `{
  "account_number": "xxxx",
  "symbol": "{{ticker}}",
  "action": "{{strategy.order.comment}}",
  "volume": "{{strategy.order.contracts}}",
  "secret": "XXX"
}`
  },
  {
    title: "Limit:",
    json: `{
  "account_number": "1123456",
  "symbol": "EURUSD",
  "action": "SELL",
  "order_type": "limit",
  "price": 1.0950,
  "volume": 0.1,
  "secret": "XXX"
}`
  },
  {
    title: "Limit 2:",
    json: `{
  "account_number": "xxxx",
  "symbol": "{{ticker}}",
  "action": "{{strategy.order.comment}}",
  "order_type": "limit",
  "price": 2425,
  "take_profit": 2450,
  "stop_loss": 2400.0,
  "volume": "{{strategy.order.contracts}}",
  "secret": "XXX"
}`
  },
  {
    title: "Close:",
    json: `{
  "account_number": "1123456",
  "symbol": "XAUUSD",
  "order_type": "close",
  "secret": "XXX"
}`
  },
  {
    title: "Close 2:",
    json: `{
  "account_number": "xxxx",
  "symbol": "{{ticker}}",
  "action": "close",
  "volume": "{{strategy.order.contracts}}",
  "secret": "XXX"
}`
  }
];

// =====================================================
// RATE LIMIT DEFAULTS
// =====================================================
export const RATE_LIMIT_DEFAULTS = {
  ACCOUNTS: 'exempt',
  WEBHOOK: '10 per minute',
  API: '100 per hour',
  COMMAND_API: '60 per minute'
};

// =====================================================
// VALIDATION PATTERNS
// =====================================================
export const VALIDATION = {
  RATE_LIMIT_PATTERN: /^\d+\s+per\s+(minute|hour|day)$/i,
  EXEMPT_PATTERN: /^exempt$/i,
  EMAIL_PATTERN: /^[^\s@]+@[^\s@]+\.[^\s@]+$/
};

// =====================================================
// TOAST TYPES
// =====================================================
export const TOAST_TYPES = {
  SUCCESS: 'success',
  ERROR: 'error',
  WARNING: 'warning',
  INFO: 'info'
};

// =====================================================
// TOAST ICONS
// =====================================================
export const TOAST_ICONS = {
  success: 'check-circle',
  error: 'exclamation-circle',
  warning: 'exclamation-triangle',
  info: 'info-circle'
};

// =====================================================
// TOAST TITLES
// =====================================================
export const TOAST_TITLES = {
  success: 'Success',
  error: 'Error',
  warning: 'Warning',
  info: 'Information'
};

