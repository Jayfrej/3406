/**
 * @file sse.js
 * @description Server-Sent Events service for real-time updates
 * @module services/sse
 */

import appState from '../config/state.js';
import { API_ENDPOINTS } from '../config/constants.js';

/**
 * SSE Service for real-time event subscriptions
 */
class SSEService {
  constructor() {
    this.reconnectDelay = 5000;
  }

  /**
   * Subscribe to trade events
   * @param {Function} onMessage - Message handler
   * @param {Function} onHistoryCleared - History cleared handler
   * @param {Function} onAccountDeleted - Account deleted handler
   */
  subscribeTradeEvents(onMessage, onHistoryCleared, onAccountDeleted) {
    if (!('EventSource' in window)) return;

    try {
      const es = new EventSource(API_ENDPOINTS.EVENTS_TRADES);

      es.onmessage = (evt) => {
        try {
          const data = JSON.parse(evt.data);

          if (data.event === 'history_cleared') {
            if (onHistoryCleared) onHistoryCleared();
            return;
          }

          if (data.event === 'account_deleted' && data.account) {
            if (onAccountDeleted) onAccountDeleted(data.account);
            return;
          }

          if (onMessage) onMessage(data);
        } catch (e) {
          console.warn('Invalid trade event:', e);
        }
      };

      es.onerror = () => {
        console.warn('[SSE] Trade events connection error');
      };

      appState.setTradeEventSource(es);
    } catch (e) {
      console.warn('Trade SSE unavailable', e);
    }
  }

  /**
   * Subscribe to copy trading events
   * @param {Function} onMessage - Message handler
   * @param {Function} onHistoryCleared - History cleared handler
   */
  subscribeCopyEvents(onMessage, onHistoryCleared) {
    if (!('EventSource' in window)) return;

    try {
      const es = new EventSource(API_ENDPOINTS.EVENTS_COPY);

      es.onmessage = (evt) => {
        try {
          const data = JSON.parse(evt.data);

          if (data.event === 'copy_history_cleared') {
            if (onHistoryCleared) onHistoryCleared();
            return;
          }

          if (onMessage) onMessage(data);
        } catch (e) {
          console.warn('Invalid copy event:', e);
        }
      };

      appState.setCopyEventSource(es);
    } catch (e) {
      console.warn('Copy SSE unavailable', e);
    }
  }

  /**
   * Subscribe to system log events
   * @param {Function} onLog - Log handler
   * @param {Function} onAccountDeleted - Account deleted handler
   * @param {Function} onPairDeleted - Pair deleted handler
   */
  subscribeSystemLogs(onLog, onAccountDeleted, onPairDeleted) {
    if (!('EventSource' in window)) return;

    try {
      const es = new EventSource(API_ENDPOINTS.EVENTS_SYSTEM);

      es.onmessage = (evt) => {
        try {
          const data = JSON.parse(evt.data);
          if (onLog) {
            onLog(data.type || 'info', data.message || '', data.timestamp);
          }
        } catch (e) {
          console.warn('Invalid system log event:', e);
        }
      };

      // Account deleted event
      es.addEventListener('account_deleted', async (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log('[SSE] Account deleted event:', data);
          if (onAccountDeleted) {
            await onAccountDeleted(data);
          }
        } catch (e) {
          console.error('[SSE] Error handling account_deleted:', e);
        }
      });

      // Pair deleted event
      es.addEventListener('pair_deleted', async (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log('[SSE] Pair deleted event:', data);
          if (onPairDeleted) {
            await onPairDeleted(data);
          }
        } catch (e) {
          console.error('[SSE] Error handling pair_deleted:', e);
        }
      });

      es.onerror = (error) => {
        console.error('[SSE] System logs connection error:', error);
        // Reconnect after delay
        setTimeout(() => {
          this.subscribeSystemLogs(onLog, onAccountDeleted, onPairDeleted);
        }, this.reconnectDelay);
      };

      appState.setSystemEventSource(es);
    } catch (e) {
      console.warn('System logs SSE unavailable', e);
    }
  }

  /**
   * Unsubscribe from all events
   */
  unsubscribeAll() {
    appState.closeAllEventSources();
  }
}

// Export singleton
const sseService = new SSEService();
export default sseService;

// Also export class for testing
export { SSEService };

