"""
Routes package - Exports all route blueprints
"""
from .webhook_routes import webhook_bp
from .account_routes import account_bp
from .copy_trading_routes import copy_trading_bp
from .settings_routes import settings_bp
from .system_routes import system_bp
from .broker_balance_routes import broker_balance_bp
from .ui_routes import ui_bp

__all__ = [
    'webhook_bp',
    'account_bp',
    'copy_trading_bp',
    'settings_bp',
    'system_bp',
    'broker_balance_bp',
    'ui_bp'
]

