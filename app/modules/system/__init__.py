"""
System Module - System Settings and Logs

Handles system-wide configuration and monitoring:
- Settings management (rate limits, email)
- System logs (view, clear)
- System information
"""

from .routes import system_bp

__all__ = ['system_bp']

