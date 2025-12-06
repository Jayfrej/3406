"""
User Routes - License Key and User Management API

Provides endpoints for:
- Get user profile and license key
- Regenerate license key
- Get webhook URL

Reference: Domain + License Key unified endpoint system
"""
import os
import logging
from flask import Blueprint, request, jsonify, session
from app.middleware.auth import require_auth, session_login_required, get_current_user_id

logger = logging.getLogger(__name__)

# Create blueprint
user_bp = Blueprint('user', __name__)

# Inject dependencies
user_service = None
system_logs_service = None

EXTERNAL_BASE_URL = os.getenv('EXTERNAL_BASE_URL', 'http://localhost:5000')


def init_user_routes(us, sls):
    """
    Initialize user routes with dependencies

    Args:
        us: UserService instance
        sls: SystemLogsService instance
    """
    global user_service, system_logs_service
    user_service = us
    system_logs_service = sls


@user_bp.route('/api/user/profile', methods=['GET'])
@require_auth
def get_user_profile():
    """
    Get current user's profile.

    Returns:
        JSON with user profile data including license key
    """
    try:
        user_id = get_current_user_id()

        if not user_id:
            return jsonify({'error': 'Not authenticated'}), 401

        user = user_service.get_user_by_id(user_id)

        if not user:
            return jsonify({'error': 'User not found'}), 404

        # Get license key
        license_key = user_service.get_user_license_key(user_id)
        webhook_url = f"{EXTERNAL_BASE_URL}/{license_key}" if license_key else None

        # Get user stats
        stats = user_service.get_user_stats(user_id)

        return jsonify({
            'success': True,
            'user': {
                'user_id': user['user_id'],
                'email': user['email'],
                'name': user.get('name'),
                'picture': user.get('picture'),
                'is_admin': user.get('is_admin', False),
                'created_at': user.get('created_at'),
                'last_login': user.get('last_login')
            },
            'credentials': user_service.get_user_credentials(user_id),
            'stats': stats
        })

    except Exception as e:
        logger.error(f"[USER_PROFILE] Error: {e}")
        return jsonify({'error': str(e)}), 500


@user_bp.route('/api/user/credentials', methods=['GET'])
@require_auth
def get_user_credentials():
    """
    Get user's license key AND webhook secret together.

    This returns both pieces needed for secure webhook configuration:
    - license_key: Goes in the URL
    - webhook_secret: Goes in the request body (if set)
    - has_secret: Whether user has configured a secret

    Returns:
        JSON with license_key, webhook_secret, has_secret, and webhook_url
    """
    try:
        user_id = get_current_user_id()

        if not user_id:
            return jsonify({'error': 'Not authenticated'}), 401

        credentials = user_service.get_user_credentials(user_id)

        if not credentials:
            return jsonify({'error': 'Failed to get credentials'}), 500

        has_secret = credentials.get('has_secret', False)
        webhook_secret = credentials.get('webhook_secret')

        # Build response
        response = {
            'success': True,
            'license_key': credentials['license_key'],
            'webhook_secret': webhook_secret,
            'has_secret': has_secret,
            'webhook_url': credentials['webhook_url'],
        }

        # Instructions based on whether secret is configured
        if has_secret and webhook_secret:
            response['instructions'] = {
                'tradingview': f'Webhook URL: {credentials["webhook_url"]}',
                'alert_body': f'{{"secret": "{webhook_secret}", "action": "{{{{strategy.order.action}}}}", "symbol": "{{{{ticker}}}}"}}',
                'mt5_ea': f'API_ServerURL = {credentials["webhook_url"]}',
                'security_note': '🔒 Secret is SET. Include "secret" in every request.'
            }
        else:
            response['instructions'] = {
                'tradingview': f'Webhook URL: {credentials["webhook_url"]}',
                'alert_body': f'{{"action": "{{{{strategy.order.action}}}}", "symbol": "{{{{ticker}}}}"}}',
                'mt5_ea': f'API_ServerURL = {credentials["webhook_url"]}',
                'security_note': '🔓 No secret configured. Requests accepted without secret.'
            }

        return jsonify(response)

    except Exception as e:
        logger.error(f"[USER_CREDENTIALS] Error: {e}")
        return jsonify({'error': str(e)}), 500


@user_bp.route('/api/user/license-key', methods=['GET'])
@require_auth
def get_license_key():
    """
    Get user's license key and webhook URL.

    This is the key piece of information users need to configure
    TradingView webhooks and MT5 EA.

    Returns:
        JSON with license_key, has_secret, and full webhook_url
    """
    try:
        user_id = get_current_user_id()

        if not user_id:
            return jsonify({'error': 'Not authenticated'}), 401

        credentials = user_service.get_user_credentials(user_id)

        if not credentials:
            # Generate if missing
            license_key = user_service.regenerate_license_key(user_id)
            webhook_secret = user_service.regenerate_webhook_secret(user_id)
            if not license_key:
                return jsonify({'error': 'Failed to generate credentials'}), 500
            credentials = {
                'license_key': license_key,
                'webhook_secret': webhook_secret,
                'has_secret': webhook_secret is not None,
                'webhook_url': f"{EXTERNAL_BASE_URL}/{license_key}"
            }

        has_secret = credentials.get('has_secret', False)
        webhook_secret = credentials.get('webhook_secret')

        response = {
            'success': True,
            'license_key': credentials['license_key'],
            'webhook_secret': webhook_secret,
            'has_secret': has_secret,
            'webhook_url': credentials['webhook_url'],
        }

        # Instructions based on whether secret is configured
        if has_secret and webhook_secret:
            response['instructions'] = {
                'tradingview': f'Use this URL in TradingView Alert webhook: {credentials["webhook_url"]}',
                'alert_body': f'{{"secret": "{webhook_secret}", "action": "{{{{strategy.order.action}}}}", "symbol": "{{{{ticker}}}}"}}',
                'mt5_ea': f'Set API_ServerURL in EA to: {credentials["webhook_url"]}',
                'note': '🔒 Secret is SET. Include "secret" in every request.'
            }
        else:
            response['instructions'] = {
                'tradingview': f'Use this URL in TradingView Alert webhook: {credentials["webhook_url"]}',
                'alert_body': f'{{"action": "{{{{strategy.order.action}}}}", "symbol": "{{{{ticker}}}}"}}',
                'mt5_ea': f'Set API_ServerURL in EA to: {credentials["webhook_url"]}',
                'note': '🔓 No secret configured. Requests accepted without secret.'
            }

        return jsonify(response)

    except Exception as e:
        logger.error(f"[LICENSE_KEY] Error: {e}")
        return jsonify({'error': str(e)}), 500


@user_bp.route('/api/user/license-key/regenerate', methods=['POST'])
@require_auth
def regenerate_license_key():
    """
    Generate new license key (invalidates old one).

    ⚠️ WARNING: After regeneration, user must update:
    - TradingView webhook URL
    - MT5 EA configuration

    Returns:
        JSON with new license_key and webhook_url
    """
    try:
        user_id = get_current_user_id()

        if not user_id:
            return jsonify({'error': 'Not authenticated'}), 401

        # Get user email for logging
        user = user_service.get_user_by_id(user_id)
        user_email = user.get('email', 'unknown') if user else 'unknown'

        new_key = user_service.regenerate_license_key(user_id)

        if not new_key:
            return jsonify({'error': 'Failed to regenerate license key'}), 500

        webhook_url = f"{EXTERNAL_BASE_URL}/{new_key}"

        # Log the regeneration
        system_logs_service.add_log(
            'warning',
            f'🔑 License key regenerated for {user_email}',
            user_id=user_id
        )

        logger.info(f"[LICENSE_KEY] Regenerated for user: {user_id}")

        return jsonify({
            'success': True,
            'license_key': new_key,
            'webhook_url': webhook_url,
            'message': 'License key regenerated successfully. Please update your TradingView webhook and MT5 EA configuration.',
            'warning': 'Your old license key is now invalid!'
        })

    except Exception as e:
        logger.error(f"[REGENERATE_KEY] Error: {e}")
        return jsonify({'error': str(e)}), 500


@user_bp.route('/api/user/webhook-secret/regenerate', methods=['POST'])
@require_auth
def regenerate_webhook_secret():
    """
    Generate new webhook secret (invalidates old one).

    ⚠️ WARNING: After regeneration, user must update:
    - TradingView alert message (the "secret" field)
    - MT5 EA configuration if using secret

    Returns:
        JSON with new webhook_secret
    """
    try:
        user_id = get_current_user_id()

        if not user_id:
            return jsonify({'error': 'Not authenticated'}), 401

        # Get user email for logging
        user = user_service.get_user_by_id(user_id)
        user_email = user.get('email', 'unknown') if user else 'unknown'

        new_secret = user_service.regenerate_webhook_secret(user_id)

        if not new_secret:
            return jsonify({'error': 'Failed to regenerate webhook secret'}), 500

        # Log the regeneration
        system_logs_service.add_log(
            'warning',
            f'🔐 Webhook secret regenerated for {user_email}',
            user_id=user_id
        )

        logger.info(f"[WEBHOOK_SECRET] Regenerated for user: {user_id}")

        return jsonify({
            'success': True,
            'webhook_secret': new_secret,
            'has_secret': True,
            'message': 'Webhook secret regenerated successfully. Now you must include "secret" in your webhook requests.',
            'note': '🔒 Secret is now SET. Include "secret" in every request.'
        })

    except Exception as e:
        logger.error(f"[REGENERATE_SECRET] Error: {e}")
        return jsonify({'error': str(e)}), 500


@user_bp.route('/api/user/webhook-secret/clear', methods=['POST'])
@require_auth
def clear_webhook_secret():
    """
    Clear/remove webhook secret (disable secret requirement).

    After clearing, webhook requests will be accepted without secret.

    Returns:
        JSON with updated status
    """
    try:
        user_id = get_current_user_id()

        if not user_id:
            return jsonify({'error': 'Not authenticated'}), 401

        # Get user email for logging
        user = user_service.get_user_by_id(user_id)
        user_email = user.get('email', 'unknown') if user else 'unknown'

        # Clear the secret by setting to empty string
        success = user_service.clear_webhook_secret(user_id)

        if not success:
            return jsonify({'error': 'Failed to clear webhook secret'}), 500

        # Log the change
        system_logs_service.add_log(
            'info',
            f'🔓 Webhook secret cleared for {user_email}',
            user_id=user_id
        )

        logger.info(f"[WEBHOOK_SECRET] Cleared for user: {user_id}")

        return jsonify({
            'success': True,
            'has_secret': False,
            'message': 'Webhook secret cleared. Now requests are accepted without secret.',
            'note': '🔓 No secret required. Requests accepted without secret.'
        })

    except Exception as e:
        logger.error(f"[CLEAR_SECRET] Error: {e}")
        return jsonify({'error': str(e)}), 500


@user_bp.route('/api/user/webhook-secret/status', methods=['GET'])
@require_auth
def get_webhook_secret_status():
    """
    Get current webhook secret status (has secret or not).

    Returns:
        JSON with secret status information
    """
    try:
        user_id = get_current_user_id()

        if not user_id:
            return jsonify({'error': 'Not authenticated'}), 401

        status = user_service.get_webhook_secret_status(user_id)

        return jsonify({
            'success': True,
            'has_secret': status.get('has_secret', False),
            'webhook_secret': status.get('secret'),
            'note': '🔒 Secret is SET. Include it in requests.' if status.get('has_secret') else '🔓 No secret. Requests accepted without secret.'
        })

    except Exception as e:
        logger.error(f"[SECRET_STATUS] Error: {e}")
        return jsonify({'error': str(e)}), 500


@user_bp.route('/api/user/accounts', methods=['GET'])
@require_auth
def get_user_accounts():
    """
    Get list of MT5 accounts belonging to current user.

    Returns:
        JSON with list of account numbers
    """
    try:
        user_id = get_current_user_id()

        if not user_id:
            return jsonify({'error': 'Not authenticated'}), 401

        accounts = user_service.get_user_accounts_list(user_id)

        return jsonify({
            'success': True,
            'accounts': accounts,
            'count': len(accounts)
        })

    except Exception as e:
        logger.error(f"[USER_ACCOUNTS] Error: {e}")
        return jsonify({'error': str(e)}), 500

