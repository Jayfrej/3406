"""
Unified Endpoint Routes - Domain + License Key

This blueprint handles the new unified webhook endpoint:
- URL Format: https://domain.com/<license_key>
- Single URL for both TradingView webhooks and MT5 EA

This blueprint should be registered LAST to avoid conflicts with other routes.
Reference: DOMAIN_LICENSE_KEY_IMPLEMENTATION.md
"""
import os
import json
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

# Create blueprint with NO url_prefix (catches root paths)
unified_bp = Blueprint('unified', __name__)

# These will be injected by the app factory
user_service = None
session_manager = None
webhook_service = None
system_logs_service = None
limiter = None

EXTERNAL_BASE_URL = os.getenv('EXTERNAL_BASE_URL', 'http://localhost:5000')


def init_unified_routes(us, sm, ws, sls, lim):
    """
    Initialize unified routes with dependencies

    Args:
        us: UserService instance
        sm: SessionManager instance
        ws: WebhookService instance
        sls: SystemLogsService instance
        lim: Limiter instance
    """
    global user_service, session_manager, webhook_service, system_logs_service, limiter
    user_service = us
    session_manager = sm
    webhook_service = ws
    system_logs_service = sls
    limiter = lim


def _detect_request_type(data: dict) -> str:
    """
    Detect type of incoming request.

    Returns:
        'heartbeat' | 'command_poll' | 'trading_signal' | 'unknown'
    """
    # EA Heartbeat: has account, broker, symbol but no action
    if 'account' in data and 'broker' in data and 'symbol' in data and 'action' not in data:
        return 'heartbeat'

    # EA Command Poll: has account and command_type='poll'
    if 'account' in data and data.get('command_type') == 'poll':
        return 'command_poll'

    # Trading Signal: has action (BUY, SELL, etc.)
    if 'action' in data:
        return 'trading_signal'

    return 'unknown'


@unified_bp.route('/<license_key>', methods=['POST'])
def unified_webhook_handler(license_key):
    """
    🆕 Unified Webhook Handler - Domain + License Key + Per-User Secret

    URL Format: https://domain.com/<LICENSE_KEY>

    This single endpoint handles:
    - TradingView webhooks (trading signals)
    - MT5 EA heartbeats
    - MT5 EA command polling

    Security Layers:
    1. License Key (URL) - Identifies which user
    2. Per-User Secret (Body/Header) - Validates request authenticity

    Args:
        license_key: User's license key from URL path

    Flow:
    1. Validate license key → get user
    2. Validate per-user secret → authenticate request
    3. Detect request type (heartbeat/signal/poll)
    4. Route to appropriate handler
    5. Process with user isolation
    """
    # Apply rate limit
    try:
        limiter.limit("100 per minute")(lambda: None)()
    except Exception as e:
        logger.warning(f"[UNIFIED] Rate limit check failed: {e}")

    try:
        # 1. Validate license key format
        if not license_key or len(license_key) < 10:
            logger.warning(f"[UNIFIED] Invalid license key format: {license_key[:20] if license_key else 'None'}...")
            return jsonify({'error': 'Invalid license key format'}), 401

        # Skip if this looks like a static file or known route
        if license_key in ['static', 'api', 'webhook', 'login', 'logout', 'auth', 'health', 'favicon.ico']:
            return jsonify({'error': 'Invalid endpoint'}), 404

        # 2. Lookup user by license key
        user = user_service.get_user_by_license_key(license_key)

        if not user:
            logger.warning(f"[UNIFIED] License key not found: {license_key[:15]}...")
            system_logs_service.add_log('error', f'🔐 [401] Invalid license key: {license_key[:10]}...')
            return jsonify({'error': 'Unauthorized - Invalid license key'}), 401

        user_id = user['user_id']
        user_email = user['email']

        # 3. Parse request data first (need to check secret in body)
        try:
            data = request.get_json(force=True) or {}
        except Exception:
            raw_data = request.get_data(as_text=True)
            try:
                data = json.loads(raw_data) if raw_data else {}
            except Exception:
                data = {}

        if not data:
            return jsonify({'error': 'No JSON data received'}), 400

        # 4. 🔐 SECURITY: Validate Per-User Webhook Secret
        # Secret can be in body (preferred) or header
        provided_secret = data.get('secret') or request.headers.get('X-Webhook-Secret')

        if not provided_secret:
            logger.warning(f"[UNIFIED] ❌ No secret provided for {user_email}")
            system_logs_service.add_log('error', f'🔐 [401] Missing secret for {user_email}', user_id=user_id)
            return jsonify({
                'error': 'Unauthorized - Secret required',
                'hint': 'Include "secret" in JSON body or X-Webhook-Secret header'
            }), 401

        if not user_service.validate_webhook_secret(license_key, provided_secret):
            logger.warning(f"[UNIFIED] ❌ Invalid secret for {user_email}")
            system_logs_service.add_log('error', f'🔐 [403] Invalid secret for {user_email}', user_id=user_id)
            return jsonify({'error': 'Forbidden - Invalid secret'}), 403

        logger.info(f"[UNIFIED] ✅ User authenticated with valid secret: {user_email}")

        # Update last login
        user_service.update_last_login(user_id)

        # 5. Detect request type and route to handler
        request_type = _detect_request_type(data)

        if request_type == 'heartbeat':
            return _handle_heartbeat(user_id, user_email, data)

        elif request_type == 'command_poll':
            return _handle_command_poll(user_id, user_email, data)

        elif request_type == 'trading_signal':
            return _handle_trading_signal(user_id, user_email, data)

        else:
            logger.warning(f"[UNIFIED] Unknown request type from {user_email}: {list(data.keys())}")
            return jsonify({'error': 'Unknown request type. Include action for signals or account/broker/symbol for heartbeat.'}), 400

    except Exception as e:
        logger.error(f"[UNIFIED] Error: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


@unified_bp.route('/<license_key>', methods=['GET'])
def unified_info(license_key):
    """
    GET request to license key endpoint - return info
    """
    # Validate license key
    if not license_key or len(license_key) < 10:
        return jsonify({'error': 'Invalid endpoint'}), 404

    # Skip if this looks like a static file or known route
    if license_key in ['static', 'api', 'webhook', 'login', 'logout', 'auth', 'health', 'favicon.ico']:
        return jsonify({'error': 'Invalid endpoint'}), 404

    user = user_service.get_user_by_license_key(license_key)

    if not user:
        return jsonify({'error': 'Invalid license key'}), 401

    return jsonify({
        'status': 'ok',
        'message': 'Unified webhook endpoint active',
        'supported_methods': ['POST'],
        'supported_types': [
            'Trading Signal (include action: BUY/SELL/CLOSE)',
            'EA Heartbeat (include account, broker, symbol)',
            'EA Command Poll (include account, command_type: poll)'
        ],
        'timestamp': datetime.now().isoformat()
    })


def _handle_heartbeat(user_id: str, user_email: str, data: dict):
    """Handle EA heartbeat - EA reports it's online."""
    account = str(data.get('account', '')).strip()
    broker = data.get('broker', '-')
    symbol = data.get('symbol', '-')

    if not account:
        return jsonify({'error': 'Account number required'}), 400

    # Get user's accounts
    user_accounts = user_service.get_user_accounts_list(user_id)

    if account not in user_accounts:
        # Auto-add new account for this user
        try:
            if hasattr(session_manager, 'add_remote_account_with_user'):
                session_manager.add_remote_account_with_user(account, f"Account {account}", user_id)
            else:
                session_manager.add_remote_account(account, f"Account {account}")
            logger.info(f"[HEARTBEAT] ✅ Auto-added account {account} for {user_email}")
        except Exception as e:
            logger.warning(f"[HEARTBEAT] Could not auto-add account: {e}")

    # Update heartbeat
    try:
        session_manager.update_account_heartbeat(account)
    except Exception as e:
        logger.warning(f"[HEARTBEAT] Update failed: {e}")

    logger.info(f"[HEARTBEAT] ✅ {user_email} → Account {account} ({broker}) is online")

    return jsonify({
        'success': True,
        'message': 'Heartbeat received',
        'account': account,
        'status': 'Online',
        'timestamp': datetime.now().isoformat()
    })


def _handle_command_poll(user_id: str, user_email: str, data: dict):
    """Handle EA command polling - EA asks for pending commands."""
    account = str(data.get('account', '')).strip()

    if not account:
        return jsonify({'error': 'Account number required'}), 400

    # Verify account belongs to user
    user_accounts = user_service.get_user_accounts_list(user_id)

    if account not in user_accounts:
        logger.warning(f"[COMMAND_POLL] Unauthorized account {account} for {user_email}")
        return jsonify({'error': 'Unauthorized account'}), 403

    # Get pending command
    command = None
    try:
        if hasattr(session_manager, 'get_pending_command'):
            command = session_manager.get_pending_command(account)
    except Exception as e:
        logger.warning(f"[COMMAND_POLL] Error getting command: {e}")

    if command:
        logger.info(f"[COMMAND_POLL] Sending command to {account}: {command.get('action')}")
        return jsonify({
            'success': True,
            'has_command': True,
            'command': command
        })
    else:
        return jsonify({
            'success': True,
            'has_command': False
        })


def _handle_trading_signal(user_id: str, user_email: str, data: dict):
    """Handle trading signal from TradingView or other sources."""
    action = str(data.get('action', '')).upper()
    symbol = data.get('symbol', '-')
    volume = data.get('volume', '-')

    logger.info(f"[SIGNAL] {user_email} → {action} {symbol} Vol:{volume}")
    system_logs_service.add_log(
        'info',
        f'📡 Signal: {action} {symbol} from {user_email}',
        user_id=user_id
    )

    # Get user's accounts
    user_accounts = user_service.get_user_accounts_list(user_id)

    if not user_accounts:
        logger.warning(f"[SIGNAL] No accounts for {user_email}")
        return jsonify({
            'error': 'No accounts found. Please add accounts via the dashboard first.',
            'suggestion': 'Run MT5 EA with your license key to auto-register accounts'
        }), 400

    # Determine target accounts
    if 'account_number' in data:
        target_account = str(data['account_number']).strip()
        if target_account not in user_accounts:
            return jsonify({'error': f'Unauthorized account: {target_account}'}), 403
        target_accounts = [target_account]
    elif 'accounts' in data:
        requested = [str(a).strip() for a in data['accounts']]
        target_accounts = [a for a in requested if a in user_accounts]
        if not target_accounts:
            return jsonify({'error': 'No authorized accounts in request'}), 403
    else:
        # No specific account - send to all user's accounts
        target_accounts = user_accounts

    # Validate payload
    try:
        valid = webhook_service.validate_webhook_payload(data)
        if not valid.get("valid"):
            return jsonify({'error': valid.get('error')}), 400
    except Exception as e:
        logger.warning(f"[SIGNAL] Validation error: {e}")

    # Process signal
    data_processed = dict(data)
    data_processed['accounts'] = target_accounts

    try:
        result = webhook_service.process_webhook(data_processed)
    except Exception as e:
        logger.error(f"[SIGNAL] Process error: {e}")
        return jsonify({'error': f'Processing failed: {str(e)}'}), 500

    if result.get('success'):
        system_logs_service.add_log(
            'success',
            f'✅ Signal: {action} {symbol} → {len(target_accounts)} account(s)',
            user_id=user_id,
            accounts=target_accounts
        )
        return jsonify({
            'success': True,
            'message': f'Signal sent to {len(target_accounts)} account(s)',
            'action': action,
            'symbol': symbol,
            'accounts': target_accounts
        })
    else:
        error_msg = result.get('error', 'Unknown error')
        system_logs_service.add_log('error', f'❌ Signal failed: {error_msg[:80]}', user_id=user_id)
        return jsonify({'error': error_msg}), 500

