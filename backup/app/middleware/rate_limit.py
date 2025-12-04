"""
Rate limiting configuration and helpers
"""
import os
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


def create_limiter(app):
    """
    Create and configure Flask-Limiter instance

    Args:
        app: Flask application instance

    Returns:
        Limiter: Configured Flask-Limiter instance
    """
    try:
        limiter = Limiter(
            key_func=get_remote_address,
            default_limits=["100 per hour"]
        )
        limiter.init_app(app)
    except TypeError:
        # Fallback for older Flask-Limiter versions
        limiter = Limiter(
            app,
            key_func=get_remote_address,
            default_limits=["100 per hour"]
        )

    return limiter


def get_command_api_rate_limit():
    """
    Get command API rate limit from settings (called at runtime by flask-limiter)

    Returns:
        str: Rate limit string (e.g., '60 per minute')
    """
    try:
        from app.services.settings_service import SettingsService
        settings_service = SettingsService()
        settings = settings_service.load_settings()
        return settings.get('rate_limits', {}).get('command_api', '60 per minute')
    except Exception:
        return '60 per minute'

