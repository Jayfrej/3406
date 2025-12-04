"""
System Logs Service
Manages in-memory system logs with SSE broadcasting
"""
import time
import json
import queue
import threading
import logging
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class SystemLogsService:
    """Service for managing system logs with real-time broadcasting"""

    MAX_LOGS = 300

    def __init__(self):
        self.logs = []
        self.logs_lock = threading.Lock()
        self.sse_clients = []
        self.sse_lock = threading.Lock()

    def add_log(self, log_type: str, message: str) -> Dict:
        """
        Add a new system log entry

        Args:
            log_type: Log type ('info', 'success', 'warning', 'error')
            message: Log message

        Returns:
            dict: Created log entry
        """
        with self.logs_lock:
            log_entry = {
                'id': time.time() + id(message),
                'type': log_type or 'info',
                'message': message or '',
                'timestamp': datetime.now().isoformat()
            }

            # Add at the beginning (most recent first)
            self.logs.insert(0, log_entry)

            # Limit log size
            if len(self.logs) > self.MAX_LOGS:
                self.logs.pop()

            # Broadcast to SSE clients
            self._broadcast_log(log_entry)

            return log_entry

    def get_logs(self, limit: int = 300) -> List[Dict]:
        """
        Get system logs

        Args:
            limit: Maximum number of logs to return

        Returns:
            list: List of log entries
        """
        limit = max(1, min(limit, self.MAX_LOGS))

        with self.logs_lock:
            return self.logs[:limit]

    def clear_logs(self) -> bool:
        """
        Clear all system logs

        Returns:
            bool: True if cleared successfully
        """
        try:
            with self.logs_lock:
                self.logs.clear()

            self.add_log('info', 'System logs cleared')
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

