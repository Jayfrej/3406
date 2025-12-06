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

    # ⚠️ CHANGED: Do NOT auto-add accounts - user must add via Dashboard first
    if account not in user_accounts:
        logger.warning(f"[HEARTBEAT] ❌ Account {account} not found for {user_email}. User must add account via Dashboard first!")
        return jsonify({
            'error': 'Account not found. Please add this account via Dashboard first.',
            'hint': f'Go to Dashboard → Add Account → Enter account number: {account}',
            'account': account
        }), 404

    # Update heartbeat (account is activated/online)
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


# ========================================
# EA API ENDPOINTS (/{license_key}/api/ea/*)
# ========================================

def _validate_license_and_get_user(license_key: str) -> tuple:
    """
    Helper to validate license key and get user info.
    Returns (user_dict, None) on success or (None, error_response) on failure.
    """
    if not license_key or len(license_key) < 10:
        return None, (jsonify({'success': False, 'error': 'Invalid license key format'}), 401)

    if license_key in ['static', 'api', 'webhook', 'login', 'logout', 'auth', 'health', 'favicon.ico']:
        return None, (jsonify({'success': False, 'error': 'Invalid endpoint'}), 404)

    user = user_service.get_user_by_license_key(license_key)
    if not user:
        return None, (jsonify({'success': False, 'error': 'Invalid license key'}), 401)

    return user, None


@unified_bp.route('/<license_key>/api/ea/heartbeat', methods=['POST'])
def ea_heartbeat(license_key: str):
    """
    EA Heartbeat - รายงานสถานะ EA

    URL: https://yourdomain.com/{license_key}/api/ea/heartbeat

    Body:
    {
        "account": "12345678",
        "broker": "XM",
        "balance": 10000.50,
        "equity": 10050.25,
        "ea_version": "1.0.0"
    }
    """
    user, error = _validate_license_and_get_user(license_key)
    if error:
        return error

    user_id = user['user_id']
    user_email = user['email']

    data = request.get_json() or {}
    account = str(data.get('account', '')).strip()

    if not account:
        return jsonify({'success': False, 'error': 'Account number required'}), 400

    logger.info(f"[EA_HEARTBEAT] User {user_email}, Account {account}")

    # Update heartbeat
    try:
        session_manager.update_account_heartbeat(account)
    except Exception as e:
        logger.warning(f"[EA_HEARTBEAT] Update failed: {e}")

    return jsonify({
        'success': True,
        'type': 'heartbeat',
        'user_id': user_id,
        'account': account,
        'server_time': datetime.now().isoformat()
    })


@unified_bp.route('/<license_key>/api/ea/get_signals', methods=['GET', 'POST'])
def ea_get_signals(license_key: str):
    """
    EA ดึง pending signals

    URL: https://yourdomain.com/{license_key}/api/ea/get_signals

    Query/Body:
    {
        "account": "12345678"
    }
    """
    user, error = _validate_license_and_get_user(license_key)
    if error:
        return error

    user_id = user['user_id']
    user_email = user['email']

    # Get account from query or body
    account = request.args.get('account')
    if request.is_json:
        data = request.get_json() or {}
        account = account or data.get('account')

    if not account:
        return jsonify({'success': False, 'error': 'Account number required'}), 400

    account = str(account).strip()

    # Verify account belongs to user
    user_accounts = user_service.get_user_accounts_list(user_id)
    if account not in user_accounts:
        logger.warning(f"[EA_SIGNALS] Unauthorized account {account} for {user_email}")
        return jsonify({'success': False, 'error': 'Unauthorized account'}), 403

    logger.debug(f"[EA_SIGNALS] User {user_email}, Account {account}")

    # Get pending command/signal for this account
    command = None
    try:
        if hasattr(session_manager, 'get_pending_command'):
            command = session_manager.get_pending_command(account)
    except Exception as e:
        logger.warning(f"[EA_SIGNALS] Error getting signals: {e}")

    if command:
        logger.info(f"[EA_SIGNALS] Sending signal to {account}: {command.get('action', 'unknown')}")
        return jsonify({
            'success': True,
            'type': 'get_signals',
            'user_id': user_id,
            'account': account,
            'has_signal': True,
            'signals': [command]
        })
    else:
        return jsonify({
            'success': True,
            'type': 'get_signals',
            'user_id': user_id,
            'account': account,
            'has_signal': False,
            'signals': []
        })


@unified_bp.route('/<license_key>/api/ea/confirm_execution', methods=['POST'])
def ea_confirm_execution(license_key: str):
    """
    EA ยืนยันการ execute trade

    URL: https://yourdomain.com/{license_key}/api/ea/confirm_execution

    Body:
    {
        "account": "12345678",
        "signal_id": "abc123",
        "ticket": 123456789,
        "status": "success",
        "message": "Order executed"
    }
    """
    user, error = _validate_license_and_get_user(license_key)
    if error:
        return error

    user_id = user['user_id']
    user_email = user['email']

    data = request.get_json() or {}
    account = str(data.get('account', '')).strip()
    signal_id = data.get('signal_id', '')
    ticket = data.get('ticket')
    status = data.get('status', 'unknown')
    message = data.get('message', '')

    if not account:
        return jsonify({'success': False, 'error': 'Account number required'}), 400

    # Verify account belongs to user
    user_accounts = user_service.get_user_accounts_list(user_id)
    if account not in user_accounts:
        logger.warning(f"[EA_CONFIRM] Unauthorized account {account} for {user_email}")
        return jsonify({'success': False, 'error': 'Unauthorized account'}), 403

    logger.info(f"[EA_CONFIRM] User {user_email}, Account {account}, Status: {status}, Ticket: {ticket}")

    # Log the execution result
    if status == 'success':
        system_logs_service.add_log(
            'success',
            f'✅ Trade executed: Account {account}, Ticket {ticket}',
            user_id=user_id
        )
    else:
        system_logs_service.add_log(
            'error',
            f'❌ Trade failed: Account {account}, {message}',
            user_id=user_id
        )

    return jsonify({
        'success': True,
        'type': 'confirm_execution',
        'user_id': user_id,
        'account': account,
        'confirmed': True
    })


@unified_bp.route('/<license_key>/api/ea/register', methods=['POST'])
def ea_register(license_key: str):
    """
    EA ลงทะเบียน/Activate account (ต้องเพิ่ม account ผ่าน Dashboard ก่อน!)

    URL: https://yourdomain.com/{license_key}/api/ea/register

    ⚠️ IMPORTANT: User must add account via Dashboard first!
    This endpoint only ACTIVATES existing accounts, it does NOT auto-add new accounts.

    Body:
    {
        "account": "12345678",
        "broker": "XM Global",
        "server": "XM-MT5-Real",
        "balance": 10000.00
    }
    """
    user, error = _validate_license_and_get_user(license_key)
    if error:
        return error

    user_id = user['user_id']
    user_email = user['email']

    data = request.get_json() or {}
    account = str(data.get('account', '')).strip()
    broker = data.get('broker', 'Unknown')
    server = data.get('server', '')

    if not account:
        return jsonify({'success': False, 'error': 'Account number required'}), 400

    logger.info(f"[EA_REGISTER] User {user_email}, Account {account}, Broker {broker}")

    # Check if account exists for this user
    user_accounts = user_service.get_user_accounts_list(user_id)

    if account in user_accounts:
        # Account exists - activate it (update heartbeat)
        try:
            session_manager.update_account_heartbeat(account)
        except Exception as e:
            logger.warning(f"[EA_REGISTER] Could not update heartbeat: {e}")

        logger.info(f"[EA_REGISTER] ✅ Account {account} activated for {user_email}")
        return jsonify({
            'success': True,
            'type': 'register',
            'user_id': user_id,
            'account': account,
            'status': 'activated',
            'message': 'Account activated successfully'
        })

    # ⚠️ Account NOT found - user must add it via Dashboard first
    logger.warning(f"[EA_REGISTER] ❌ Account {account} not found for {user_email}. User must add account via Dashboard first!")
    return jsonify({
        'success': False,
        'error': 'Account not found. Please add this account via Dashboard first.',
        'hint': f'Go to Dashboard → Add Account → Enter account number: {account}',
        'account': account
    }), 404


@unified_bp.route('/<license_key>/api/ea/get_copy_pairs', methods=['GET'])
def ea_get_copy_pairs(license_key: str):
    """
    EA ดึง copy trading pairs สำหรับ account

    URL: https://yourdomain.com/{license_key}/api/ea/get_copy_pairs

    Query:
    ?account=12345678
    """
    user, error = _validate_license_and_get_user(license_key)
    if error:
        return error

    user_id = user['user_id']
    user_email = user['email']

    account = request.args.get('account', '').strip()

    if not account:
        return jsonify({'success': False, 'error': 'Account number required'}), 400

    # Verify account belongs to user
    user_accounts = user_service.get_user_accounts_list(user_id)
    if account not in user_accounts:
        logger.warning(f"[EA_PAIRS] Unauthorized account {account} for {user_email}")
        return jsonify({'success': False, 'error': 'Unauthorized account'}), 403

    logger.debug(f"[EA_PAIRS] User {user_email}, Account {account}")

    # Get copy pairs for this user
    try:
        from app.copy_trading import CopyManager
        copy_manager = CopyManager()

        # Get pairs where this account is master or slave
        all_pairs = copy_manager.get_pairs()

        # Filter by user_id
        user_pairs = [p for p in all_pairs if p.get('user_id') == user_id]

        # Further filter where account is involved
        account_pairs = []
        for pair in user_pairs:
            if pair.get('master_account') == account or pair.get('slave_account') == account:
                account_pairs.append({
                    'pair_id': pair.get('id'),
                    'master_account': pair.get('master_account'),
                    'slave_account': pair.get('slave_account'),
                    'enabled': pair.get('enabled', True),
                    'copy_mode': pair.get('copy_mode', 'fixed'),
                    'fixed_lot': pair.get('fixed_lot', 0.01)
                })

        return jsonify({
            'success': True,
            'type': 'get_copy_pairs',
            'user_id': user_id,
            'account': account,
            'pairs': account_pairs
        })

    except Exception as e:
        logger.error(f"[EA_PAIRS] Error getting copy pairs: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to get copy pairs: {str(e)}'
        }), 500


@unified_bp.route('/<license_key>/api/ea/status', methods=['GET'])
def ea_status(license_key: str):
    """
    ตรวจสอบสถานะ endpoint และ license

    URL: https://yourdomain.com/{license_key}/api/ea/status
    """
    user, error = _validate_license_and_get_user(license_key)
    if error:
        return error

    user_id = user['user_id']
    user_email = user['email']

    # Get user's accounts
    user_accounts = user_service.get_user_accounts_list(user_id)

    return jsonify({
        'success': True,
        'type': 'status',
        'user_id': user_id,
        'email': user_email,
        'license_valid': True,
        'accounts_count': len(user_accounts),
        'accounts': user_accounts,
        'server_time': datetime.now().isoformat(),
        'endpoints': {
            'heartbeat': f'/{license_key}/api/ea/heartbeat',
            'get_signals': f'/{license_key}/api/ea/get_signals',
            'confirm_execution': f'/{license_key}/api/ea/confirm_execution',
            'register': f'/{license_key}/api/ea/register',
            'get_copy_pairs': f'/{license_key}/api/ea/get_copy_pairs',
            'status': f'/{license_key}/api/ea/status'
        }
    })


# ========================================
# BROKER API ENDPOINTS (/{license_key}/api/broker/*)
# ========================================

@unified_bp.route('/<license_key>/api/broker/register', methods=['POST'])
def broker_register(license_key: str):
    """
    EA registers broker/account information (ACTIVATE existing account)

    URL: https://yourdomain.com/{license_key}/api/broker/register

    ⚠️ IMPORTANT: User must add account via Dashboard first!
    This endpoint only ACTIVATES existing accounts, it does NOT auto-add new accounts.

    Body:
    {
        "account": "12345678",
        "broker": "XM Global",
        "server": "XM-MT5-Real",
        "balance": 10000.00,
        "equity": 10050.25,
        "currency": "USD",
        "symbols": ["EURUSD", "GBPUSD", "XAUUSD"]
    }
    """
    user, error = _validate_license_and_get_user(license_key)
    if error:
        return error

    user_id = user['user_id']
    user_email = user['email']

    data = request.get_json() or {}
    account = str(data.get('account', '')).strip()
    broker = data.get('broker', 'Unknown')
    server = data.get('server', '')
    balance = data.get('balance', 0)
    equity = data.get('equity', 0)
    currency = data.get('currency', 'USD')
    symbols = data.get('symbols', [])

    if not account:
        return jsonify({'success': False, 'error': 'Account number required'}), 400

    logger.info(f"[BROKER_REGISTER] User {user_email}, Account {account}, Broker {broker}")

    # Check if account exists for this user
    user_accounts = user_service.get_user_accounts_list(user_id)

    # ⚠️ CHANGED LOGIC: Do NOT auto-add accounts
    # User must add account via Dashboard first, then EA activates it
    if account not in user_accounts:
        logger.warning(f"[BROKER_REGISTER] ❌ Account {account} not found for {user_email}. User must add account via Dashboard first!")
        return jsonify({
            'success': False,
            'error': 'Account not found. Please add this account via Dashboard first.',
            'hint': f'Go to Dashboard → Add Account → Enter account number: {account}',
            'account': account
        }), 404

    # Account exists - update broker data and activate it
    try:
        # Update broker data using save_broker_info
        try:
            from app.broker_data_manager import BrokerDataManager
            broker_manager = BrokerDataManager()
            broker_manager.save_broker_info(account, {
                'broker': broker,
                'server': server,
                'symbols': symbols,
                'user_id': user_id,
                'last_update': datetime.now().isoformat()
            })
        except Exception as e:
            logger.warning(f"[BROKER_REGISTER] Could not update broker data: {e}")

        # Update heartbeat to mark account as ACTIVE/Online
        try:
            session_manager.update_account_heartbeat(account)
            logger.info(f"[BROKER_REGISTER] ✅ Account {account} ACTIVATED for {user_email}")
        except Exception as e:
            logger.warning(f"[BROKER_REGISTER] Could not update heartbeat: {e}")

        # Log success
        system_logs_service.add_log(
            'success',
            f'✅ Account {account} activated by EA ({broker})',
            user_id=user_id
        )

        return jsonify({
            'success': True,
            'type': 'broker_register',
            'user_id': user_id,
            'account': account,
            'broker': broker,
            'status': 'activated',
            'message': 'Account activated successfully'
        })

    except Exception as e:
        logger.error(f"[BROKER_REGISTER] Failed: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to activate account: {str(e)}'
        }), 500


# ========================================
# COMMANDS API ENDPOINTS (/{license_key}/api/commands/*)
# ========================================

@unified_bp.route('/<license_key>/api/commands/<account>', methods=['GET'])
def get_commands(license_key: str, account: str):
    """
    EA gets pending commands for an account

    URL: https://yourdomain.com/{license_key}/api/commands/{account}

    Query params:
    ?limit=10  (optional, default 10)
    """
    user, error = _validate_license_and_get_user(license_key)
    if error:
        return error

    user_id = user['user_id']
    user_email = user['email']
    account = str(account).strip()

    if not account:
        return jsonify({'success': False, 'error': 'Account number required'}), 400

    # Verify account belongs to user
    user_accounts = user_service.get_user_accounts_list(user_id)
    if account not in user_accounts:
        logger.warning(f"[GET_COMMANDS] Unauthorized account {account} for {user_email}")
        return jsonify({'success': False, 'error': 'Unauthorized account'}), 403

    limit = request.args.get('limit', 10, type=int)

    # Get pending commands
    commands = []
    try:
        if hasattr(session_manager, 'get_pending_command'):
            command = session_manager.get_pending_command(account)
            if command:
                commands.append(command)

        # Also check command queue if exists
        try:
            from app.command_queue import CommandQueue
            cmd_queue = CommandQueue()
            queued_commands = cmd_queue.get_commands(account, limit=limit)
            if queued_commands:
                commands.extend(queued_commands)
        except Exception as e:
            logger.debug(f"[GET_COMMANDS] Command queue not available: {e}")

    except Exception as e:
        logger.warning(f"[GET_COMMANDS] Error getting commands: {e}")

    # Update heartbeat since EA is polling
    try:
        session_manager.update_account_heartbeat(account)
    except Exception:
        pass

    return jsonify({
        'success': True,
        'type': 'get_commands',
        'user_id': user_id,
        'account': account,
        'count': len(commands),
        'commands': commands
    })


@unified_bp.route('/<license_key>/api/commands/<account>/ack', methods=['POST'])
def ack_command(license_key: str, account: str):
    """
    EA acknowledges command execution

    URL: https://yourdomain.com/{license_key}/api/commands/{account}/ack

    Body:
    {
        "command_id": "abc123",
        "status": "success",
        "ticket": 123456789,
        "message": "Order executed successfully"
    }
    """
    user, error = _validate_license_and_get_user(license_key)
    if error:
        return error

    user_id = user['user_id']
    user_email = user['email']
    account = str(account).strip()

    if not account:
        return jsonify({'success': False, 'error': 'Account number required'}), 400

    # Verify account belongs to user
    user_accounts = user_service.get_user_accounts_list(user_id)
    if account not in user_accounts:
        logger.warning(f"[ACK_COMMAND] Unauthorized account {account} for {user_email}")
        return jsonify({'success': False, 'error': 'Unauthorized account'}), 403

    data = request.get_json() or {}
    command_id = data.get('command_id', '')
    status = data.get('status', 'unknown')
    ticket = data.get('ticket')
    message = data.get('message', '')

    logger.info(f"[ACK_COMMAND] User {user_email}, Account {account}, Command {command_id}, Status {status}")

    # Mark command as executed
    try:
        if hasattr(session_manager, 'mark_command_executed'):
            session_manager.mark_command_executed(account, command_id, status, ticket)

        # Also try command queue
        try:
            from app.command_queue import CommandQueue
            cmd_queue = CommandQueue()
            cmd_queue.acknowledge_command(command_id, status, ticket, message)
        except Exception:
            pass

    except Exception as e:
        logger.warning(f"[ACK_COMMAND] Error acknowledging command: {e}")

    # Log result
    if status == 'success':
        system_logs_service.add_log(
            'success',
            f'✅ Command executed: Account {account}, Ticket {ticket}',
            user_id=user_id
        )
    else:
        system_logs_service.add_log(
            'error',
            f'❌ Command failed: Account {account}, {message}',
            user_id=user_id
        )

    return jsonify({
        'success': True,
        'type': 'ack_command',
        'user_id': user_id,
        'account': account,
        'command_id': command_id,
        'acknowledged': True
    })


# ========================================
# BALANCE API ENDPOINTS (/{license_key}/api/balance/*, /{license_key}/api/account/*)
# ========================================

@unified_bp.route('/<license_key>/api/balance/need-update/<account>', methods=['GET'])
def check_balance_need_update(license_key: str, account: str):
    """
    EA checks if balance update is needed

    URL: https://yourdomain.com/{license_key}/api/balance/need-update/{account}
    """
    user, error = _validate_license_and_get_user(license_key)
    if error:
        return error

    user_id = user['user_id']
    user_email = user['email']
    account = str(account).strip()

    if not account:
        return jsonify({'success': False, 'error': 'Account number required'}), 400

    # Verify account belongs to user
    user_accounts = user_service.get_user_accounts_list(user_id)
    if account not in user_accounts:
        logger.warning(f"[BALANCE_CHECK] Unauthorized account {account} for {user_email}")
        return jsonify({'success': False, 'error': 'Unauthorized account'}), 403

    # Check if balance update is needed
    need_update = True  # Default to true to ensure EA sends balance
    last_update = None

    try:
        from app.account_balance import AccountBalanceManager
        balance_manager = AccountBalanceManager()

        if hasattr(balance_manager, 'need_balance_update'):
            need_update = balance_manager.need_balance_update(account)

        if hasattr(balance_manager, 'get_last_update_time'):
            last_update = balance_manager.get_last_update_time(account)
    except Exception as e:
        logger.debug(f"[BALANCE_CHECK] Balance manager not available: {e}")

    return jsonify({
        'success': True,
        'type': 'balance_check',
        'user_id': user_id,
        'account': account,
        'need_update': need_update,
        'last_update': last_update
    })


@unified_bp.route('/<license_key>/api/account/balance', methods=['POST'])
def update_account_balance(license_key: str):
    """
    EA updates account balance

    URL: https://yourdomain.com/{license_key}/api/account/balance

    Body:
    {
        "account": "12345678",
        "balance": 10000.50,
        "equity": 10050.25,
        "margin": 500.00,
        "free_margin": 9550.25,
        "margin_level": 2010.05,
        "profit": 50.25,
        "currency": "USD"
    }
    """
    user, error = _validate_license_and_get_user(license_key)
    if error:
        return error

    user_id = user['user_id']
    user_email = user['email']

    data = request.get_json() or {}
    account = str(data.get('account', '')).strip()

    if not account:
        return jsonify({'success': False, 'error': 'Account number required'}), 400

    # Verify account belongs to user
    user_accounts = user_service.get_user_accounts_list(user_id)
    if account not in user_accounts:
        logger.warning(f"[BALANCE_UPDATE] Unauthorized account {account} for {user_email}")
        return jsonify({'success': False, 'error': 'Unauthorized account'}), 403

    # Extract balance data
    balance_data = {
        'account': account,
        'balance': data.get('balance', 0),
        'equity': data.get('equity', 0),
        'margin': data.get('margin', 0),
        'free_margin': data.get('free_margin', 0),
        'margin_level': data.get('margin_level', 0),
        'profit': data.get('profit', 0),
        'currency': data.get('currency', 'USD'),
        'user_id': user_id,
        'timestamp': datetime.now().isoformat()
    }

    logger.info(f"[BALANCE_UPDATE] User {user_email}, Account {account}, Balance: {balance_data.get('balance')}")

    # Update balance
    try:
        from app.account_balance import AccountBalanceManager
        balance_manager = AccountBalanceManager()

        # Extract numeric values (handle case where EA sends nested object)
        raw_balance = data.get('balance', 0)
        raw_equity = data.get('equity')
        raw_margin = data.get('margin')
        raw_free_margin = data.get('free_margin')

        # If balance is a dict, try to extract the actual value
        if isinstance(raw_balance, dict):
            raw_balance = raw_balance.get('value', raw_balance.get('balance', 0))
        if isinstance(raw_equity, dict):
            raw_equity = raw_equity.get('value', raw_equity.get('equity', 0))
        if isinstance(raw_margin, dict):
            raw_margin = raw_margin.get('value', raw_margin.get('margin', 0))
        if isinstance(raw_free_margin, dict):
            raw_free_margin = raw_free_margin.get('value', raw_free_margin.get('free_margin', 0))

        # Call update_balance with individual parameters (not dict)
        balance_manager.update_balance(
            account=account,
            balance=float(raw_balance) if raw_balance is not None else 0,
            equity=float(raw_equity) if raw_equity is not None else None,
            margin=float(raw_margin) if raw_margin is not None else None,
            free_margin=float(raw_free_margin) if raw_free_margin is not None else None,
            currency=data.get('currency', 'USD')
        )
        logger.info(f"[BALANCE_UPDATE] ✅ Balance updated for {account}: {raw_balance}")
    except Exception as e:
        logger.warning(f"[BALANCE_UPDATE] Could not update balance: {e}")

    # Also update heartbeat
    try:
        session_manager.update_account_heartbeat(account)
    except Exception:
        pass

    return jsonify({
        'success': True,
        'type': 'balance_update',
        'user_id': user_id,
        'account': account,
        'message': 'Balance updated successfully'
    })


@unified_bp.route('/<license_key>/api/account/<account>/balance', methods=['GET'])
def get_account_balance(license_key: str, account: str):
    """
    Get account balance

    URL: https://yourdomain.com/{license_key}/api/account/{account}/balance
    """
    user, error = _validate_license_and_get_user(license_key)
    if error:
        return error

    user_id = user['user_id']
    user_email = user['email']
    account = str(account).strip()

    if not account:
        return jsonify({'success': False, 'error': 'Account number required'}), 400

    # Verify account belongs to user
    user_accounts = user_service.get_user_accounts_list(user_id)
    if account not in user_accounts:
        logger.warning(f"[GET_BALANCE] Unauthorized account {account} for {user_email}")
        return jsonify({'success': False, 'error': 'Unauthorized account'}), 403

    # Get balance
    balance_data = None
    try:
        from app.account_balance import AccountBalanceManager
        balance_manager = AccountBalanceManager()

        if hasattr(balance_manager, 'get_balance'):
            balance_data = balance_manager.get_balance(account)
    except Exception as e:
        logger.debug(f"[GET_BALANCE] Balance manager not available: {e}")

    if balance_data:
        return jsonify({
            'success': True,
            'type': 'get_balance',
            'user_id': user_id,
            'account': account,
            'balance': balance_data
        })
    else:
        return jsonify({
            'success': True,
            'type': 'get_balance',
            'user_id': user_id,
            'account': account,
            'balance': None,
            'message': 'No balance data available'
        })

