"""
Webhooks Services - Business Logic

Core webhook processing logic:
- Payload validation
- Account allowlist management
- Signal processing
- Command preparation
"""

import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Data paths
DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
WEBHOOK_ACCOUNTS_FILE = DATA_DIR / "webhook_accounts.json"


# =================== Utility Functions ===================

def _load_json(path: Path, default: Any) -> Any:
    """Load JSON file safely"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save_json(path: Path, obj: Any) -> None:
    """Save JSON file safely with atomic write"""
    tmp = path.with_suffix('.tmp')
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


# =================== Webhook Account Management ===================

def get_webhook_allowlist() -> List[Dict[str, Any]]:
    """
    Get webhook account allowlist

    Returns:
        List of accounts: [{"account": "111", "nickname": "A", "enabled": true}, ...]
    """
    lst = _load_json(WEBHOOK_ACCOUNTS_FILE, [])
    out = []
    for it in lst:
        acc = str(it.get("account") or it.get("id") or "").strip()
        if acc:
            out.append({
                "account": acc,
                "nickname": it.get("nickname", ""),
                "enabled": bool(it.get("enabled", True)),
            })
    return out


def is_account_allowed_for_webhook(account: str) -> bool:
    """
    Check if account is allowed for webhook

    Args:
        account: Account number

    Returns:
        True if account is in allowlist and enabled
    """
    account = str(account).strip()
    for it in get_webhook_allowlist():
        if it["account"] == account and it.get("enabled", True):
            return True
    return False


def add_webhook_account(account: str, nickname: str = "", enabled: bool = True) -> Dict[str, Any]:
    """
    Add or update account in webhook allowlist

    Args:
        account: Account number
        nickname: Optional nickname
        enabled: Whether account is enabled

    Returns:
        Dict with 'success' and optional 'error'
    """
    try:
        lst = get_webhook_allowlist()

        # Update existing or add new
        found = False
        for it in lst:
            if it["account"] == account:
                it["nickname"] = nickname or it.get("nickname", "")
                it["enabled"] = enabled
                found = True
                break

        if not found:
            lst.append({
                "account": account,
                "nickname": nickname,
                "enabled": enabled
            })

        _save_json(WEBHOOK_ACCOUNTS_FILE, lst)

        status = "updated" if found else "added"
        logger.info(f"[WEBHOOK_ACCOUNTS] {status.capitalize()} account: {account}")

        return {'success': True, 'status': status}

    except Exception as e:
        logger.error(f"[WEBHOOK_ACCOUNTS] Error adding account: {e}")
        return {'success': False, 'error': str(e)}


def remove_webhook_account(account: str) -> Dict[str, Any]:
    """
    Remove account from webhook allowlist

    Args:
        account: Account number

    Returns:
        Dict with 'success' and optional 'error'
    """
    try:
        lst = [it for it in get_webhook_allowlist() if it["account"] != str(account)]
        _save_json(WEBHOOK_ACCOUNTS_FILE, lst)

        logger.info(f"[WEBHOOK_ACCOUNTS] Removed account: {account}")
        return {'success': True}

    except Exception as e:
        logger.error(f"[WEBHOOK_ACCOUNTS] Error removing account: {e}")
        return {'success': False, 'error': str(e)}


def save_webhook_allowlist(accounts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Save entire webhook allowlist

    Args:
        accounts: List of account dicts

    Returns:
        Dict with 'success' and optional 'error'
    """
    try:
        _save_json(WEBHOOK_ACCOUNTS_FILE, accounts)
        return {'success': True}
    except Exception as e:
        logger.error(f"[WEBHOOK_ACCOUNTS] Error saving allowlist: {e}")
        return {'success': False, 'error': str(e)}


# =================== Webhook Validation ===================

def normalize_action(action: str) -> str:
    """
    Normalize action aliases to standard actions

    Mappings:
    - CALL -> BUY
    - PUT -> SELL

    Args:
        action: Original action string

    Returns:
        Normalized action
    """
    if not action:
        return action

    action_upper = str(action).upper().strip()

    action_aliases = {
        'CALL': 'BUY',
        'PUT': 'SELL',
    }

    return action_aliases.get(action_upper, action_upper)


def validate_webhook_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate webhook payload structure

    Args:
        data: Webhook payload

    Returns:
        Dict with 'valid' (bool) and optional 'error' (str)
    """
    # Check required fields
    required_fields = ['action']
    if 'account_number' not in data and 'accounts' not in data:
        return {'valid': False, 'error': 'Missing field: account_number or accounts'}

    for field in required_fields:
        if field not in data:
            return {'valid': False, 'error': f'Missing field: {field}'}

    # Normalize action
    action = normalize_action(data['action'])
    data['action'] = action

    # Validate trading actions
    if action in ['BUY', 'SELL', 'LONG', 'SHORT']:
        if 'symbol' not in data:
            return {'valid': False, 'error': 'symbol required for trading actions'}
        if 'volume' not in data:
            return {'valid': False, 'error': 'volume required for trading actions'}

        # Set default order type
        data.setdefault('order_type', 'market')

        # Validate order type specific fields
        order_type = str(data.get('order_type', 'market')).lower()
        if order_type in ['limit', 'stop'] and 'price' not in data:
            return {'valid': False, 'error': f'price required for {order_type} orders'}

        # Validate volume
        try:
            vol = float(data['volume'])
            if vol <= 0:
                return {'valid': False, 'error': 'Volume must be positive'}
        except Exception:
            return {'valid': False, 'error': 'Volume must be a number'}

    # Validate close actions
    elif action in ['CLOSE', 'CLOSE_ALL', 'CLOSE_SYMBOL']:
        if action == 'CLOSE':
            if 'ticket' not in data and 'symbol' not in data:
                return {'valid': False, 'error': 'ticket or symbol required for CLOSE action'}
            if 'ticket' in data:
                try:
                    int(data['ticket'])
                except Exception:
                    return {'valid': False, 'error': 'ticket must be a number'}

        if action == 'CLOSE_SYMBOL' and 'symbol' not in data:
            return {'valid': False, 'error': 'symbol required for CLOSE_SYMBOL action'}

        # Validate volume if provided
        if 'volume' in data:
            try:
                vol = float(data['volume'])
                if vol <= 0:
                    return {'valid': False, 'error': 'Volume must be positive'}
            except Exception:
                return {'valid': False, 'error': 'Volume must be a number'}

        # Validate position_type if provided
        if 'position_type' in data:
            pt = str(data['position_type']).upper()
            if pt not in ['BUY', 'SELL']:
                return {'valid': False, 'error': 'position_type must be BUY or SELL'}

    else:
        return {
            'valid': False,
            'error': 'Invalid action. Must be one of: BUY, SELL, LONG, SHORT, CALL, PUT, CLOSE, CLOSE_ALL, CLOSE_SYMBOL'
        }

    return {'valid': True}


# =================== Webhook Processing ===================

def prepare_trading_command(data: Dict[str, Any], mapped_symbol: Optional[str], account: str) -> Dict[str, Any]:
    """
    Prepare trading command for MT5 EA

    Args:
        data: Webhook payload
        mapped_symbol: Mapped symbol (if applicable)
        account: Account number

    Returns:
        Command dict for EA
    """
    action = str(data['action']).upper()

    # Normalize LONG/SHORT to BUY/SELL
    if action == 'LONG':
        action = 'BUY'
    elif action == 'SHORT':
        action = 'SELL'

    # Coerce volume to float
    vol = data.get('volume')
    try:
        volume = float(vol) if vol is not None else None
    except Exception:
        volume = vol

    command = {
        'timestamp': datetime.now().isoformat(),
        'action': action,
        'account': str(account),
        'symbol': (mapped_symbol or data.get('symbol')),
        'order_type': str(data.get('order_type', 'market')).lower(),
        'volume': volume,
        'price': data.get('price'),
        'take_profit': data.get('take_profit'),
        'stop_loss': data.get('stop_loss'),
        'ticket': data.get('ticket'),
        'position_type': data.get('position_type'),
        'comment': data.get('comment', '')
    }

    return command


def write_command_for_ea(account: str, command: Dict[str, Any]) -> bool:
    """
    Send command to EA via Command Queue

    Args:
        account: Account number
        command: Command dict

    Returns:
        True if successful
    """
    try:
        from app.services.commands import command_queue

        account = str(account)
        success = command_queue.add_command(account, command)

        if success:
            logger.info(
                f"[WRITE_CMD] ✅ Added to queue: {command.get('action')} "
                f"{command.get('symbol')} for {account}"
            )
        else:
            logger.error(f"[WRITE_CMD] ❌ Failed to add to queue for {account}")

        return success

    except Exception as e:
        logger.error(f"[WRITE_CMD_ERROR] {e}")
        return False


def process_webhook_signal(
    data: Dict[str, Any],
    session_manager: Any,
    record_and_broadcast: callable
) -> Dict[str, Any]:
    """
    Process webhook signal and send commands to target accounts

    Args:
        data: Webhook payload
        session_manager: SessionManager instance
        record_and_broadcast: Function to record trade history

    Returns:
        Dict with 'success' (bool), 'message' (str), and optional 'error' (str)
    """
    try:
        # Get target accounts
        target_accounts = data['accounts'] if 'accounts' in data else [data['account_number']]
        action = str(data['action']).upper()
        mapped_symbol = data.get('symbol')

        results = []

        for account in target_accounts:
            account_str = str(account).strip()

            # 1. Check if account exists
            if not session_manager.account_exists(account_str):
                error_msg = f'Account {account_str} not found in system'
                logger.error(f"[WEBHOOK_ERROR] {error_msg}")

                record_and_broadcast({
                    'status': 'error',
                    'action': action,
                    'symbol': data.get('symbol', '-'),
                    'account': account_str,
                    'volume': data.get('volume', ''),
                    'price': data.get('price', ''),
                    'message': f'❌ {error_msg}'
                })

                results.append({'account': account_str, 'success': False, 'error': error_msg})
                continue

            # 2. Check if account is in webhook allowlist
            if not is_account_allowed_for_webhook(account_str):
                error_msg = f'Account {account_str} not in Webhook Management'
                logger.error(f"[WEBHOOK_ERROR] {error_msg}")

                record_and_broadcast({
                    'status': 'error',
                    'action': action,
                    'symbol': data.get('symbol', '-'),
                    'account': account_str,
                    'volume': data.get('volume', ''),
                    'price': data.get('price', ''),
                    'message': f'❌ {error_msg}'
                })

                results.append({'account': account_str, 'success': False, 'error': error_msg})
                continue

            # 3. Check account status
            account_info = session_manager.get_account_info(account_str)
            account_status = account_info.get('status', '') if account_info else ''

            if account_status == 'Offline':
                error_msg = f'Account {account_str} Offline'
                logger.warning(f"[WEBHOOK_ERROR] {error_msg}")

                record_and_broadcast({
                    'status': 'error',
                    'action': action,
                    'symbol': data.get('symbol', '-'),
                    'account': account_str,
                    'volume': data.get('volume', ''),
                    'price': data.get('price', ''),
                    'message': 'Account Offline'
                })

                results.append({'account': account_str, 'success': False, 'error': error_msg})
                continue

            # 4. Check if account is paused
            if account_status == 'PAUSE':
                error_msg = f'Account {account_str} is paused'
                logger.warning(f"[WEBHOOK_BLOCKED] {error_msg}")

                record_and_broadcast({
                    'status': 'error',
                    'action': action,
                    'symbol': data.get('symbol', '-'),
                    'account': account_str,
                    'volume': data.get('volume', ''),
                    'price': data.get('price', ''),
                    'message': 'Account Paused'
                })

                results.append({'account': account_str, 'success': False, 'error': error_msg})
                continue

            # 5. Check if account can receive orders
            can_receive, reason = session_manager.can_receive_orders(account_str)
            if not can_receive:
                error_msg = f'Account {account_str}: {reason}'
                logger.warning(f"[WEBHOOK_BLOCKED] {error_msg}")

                record_and_broadcast({
                    'status': 'error',
                    'action': action,
                    'symbol': data.get('symbol', '-'),
                    'account': account_str,
                    'volume': data.get('volume', ''),
                    'price': data.get('price', ''),
                    'message': reason
                })

                results.append({'account': account_str, 'success': False, 'error': error_msg})
                continue

            # 6. Prepare and send command
            cmd = prepare_trading_command(data, mapped_symbol, account_str)
            ok = write_command_for_ea(account_str, cmd)

            if ok:
                record_and_broadcast({
                    'status': 'success',
                    'action': action,
                    'order_type': data.get('order_type', 'market'),
                    'symbol': mapped_symbol or data.get('symbol', '-'),
                    'account': account_str,
                    'volume': data.get('volume', ''),
                    'price': data.get('price', ''),
                    'tp': data.get('take_profit', ''),
                    'sl': data.get('stop_loss', ''),
                    'message': f'{action} command sent to EA'
                })

                results.append({
                    'account': account_str,
                    'success': True,
                    'command': cmd,
                    'action': action
                })
            else:
                error_msg = 'Failed to write command file'

                record_and_broadcast({
                    'status': 'error',
                    'action': action,
                    'order_type': data.get('order_type', 'market'),
                    'symbol': mapped_symbol or data.get('symbol', '-'),
                    'account': account_str,
                    'volume': data.get('volume', ''),
                    'price': data.get('price', ''),
                    'tp': data.get('take_profit', ''),
                    'sl': data.get('stop_loss', ''),
                    'message': error_msg
                })

                results.append({'account': account_str, 'success': False, 'error': error_msg})

        # Summarize results
        success_count = sum(1 for r in results if r['success'])
        total_count = len(results)

        if success_count == total_count:
            return {
                'success': True,
                'message': f'{action} sent to {success_count}/{total_count} accounts'
            }
        elif success_count > 0:
            return {
                'success': True,
                'message': f'{action} partial success: {success_count}/{total_count} accounts'
            }
        else:
            return {
                'success': False,
                'error': f'Failed to send {action} to any account'
            }

    except Exception as e:
        logger.error(f"[WEBHOOK_ERROR] {e}", exc_info=True)
        return {'success': False, 'error': str(e)}

