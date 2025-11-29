"""
Webhooks Routes - Flask Blueprint

All webhook-related HTTP endpoints:
- POST /webhook/<token> - Main webhook handler
- GET /webhook - Webhook information
- GET /webhook/health - Health check
- GET /webhook-url - Get webhook URL (authenticated)
- GET /webhook-accounts - Manage webhook accounts (authenticated)
- POST /webhook-accounts - Add webhook account (authenticated)
- DELETE /webhook-accounts/<account> - Remove webhook account (authenticated)
"""

import os
import json
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify

from .services import (
    validate_webhook_payload,
    process_webhook_signal,
    get_webhook_allowlist,
    is_account_allowed_for_webhook,
    add_webhook_account,
    remove_webhook_account,
    save_webhook_allowlist
)

logger = logging.getLogger(__name__)

# Create Blueprint
webhooks_bp = Blueprint('webhooks', __name__)

# Get environment variables
WEBHOOK_TOKEN = os.getenv('WEBHOOK_TOKEN', 'default-token')
EXTERNAL_BASE_URL = os.getenv('EXTERNAL_BASE_URL', 'http://localhost:5000')


# =================== Public Webhook Endpoints ===================

@webhooks_bp.get('/webhook')
@webhooks_bp.get('/webhook/')
def webhook_info():
    """Webhook endpoint information (public)"""
    return jsonify({
        'message': 'Webhook endpoint active',
        'supported_methods': ['POST'],
        'health_check': '/webhook/health',
        'endpoint_format': '/webhook/{token}',
        'supported_actions': ['BUY', 'SELL', 'LONG', 'SHORT', 'CALL', 'PUT', 'CLOSE', 'CLOSE_ALL', 'CLOSE_SYMBOL'],
        'timestamp': datetime.now().isoformat()
    })


@webhooks_bp.get('/webhook/health')
def webhook_health():
    """Webhook health check (public)"""
    return jsonify({
        'status': 'ok',
        'webhook_status': 'active',
        'timestamp': datetime.now().isoformat()
    })


@webhooks_bp.post('/webhook/<token>')
def webhook_handler(token):
    """
    Main webhook handler - Process incoming trading signals

    This endpoint receives webhook signals from TradingView or other sources,
    validates them, and forwards commands to MT5 EA instances.

    Authentication:
    - Token-based (URL token)
    - Global secret key (optional)
    - Account allowlist

    Rate Limiting:
    - Applied via @limiter.limit() decorator in server.py

    Args:
        token: URL token for authentication

    Returns:
        JSON response with success/error status
    """
    # Import dependencies (late import to avoid circular dependencies)
    from app.services.accounts import SessionManager
    from app.services.signals import SignalTranslator
    from app.services.symbols import SymbolMapper
    from app.services.broker import BrokerDataManager
    from app.core.email import EmailHandler
    from app.trades import record_and_broadcast

    # Get singletons from app context
    session_manager = SessionManager()
    symbol_mapper = SymbolMapper()
    broker_manager = BrokerDataManager(data_dir='data')
    signal_translator = SignalTranslator(broker_manager, symbol_mapper)
    email_handler = EmailHandler()

    # 1. Token validation
    if token != WEBHOOK_TOKEN:
        logger.warning("[UNAUTHORIZED] Invalid webhook token")
        email_handler.send_alert("Unauthorized Webhook Access", "Invalid token")
        return jsonify({'error': 'Unauthorized'}), 401

    # 2. Parse JSON payload
    try:
        data = request.get_json()
        if not data:
            raise ValueError("No JSON data received")
    except Exception as e:
        logger.error(f"[BAD_PAYLOAD] {e}")
        email_handler.send_alert("Bad Webhook Payload", f"Invalid JSON: {e}")

        # Try to extract partial data for history
        raw_data = request.get_data(as_text=True)
        account = '-'
        action = 'UNKNOWN'
        symbol = '-'

        try:
            import re
            acc_match = re.search(r'"account(?:_number)?"\s*:\s*"?(\d+)"?', raw_data)
            if acc_match:
                account = acc_match.group(1)
            action_match = re.search(r'"action"\s*:\s*"([^"]+)"', raw_data)
            if action_match:
                action = action_match.group(1).upper()
            symbol_match = re.search(r'"symbol"\s*:\s*"([^"]+)"', raw_data)
            if symbol_match:
                symbol = symbol_match.group(1)
        except:
            pass

        record_and_broadcast({
            'status': 'error',
            'action': action,
            'symbol': symbol,
            'account': account,
            'message': 'Invalid JSON'
        })

        return jsonify({'error': 'Invalid JSON payload'}), 400

    logger.info(f"[WEBHOOK] {json.dumps(data, ensure_ascii=False)}")

    # 3. Validate payload structure
    validation = validate_webhook_payload(data)
    if not validation["valid"]:
        logger.error(f"[BAD_PAYLOAD] {validation['error']}")
        email_handler.send_alert("Bad Webhook Payload", f"Validation failed: {validation['error']}")
        return jsonify({'error': validation['error']}), 400

    # 4. Global secret key validation
    provided_secret = data.get('secret', '')
    if not session_manager.validate_global_secret(provided_secret):
        logger.warning("[UNAUTHORIZED] Invalid global secret key")
        email_handler.send_alert(
            "Webhook Secret Key Validation Failed",
            "Invalid global secret key provided in webhook request"
        )
        return jsonify({'error': 'Unauthorized - Invalid secret key'}), 403

    logger.info("[SECRET_VALIDATED] ✅ Global secret key validated")

    # 5. Symbol mapping (if applicable)
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

    # 6. Symbol translation for target account
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
                return jsonify({'error': 'Symbol not available in target account'}), 400

            data['symbol'] = translated_signal.get('symbol', data['symbol'])
            data['original_symbol'] = translated_signal.get('original_symbol')
    except Exception as e:
        logger.error(f"[WEBHOOK_TRANSLATE_ERROR] {e}", exc_info=True)

    # 7. Update heartbeat for account
    account = data.get('account_number') or (data.get('accounts', [None])[0] if data.get('accounts') else None)
    if account:
        session_manager.update_account_heartbeat(str(account))

    # 8. Process webhook signal
    result = process_webhook_signal(
        data=data,
        session_manager=session_manager,
        record_and_broadcast=record_and_broadcast
    )

    if result.get('success'):
        return jsonify({
            'success': True,
            'message': result.get('message', 'Processed')
        })
    else:
        return jsonify({'error': result.get('error', 'Processing failed')}), 500


# =================== Authenticated Webhook Management ===================

# Note: Authentication decorators must be applied in server.py using before_request
# or the decorator must be imported here and applied directly

@webhooks_bp.get('/webhook-url')
def get_webhook_url():
    """Get webhook URL (requires authentication via server.py @session_login_required)"""
    return jsonify({'url': f"{EXTERNAL_BASE_URL}/webhook/{WEBHOOK_TOKEN}"})


@webhooks_bp.get('/webhook-accounts')
def list_webhook_accounts():
    """List all webhook accounts (requires authentication via server.py @session_login_required)"""
    return jsonify({"accounts": get_webhook_allowlist()})


@webhooks_bp.post('/webhook-accounts')
def add_webhook_account_endpoint():
    """Add account to webhook allowlist (requires authentication via server.py @session_login_required)"""
    from app.services.accounts import SessionManager

    data = request.get_json(silent=True) or {}
    account = str(data.get("account") or data.get("id") or "").strip()

    if not account:
        return jsonify({"error": "account required"}), 400

    nickname = str(data.get("nickname") or "").strip()
    enabled = bool(data.get("enabled", True))

    # Create account in Account Management if it doesn't exist
    session_manager = SessionManager()
    if not session_manager.account_exists(account):
        if not session_manager.add_remote_account(account, nickname):
            return jsonify({'error': f'Failed to create account {account}'}), 500
        logger.info(f"[API] Created new account in Account Management: {account}")

    # Add to webhook allowlist
    result = add_webhook_account(account, nickname, enabled)

    if result['success']:
        return jsonify({"ok": True, "account": account})
    else:
        return jsonify({"error": result.get('error', 'Failed to add account')}), 500


@webhooks_bp.delete('/webhook-accounts/<account>')
def delete_webhook_account_endpoint(account):
    """Remove account from webhook allowlist (requires authentication)"""
    # Note: @session_login_required decorator applied in server.py
    result = remove_webhook_account(account)
    return jsonify({"ok": result['success']})

