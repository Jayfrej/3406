"""
Authentication middleware for Flask application
Provides session-based authentication for protected routes
"""
from functools import wraps
from flask import session, jsonify


def session_login_required(f):
    """
    Decorator to protect routes requiring authentication
    Checks if 'auth' key exists in session
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('auth'):
            return jsonify({'error': 'Auth required'}), 401
        return f(*args, **kwargs)
    return decorated_function

