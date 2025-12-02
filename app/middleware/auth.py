"""
Authentication middleware for Flask application
Provides both session-based and Basic authentication for protected routes
"""
from functools import wraps
from flask import session, jsonify, request
import os


def session_login_required(f):
    """
    Decorator to protect routes requiring session authentication
    Use ONLY for /login endpoint
    Checks if 'auth' key exists in session
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('auth'):
            return jsonify({'error': 'Auth required'}), 401
        return f(*args, **kwargs)
    return decorated_function


def require_auth(f):
    """
    Flexible Authentication decorator - Use for data endpoints
    Accepts EITHER:
    - Valid session cookie (session['auth'] == True), OR
    - Valid HTTP Basic Auth credentials
    Skips authentication for localhost health checks
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # Skip auth for localhost health checks
        if request.remote_addr in ['127.0.0.1', 'localhost', '::1']:
            if request.path in ['/health', '/webhook/health']:
                return f(*args, **kwargs)

        # Check if user has valid session
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


