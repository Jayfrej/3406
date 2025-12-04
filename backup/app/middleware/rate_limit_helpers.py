"""
Rate Limit Helpers
Custom functions for rate limiting
"""
from flask import request


def is_localhost():
    """Check if request is from localhost"""
    return request.remote_addr in ['127.0.0.1', 'localhost', '::1']


def get_rate_limit_key():
    """
    Custom key function for rate limiting
    Localhost gets separate, higher limits
    """
    from flask_limiter.util import get_remote_address

    if is_localhost():
        return f"localhost-{get_remote_address()}"

    return get_remote_address()

