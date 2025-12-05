"""
Authentication middleware for Flask application
Provides both session-based and Basic authentication for protected routes

Updated for Multi-User SaaS Support (Phase 2.5)
Reference: MIGRATION_ROADMAP.md Phase 2.5 - Update Auth Middleware
"""
from functools import wraps
from flask import session, jsonify, request
import os


def session_login_required(f):
    """
    Decorator to protect routes requiring session authentication.

    Updated for multi-user support:
    - NEW: Check for user_id in session (multi-user OAuth)
    - OLD: Check for auth key in session (legacy basic auth)

    Per MIGRATION_ROADMAP.md Phase 2.5
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # NEW: Check for user_id (multi-user OAuth session)
        if session.get('user_id'):
            return f(*args, **kwargs)

        # OLD: Check for auth flag (legacy session, keep during migration)
        if session.get('auth'):
            return f(*args, **kwargs)

        return jsonify({'error': 'Authentication required'}), 401
    return decorated_function


def admin_required(f):
    """
    Decorator to protect routes requiring admin privileges.

    Per MIGRATION_ROADMAP.md Phase 2.5:
    - Check if user is admin via is_admin session flag or ADMIN_EMAIL

    Returns 401 if not authenticated, 403 if not admin.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check for authentication first
        user_id = session.get('user_id')
        is_auth = session.get('auth')

        if not user_id and not is_auth:
            return jsonify({'error': 'Authentication required'}), 401

        # Check if user is admin
        # Method 1: Check is_admin flag in session (set during OAuth login)
        if session.get('is_admin'):
            return f(*args, **kwargs)

        # Method 2: Check email against ADMIN_EMAIL env var
        user_email = session.get('email')
        admin_email = os.getenv('ADMIN_EMAIL', '')

        if user_email and admin_email and user_email.lower() == admin_email.lower():
            return f(*args, **kwargs)

        # Method 3: Legacy basic auth admin (during migration)
        if is_auth and not user_id:
            # Legacy session - assume admin during migration period
            return f(*args, **kwargs)

        return jsonify({'error': 'Admin access required'}), 403
    return decorated_function


def require_auth(f):
    """
    Flexible Authentication decorator - Use for data endpoints
    Accepts EITHER:
    - Valid session cookie (session['user_id'] for multi-user), OR
    - Valid session cookie (session['auth'] for legacy), OR
    - Valid HTTP Basic Auth credentials
    Skips authentication for localhost health checks

    Updated for multi-user support.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # Skip auth for localhost health checks
        if request.remote_addr in ['127.0.0.1', 'localhost', '::1']:
            if request.path in ['/health', '/webhook/health']:
                return f(*args, **kwargs)

        # NEW: Check for user_id (multi-user OAuth session)
        if session.get('user_id'):
            return f(*args, **kwargs)

        # OLD: Check if user has valid legacy session
        if session.get('auth'):
            return f(*args, **kwargs)

        # Check Basic Auth as fallback
        auth = request.authorization

        if not auth:
            return jsonify({'error': 'Unauthorized'}), 401

        BASIC_USER = os.getenv('BASIC_USER', 'admin')
        BASIC_PASS = os.getenv('BASIC_PASS', '')

        if auth.username != BASIC_USER or auth.password != BASIC_PASS:
            return jsonify({'error': 'Unauthorized'}), 401

        return f(*args, **kwargs)
    return decorated


from typing import Optional

def get_current_user_id() -> Optional[str]:
    """
    Get current user_id from session.

    Returns:
        str: User ID or None if not authenticated
    """
    # Try multi-user session first
    user_id = session.get('user_id')
    if user_id:
        return user_id

    # Fallback for legacy sessions - find first admin user from database
    if session.get('auth'):
        try:
            from app.services.user_service import UserService
            user_service = UserService()
            admin_user = user_service.get_first_admin()
            if admin_user:
                return admin_user.get('user_id', 'admin_001')
        except Exception:
            pass
        # Ultimate fallback if database lookup fails
        return 'admin_001'

    return None


def get_current_user_email() -> Optional[str]:
    """
    Get current user's email from session.

    Returns:
        str: User email or None if not authenticated
    """
    return session.get('email')


