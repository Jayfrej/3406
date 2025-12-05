"""
Webhook Routes
Handles webhook endpoints for receiving trading signals

Updated for Multi-User SaaS:
- Per-user webhook tokens from user_tokens table
- Legacy WEBHOOK_TOKEN supported for backward compatibility
- /webhook-url now requires auth and returns user-specific URL

Reference: MIGRATION_ROADMAP.md Phase 3.1
"""
import os
import json
import re
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, session
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
load_dotenv()

# Create blueprint
webhook_bp = Blueprint('webhook', __name__)

# These will be injected by the app factory
webhook_service = None
session_manager = None
signal_translator = None
email_handler = None
system_logs_service = None
limiter = None
account_allowlist_service = None

EXTERNAL_BASE_URL = os.getenv('EXTERNAL_BASE_URL', 'http://localhost:5000')

# Legacy token - only used for backward compatibility during migration
# In Multi-User SaaS, each user gets their own token stored in user_tokens table
LEGACY_WEBHOOK_TOKEN = os.getenv('WEBHOOK_TOKEN', '')


def init_webhook_routes(ws, sm, st, eh, sls, lim, aas):
    """
    Initialize webhook routes with dependencies

    Args:
        ws: WebhookService instance
        sm: SessionManager instance
        st: SignalTranslator instance
        eh: EmailHandler instance
        sls: SystemLogsService instance
        lim: Limiter instance
        aas: AccountAllowlistService instance
    """
    global webhook_service, session_manager, signal_translator, email_handler
    global system_logs_service, limiter, account_allowlist_service

    webhook_service = ws
    session_manager = sm
    signal_translator = st
    email_handler = eh
    system_logs_service = sls
    limiter = lim
    account_allowlist_service = aas


@webhook_bp.route('/webhook-url', methods=['GET'])
def get_webhook_url():
    """
    Get webhook URL for the current user (Multi-User SaaS).

    In Multi-User mode:
    - Requires authentication
    - Returns user-specific webhook URL from user_tokens table

    In Legacy mode (no user logged in):
    - Returns legacy WEBHOOK_TOKEN URL if configured

    Reference: MIGRATION_ROADMAP.md Phase 3.1
    """
    from app.middleware.auth import get_current_user_id

    user_id = get_current_user_id()

    if user_id:
        # Multi-User SaaS: Return user-specific webhook URL
        try:
            from app.services.token_service import TokenService
            token_service = TokenService()
            webhook_url = token_service.get_webhook_url(user_id)

            if webhook_url:
                return jsonify({'url': webhook_url, 'user_id': user_id})
            else:
                # Generate new token for user
                token = token_service.generate_webhook_token(user_id)
                webhook_url = f"{EXTERNAL_BASE_URL}/webhook/{token}"
                return jsonify({'url': webhook_url, 'user_id': user_id})
        except Exception as e:
            logger.error(f"[WEBHOOK_URL] Error getting user webhook: {e}")
            return jsonify({'error': 'Failed to get webhook URL'}), 500

    # Legacy fallback: Return global WEBHOOK_TOKEN URL if configured
    if LEGACY_WEBHOOK_TOKEN:
        return jsonify({
            'url': f"{EXTERNAL_BASE_URL}/webhook/{LEGACY_WEBHOOK_TOKEN}",
            'mode': 'legacy',
            'note': 'Login with Google to get your personal webhook URL'
        })

    return jsonify({
        'error': 'Not authenticated',
        'note': 'Login with Google to get your personal webhook URL'
    }), 401



@webhook_bp.route('/webhook', methods=['GET'])
@webhook_bp.route('/webhook/', methods=['GET'])
def webhook_info():
    """Get webhook endpoint information"""
    return jsonify({
        'message': 'Webhook endpoint active',
        'supported_methods': ['POST'],
        'health_check': '/webhook/health',
        'endpoint_format': '/webhook/{token}',
        'supported_actions': ['BUY', 'SELL', 'LONG', 'SHORT', 'CALL', 'PUT', 'CLOSE', 'CLOSE_ALL', 'CLOSE_SYMBOL'],
        'timestamp': datetime.now().isoformat()
    })


@webhook_bp.route('/webhook/health', methods=['GET'])
def webhook_health():
    """Webhook health check endpoint"""
    return jsonify({
        'status': 'ok',
        'webhook_status': 'active',
        'timestamp': datetime.now().isoformat()
    })


@webhook_bp.route('/webhook/<token>', methods=['POST'])
def webhook_handler(token):
    """
    Main webhook handler - receives trading signals from external sources.

    Multi-User SaaS Token Validation:
    1. First, check if token matches a user in user_tokens table
    2. If found, only process for that user's accounts
    3. If not found, check legacy WEBHOOK_TOKEN for backward compatibility
    4. If neither match, return 401 Unauthorized

    Args:
        token: Webhook authentication token (from URL)

    Reference: MIGRATION_ROADMAP.md Phase 3.1
    """
    # Apply rate limit
    limiter.limit("10 per minute")(lambda: None)()

    # 1. Token validation - Multi-User SaaS first, then legacy fallback
    user_id = None

    # Try to find user by webhook token (Multi-User SaaS)
    try:
        from app.services.token_service import TokenService
        token_service = TokenService()
        user_id = token_service.get_user_by_webhook_token(token)

        if user_id:
            logger.info(f"[WEBHOOK] Token validated for user: {user_id}")
    except Exception as e:
        logger.debug(f"[WEBHOOK] Token service lookup failed: {e}")

    # Legacy fallback: Check against WEBHOOK_TOKEN env var
    if not user_id:
        if LEGACY_WEBHOOK_TOKEN and token == LEGACY_WEBHOOK_TOKEN:
            # Find first admin user dynamically instead of hardcoding admin_001
            try:
                from app.services.user_service import UserService
                user_service = UserService()
                admin_user = user_service.get_first_admin()
                user_id = admin_user.get('user_id') if admin_user else 'admin_001'
            except Exception:
                user_id = 'admin_001'  # Ultimate fallback
            logger.info(f"[WEBHOOK] Legacy token validated, using admin user: {user_id}")
        else:
            logger.warning("[UNAUTHORIZED] invalid webhook token")
            system_logs_service.add_log('error', '🔒 [401] Webhook unauthorized - Invalid token')
            email_handler.send_alert("Unauthorized Webhook Access", "Invalid token")
            return jsonify({'error': 'Unauthorized'}), 401

    # 2. JSON parsing with error recovery
    try:
        data = request.get_json()
        if not data:
            raise ValueError("No JSON data received")
    except Exception as e:
        logger.error(f"[BAD_PAYLOAD] {e}")
        system_logs_service.add_log('error', f'❌ [400] Webhook bad request - Invalid JSON: {str(e)[:80]}')
        email_handler.send_alert("Bad Webhook Payload", f"Invalid JSON: {e}")

        # Try to extract data from raw request for error logging
        raw_data = request.get_data(as_text=True)
        account = '-'
        action = 'UNKNOWN'
        symbol = '-'
        volume = ''
        price = ''
        tp = ''
        sl = ''

        # Best-effort parse with regex
        try:
            # Extract account number
            acc_match = re.search(r'"account(?:_number)?"\s*:\s*"?(\d+)"?', raw_data)
            if acc_match:
                account = acc_match.group(1)

            # Extract action
            action_match = re.search(r'"action"\s*:\s*"([^"]+)"', raw_data)
            if action_match:
                action = action_match.group(1).upper()

            # Extract symbol
            symbol_match = re.search(r'"symbol"\s*:\s*"([^"]+)"', raw_data)
            if symbol_match:
                symbol = symbol_match.group(1)

            # Extract volume
            vol_match = re.search(r'"volume"\s*:\s*"?([0-9.]+)"?', raw_data)
            if vol_match:
                volume = vol_match.group(1)

            # Extract price
            price_match = re.search(r'"price"\s*:\s*"?([0-9.]+)"?', raw_data)
            if price_match:
                price = price_match.group(1)

            # Extract take_profit / tp
            tp_match = re.search(r'"(?:take_profit|tp)"\s*:\s*"?([0-9.]+)"?', raw_data)
            if tp_match:
                tp = tp_match.group(1)

            # Extract stop_loss / sl
            sl_match = re.search(r'"(?:stop_loss|sl)"\s*:\s*"?([0-9.]+)"?', raw_data)
            if sl_match:
                sl = sl_match.group(1)
        except:
            pass

        # Record Invalid JSON Error to Trading History
        from app.trades import record_and_broadcast
        record_and_broadcast({
            'status': 'error',
            'action': action,
            'symbol': symbol,
            'account': account,
            'volume': volume,
            'price': price,
            'tp': tp,
            'sl': sl,
            'message': 'Invalid JSON'
        })

        return jsonify({'error': 'Invalid JSON payload'}), 400

    # 3. Log incoming webhook
    logger.info(f"[WEBHOOK] {json.dumps(data, ensure_ascii=False)}")
    action = str(data.get('action', 'UNKNOWN')).upper()
    symbol = data.get('symbol', '-')
    volume = data.get('volume', '-')
    account = data.get('account_number') or (data.get('accounts', [None])[0] if data.get('accounts') else '-')
    system_logs_service.add_log('info', f'🔥 [200] Webhook received: {action} {symbol} Vol:{volume} Acc:{account}')

    # 4. Validate payload structure
    valid = webhook_service.validate_webhook_payload(data)
    if not valid["valid"]:
        logger.error(f"[BAD_PAYLOAD] {valid['error']}")
        system_logs_service.add_log('error', f'❌ [400] Webhook validation failed: {valid["error"][:80]}')
        email_handler.send_alert("Bad Webhook Payload", f"Validation failed: {valid['error']}")
        return jsonify({'error': valid['error']}), 400

    # 5. Global Secret Key Validation
    provided_secret = data.get('secret', '')
    if not session_manager.validate_global_secret(provided_secret):
        logger.warning("[UNAUTHORIZED] Invalid global secret key")
        system_logs_service.add_log('error', '🔐 [403] Webhook unauthorized - Invalid global secret key')
        email_handler.send_alert("Webhook Secret Key Validation Failed",
                               "Invalid global secret key provided in webhook request")
        return jsonify({'error': 'Unauthorized - Invalid secret key'}), 403

    logger.info("[SECRET_VALIDATED] ✅ Global secret key validated")

    # 6. Symbol Mapping
    account_for_mapping = None
    if isinstance(data.get('account_number'), (str, int)):
        account_for_mapping = str(data.get('account_number')).strip()
    elif isinstance(data.get('accounts'), list) and len(data.get('accounts')) > 0:
        account_for_mapping = str(data['accounts'][0]).strip()

    if account_for_mapping and 'symbol' in data:
        original_symbol = data['symbol']
        mapped_symbol = session_manager.map_symbol(account_for_mapping, original_symbol)

        if mapped_symbol != original_symbol:
            data['symbol'] = mapped_symbol
            logger.info(f"[SYMBOL_MAPPED] {original_symbol} → {mapped_symbol} for account {account_for_mapping}")
            system_logs_service.add_log('info', f'🔄 Symbol mapped: {original_symbol} → {mapped_symbol} (Acc: {account_for_mapping})')

    # 7. Symbol Translation (via SignalTranslator)
    try:
        account = None
        if isinstance(data.get('account_number'), (str, int)):
            account = str(data.get('account_number')).strip()
        elif isinstance(data.get('accounts'), list) and len(data.get('accounts')) == 1:
            account = str(data['accounts'][0]).strip()

        if account and 'symbol' in data:
            translated_signal = signal_translator.translate_for_account(
                data,
                account,
                auto_map_symbol=True
            )
            if not translated_signal:
                logger.warning(f"[WEBHOOK] Symbol {data.get('symbol')} not available in account {account}")
                system_logs_service.add_log('error', f'❌ [400] Symbol not available')
                return jsonify({'error': 'Symbol not available in target account'}), 400
            data['symbol'] = translated_signal.get('symbol', data['symbol'])
            data['original_symbol'] = translated_signal.get('original_symbol')
    except Exception as _e_tr:
        logger.error(f"[WEBHOOK_TRANSLATE_ERROR] {_e_tr}", exc_info=True)

    # 8. Update heartbeat for sender account
    account = data.get('account_number') or (data.get('accounts', [None])[0] if data.get('accounts') else None)
    if account:
        session_manager.update_account_heartbeat(str(account))

    # 9. Account allowlist and status checks
    target_accounts = data.get('accounts') or [data.get('account_number')]
    allowed, blocked = [], []

    for acc in target_accounts:
        acc_str = str(acc).strip()

        # Check webhook allowlist
        if not account_allowlist_service.is_account_allowed_for_webhook(acc_str):
            blocked.append(acc_str)

            from app.trades import record_and_broadcast
            record_and_broadcast({
                'status': 'error',
                'action': str(data.get('action', 'UNKNOWN')).upper(),
                'symbol': data.get('symbol', '-'),
                'account': acc_str,
                'volume': data.get('volume', ''),
                'price': data.get('price', ''),
                'tp': data.get('take_profit', ''),
                'sl': data.get('stop_loss', ''),
                'message': 'Account not in Webhook Management'
            })

            logger.error(f"[WEBHOOK_ERROR] Account {acc_str} not in Webhook Management")
            system_logs_service.add_log('warning', f'⚠️ [403] Webhook blocked - Account {acc_str} not in whitelist')
            continue

        # Check if account is PAUSED
        account_info = session_manager.get_account_info(acc_str)
        if account_info and account_info.get("status") == "PAUSE":
            blocked.append(acc_str)

            from app.trades import record_and_broadcast
            record_and_broadcast({
                "status": "error",
                "action": str(data.get("action", "UNKNOWN")).upper(),
                "symbol": data.get("symbol", "-"),
                "account": acc_str,
                "volume": data.get("volume", ""),
                "price": data.get("price", ""),
                "tp": data.get("take_profit", ""),
                "sl": data.get("stop_loss", ""),
                "message": "Account Paused"
            })
            logger.warning(f"[WEBHOOK_BLOCKED] Account {acc_str} is PAUSED")
            system_logs_service.add_log("warning", f"[403] Webhook blocked - Account {acc_str} is paused")
            continue

        # Check if account can receive orders
        can_receive, reason = session_manager.can_receive_orders(acc_str)
        if not can_receive:
            blocked.append(acc_str)

            from app.trades import record_and_broadcast
            record_and_broadcast({
                "status": "error",
                "action": str(data.get("action", "UNKNOWN")).upper(),
                "symbol": data.get("symbol", "-"),
                "account": acc_str,
                "volume": data.get("volume", ""),
                "price": data.get("price", ""),
                "tp": data.get("take_profit", ""),
                "sl": data.get("stop_loss", ""),
                "message": f"{reason}"
            })
            logger.warning(f"[WEBHOOK_BLOCKED] Account {acc_str} cannot receive orders: {reason}")
            system_logs_service.add_log("warning", f"[403] Webhook blocked - Account {acc_str}: {reason}")
            continue

        # Account passed all checks
        allowed.append(acc_str)

    # 10. Check if any accounts are allowed
    if not allowed:
        error_msg = f"No allowed accounts for webhook. Blocked: {', '.join(blocked)}"
        logger.error(f"[WEBHOOK_ERROR] {error_msg}")
        system_logs_service.add_log('error', f'❌ [400] Webhook rejected - All accounts blocked ({len(blocked)} accounts)')
        return jsonify({'error': error_msg}), 400

    # 11. Process webhook with allowed accounts only
    data_processed = dict(data)
    if 'accounts' in data_processed:
        data_processed['accounts'] = allowed
    else:
        data_processed['account_number'] = allowed[0]

    result = webhook_service.process_webhook(data_processed)

    # 12. Return response with logging
    if result.get('success'):
        msg = result.get('message', 'Processed')
        action = data_processed.get('action', 'UNKNOWN')
        symbol = data_processed.get('symbol', '-')
        volume = data_processed.get('volume', '-')
        system_logs_service.add_log('success', f'✅ [200] Webhook processed: {action} {symbol} Vol:{volume} → {len(allowed)} account(s)')
        if blocked:
            msg += f" (⚠️ Blocked {len(blocked)} account(s): {', '.join(blocked)})"
            system_logs_service.add_log('warning', f'⚠️ Webhook partial: {len(blocked)} account(s) blocked')
        return jsonify({'success': True, 'message': msg})
    else:
        error_msg = result.get('error', 'Unknown error')
        system_logs_service.add_log('error', f'❌ [500] Webhook processing failed: {error_msg[:80]}')
        return jsonify({'error': result.get('error', 'Processing failed')}), 500

