"""
Webhooks Module - TradingView Signal Processing

Handles incoming webhook signals from TradingView and other sources:
- Signal validation and authentication
- Symbol mapping and translation
- Command preparation for MT5 EA
- Trade history recording
"""

from .routes import webhooks_bp

__all__ = ['webhooks_bp']

