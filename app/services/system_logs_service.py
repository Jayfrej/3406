"""
System Logs Service
Manages in-memory system logs with SSE broadcasting

Updated for Multi-User SaaS: Logs now include user_id for filtering
"""
import time
import re
import json
import queue
import threading
import logging
from datetime import datetime
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class SystemLogsService:
    """Service for managing system logs with real-time broadcasting and user filtering"""

    MAX_LOGS = 300

    def __init__(self):
        self.logs = []
        self.logs_lock = threading.Lock()
        self.sse_clients = []
        self.sse_lock = threading.Lock()

    def add_log(self, log_type: str, message: str, user_id: Optional[str] = None, accounts: Optional[List[str]] = None) -> Dict:
        """
        Add a new system log entry

        Args:
            log_type: Log type ('info', 'success', 'warning', 'error')
            message: Log message
            user_id: User ID who triggered this log (for filtering)
            accounts: List of account numbers related to this log (for filtering)

        Returns:
            dict: Created log entry
        """
        with self.logs_lock:
            # Try to extract account numbers from message if not provided
            extracted_accounts = accounts or []
            if not extracted_accounts:
                # Extract account numbers from message (common patterns)
                acc_matches = re.findall(r'(?:Acc(?:ount)?[:\s]*|account\s*)(\d{6,12})', message, re.IGNORECASE)
                if acc_matches:
                    extracted_accounts = list(set(acc_matches))
            
            log_entry = {
                'id': time.time() + id(message),
                'type': log_type or 'info',
                'message': message or '',
                'timestamp': datetime.now().isoformat(),
                'user_id': user_id,
                'accounts': extracted_accounts
            }

            # Add at the beginning (most recent first)
            self.logs.insert(0, log_entry)

            # Limit log size
            if len(self.logs) > self.MAX_LOGS:
                self.logs.pop()

            # Broadcast to SSE clients
            self._broadcast_log(log_entry)

            return log_entry

    def get_logs(self, limit: int = 300, user_id: Optional[str] = None, user_accounts: Optional[Set[str]] = None) -> List[Dict]:
        """
        Get system logs, optionally filtered by user

        Args:
            limit: Maximum number of logs to return
            user_id: Filter logs by user_id (None = all logs for admin)
            user_accounts: Set of account numbers belonging to user (for filtering)

        Returns:
            list: List of log entries
        """
        limit = max(1, min(limit, self.MAX_LOGS))

        with self.logs_lock:
            if user_id is None and user_accounts is None:
                # No filter - return all (admin mode)
                return self.logs[:limit]
            
            # Filter logs for specific user
            filtered_logs = []
            for log in self.logs:
                # Include if log belongs to this user
                if log.get('user_id') == user_id:
                    filtered_logs.append(log)
                    continue
                
                # Include if log mentions any of user's accounts
                if user_accounts:
                    log_accounts = set(log.get('accounts', []))
                    # Also check message for account numbers
                    message = log.get('message', '')
                    for acc in user_accounts:
                        if acc in log_accounts or acc in message:
                            filtered_logs.append(log)
                            break
                    continue
                
                # Include general system logs (no user_id and no accounts)
                if not log.get('user_id') and not log.get('accounts'):
                    # Skip sensitive system logs
                    msg_lower = log.get('message', '').lower()
                    if any(kw in msg_lower for kw in ['login', 'logout', 'cleared', 'unauthorized']):
                        continue
                    filtered_logs.append(log)
                
                if len(filtered_logs) >= limit:
                    break
            
            return filtered_logs[:limit]

    def get_logs_by_user(self, user_id: str, user_accounts: Set[str], limit: int = 300) -> List[Dict]:
        """
        Get logs for a specific user only

        Args:
            user_id: User ID to filter by
            user_accounts: Set of account numbers belonging to this user
            limit: Maximum number of logs

        Returns:
            list: Filtered log entries
        """
        return self.get_logs(limit=limit, user_id=user_id, user_accounts=user_accounts)

    def clear_logs(self, user_id: Optional[str] = None) -> bool:
        """
        Clear system logs (all for admin, or user's own logs only)

        Args:
            user_id: If provided, only clear logs for this user

        Returns:
            bool: True if cleared successfully
        """
        try:
            with self.logs_lock:
                if user_id:
                    # Only clear logs belonging to this user
                    self.logs = [log for log in self.logs if log.get('user_id') != user_id]
                else:
                    # Clear all (admin)
                    self.logs.clear()

            self.add_log('info', 'System logs cleared', user_id=user_id)
            return True
        except Exception as e:
            logger.error(f"[SYSTEM_LOGS] Error clearing logs: {e}")
            return False

    def add_sse_client(self, client_queue: queue.Queue):
        """Add an SSE client queue"""
        with self.sse_lock:
            self.sse_clients.append(client_queue)

    def remove_sse_client(self, client_queue: queue.Queue):
        """Remove an SSE client queue"""
        with self.sse_lock:
            try:
                self.sse_clients.remove(client_queue)
            except ValueError:
                pass

    def _broadcast_log(self, log_entry: Dict):
        """
        Broadcast log entry to all SSE clients

        Args:
            log_entry: Log entry to broadcast
        """
        data = f"data: {json.dumps(log_entry)}\n\n"

        with self.sse_lock:
            dead_clients = []
            for client_queue in self.sse_clients:
                try:
                    client_queue.put(data, block=False)
                except queue.Full:
                    dead_clients.append(client_queue)
                except Exception:
                    dead_clients.append(client_queue)

            # Remove dead clients
            for client in dead_clients:
                try:
                    self.sse_clients.remove(client)
                except:
                    pass

