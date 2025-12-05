"""
Routes package - Exports all route blueprints

Updated for Domain + License Key unified endpoint system
"""
from .webhook_routes import webhook_bp
from .account_routes import account_bp
from .copy_trading_routes import copy_trading_bp
from .settings_routes import settings_bp
from .system_routes import system_bp
from .broker_balance_routes import broker_balance_bp
from .command_routes import command_bp
from .ui_routes import ui_bp
from .user_routes import user_bp
from .unified_routes import unified_bp

__all__ = [
    'webhook_bp',
    'account_bp',
    'copy_trading_bp',
    'settings_bp',
    'system_bp',
    'broker_balance_bp',
    'command_bp',
    'ui_bp',
    'user_bp',
    'unified_bp'
]
