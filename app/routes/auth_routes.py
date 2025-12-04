"""
Authentication Routes for Multi-User SaaS

Handles:
- Google OAuth login flow
- Session management
- Logout

Reference: MIGRATION_ROADMAP.md Phase 2.4
"""

import os
import logging
from flask import Blueprint, redirect, url_for, session, jsonify, request

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login/google')
def google_login():
    """
    Redirect to Google OAuth.

    Per MIGRATION_ROADMAP.md Phase 2.4
    """
    from app.services.google_oauth_service import GoogleOAuthService

    oauth_service = GoogleOAuthService()

    if not oauth_service.is_configured():
        logger.error("[AUTH] Google OAuth not configured")
        return jsonify({'error': 'Google OAuth not configured'}), 500

    # Generate authorization URL with state for CSRF protection
    auth_url, state = oauth_service.get_authorization_url()

    # Store state in session for verification
    session['oauth_state'] = state

    logger.info(f"[AUTH] Redirecting to Google OAuth")
    return redirect(auth_url)


@auth_bp.route('/auth/google/callback')
def google_callback():
    """
    Handle Google OAuth callback, create session.

    Per MIGRATION_ROADMAP.md Phase 2.4
    """
    from app.services.google_oauth_service import GoogleOAuthService
    from app.services.user_service import UserService
    from app.services.token_service import TokenService

    # Get code and state from callback
    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')

    # Handle errors
    if error:
        logger.error(f"[AUTH] OAuth error: {error}")
        return redirect('/login?error=' + error)

    if not code:
        logger.error("[AUTH] No authorization code received")
        return redirect('/login?error=no_code')

    # Verify state (CSRF protection)
    stored_state = session.pop('oauth_state', None)
    if not stored_state or state != stored_state:
        logger.error("[AUTH] Invalid OAuth state - possible CSRF attack")
        return redirect('/login?error=invalid_state')

    try:
        oauth_service = GoogleOAuthService()
        user_service = UserService()
        token_service = TokenService()

        # Exchange code for tokens
        token_data = oauth_service.exchange_code_for_token(code)
        access_token = token_data.get('access_token')

        if not access_token:
            logger.error("[AUTH] No access token in response")
            return redirect('/login?error=no_token')

        # Get user info from Google
        google_user = oauth_service.get_user_info(access_token)

        if not google_user.get('email'):
            logger.error("[AUTH] No email in Google response")
            return redirect('/login?error=no_email')

        # Create or update user in database
        user = user_service.create_or_update_user(google_user)

        # Check if user is active
        if not user.get('is_active', True):
            logger.warning(f"[AUTH] Inactive user attempted login: {user['email']}")
            return redirect('/login?error=account_disabled')

        # Generate webhook token for user
        webhook_token = token_service.generate_webhook_token(user['user_id'])

        # Set session data
        session.clear()
        session['user_id'] = user['user_id']
        session['email'] = user['email']
        session['name'] = user.get('name', '')
        session['picture'] = user.get('picture', '')
        session['is_admin'] = user.get('is_admin', False)
        session['auth'] = True  # For backward compatibility
        session.permanent = True

        logger.info(f"[AUTH] User logged in successfully: {user['email']} (admin: {user.get('is_admin')})")

        # Redirect to dashboard
        return redirect('/')

    except Exception as e:
        logger.exception(f"[AUTH] OAuth callback error: {e}")
        return redirect('/login?error=auth_failed')


@auth_bp.route('/logout', methods=['GET', 'POST'])
def logout():
    """
    Clear session and logout.

    Per MIGRATION_ROADMAP.md Phase 2.4
    """
    user_email = session.get('email', 'unknown')
    session.clear()

    logger.info(f"[AUTH] User logged out: {user_email}")

    return redirect('/login')


@auth_bp.route('/auth/status')
def auth_status():
    """
    Return current user info for frontend.

    Per MIGRATION_ROADMAP.md Phase 2.4
    """
    if session.get('user_id') or session.get('auth'):
        return jsonify({
            'authenticated': True,
            'user_id': session.get('user_id'),
            'email': session.get('email', ''),
            'name': session.get('name', ''),
            'picture': session.get('picture', ''),
            'is_admin': session.get('is_admin', False)
        })

    return jsonify({
        'authenticated': False
    })


@auth_bp.route('/auth/webhook-token')
def get_webhook_token():
    """
    Get current user's webhook token and URL.
    """
    from app.services.token_service import TokenService
    from app.middleware.auth import get_current_user_id

    user_id = get_current_user_id()

    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401

    token_service = TokenService()
    webhook_url = token_service.get_webhook_url(user_id)

    return jsonify({
        'webhook_url': webhook_url,
        'user_id': user_id
    })


@auth_bp.route('/auth/rotate-token', methods=['POST'])
def rotate_webhook_token():
    """
    Generate new webhook token for current user.
    """
    from app.services.token_service import TokenService
    from app.middleware.auth import get_current_user_id

    user_id = get_current_user_id()

    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401

    token_service = TokenService()
    new_token = token_service.rotate_token(user_id)
    webhook_url = token_service.get_webhook_url(user_id)

    logger.info(f"[AUTH] Rotated webhook token for user: {user_id}")

    return jsonify({
        'success': True,
        'webhook_url': webhook_url
    })

