"""
Accounts Routes - Flask Blueprint

All account management HTTP endpoints:
- GET /accounts - List all accounts
- POST /accounts - Add new account
- DELETE /accounts/<account> - Delete account
- POST /accounts/<account>/pause - Pause account
- POST /accounts/<account>/resume - Resume account
- POST /accounts/<account>/restart - Restart account (remote mode not supported)
- POST /accounts/<account>/stop - Stop account (remote mode not supported)
- POST /accounts/<account>/open - Open account (remote mode not supported)
- GET /accounts/stats - Get account statistics
"""

import json
import logging
from pathlib import Path
from flask import Blueprint, request, jsonify, current_app

logger = logging.getLogger(__name__)

# Create Blueprint
accounts_bp = Blueprint('accounts', __name__)


# =================== Account Management Endpoints ===================

@accounts_bp.get('/accounts')
def get_accounts():
    """
    Get all accounts

    Returns:
        JSON response with list of accounts
    """
    # Import services (late import to avoid circular dependencies)
    from app.services.accounts import SessionManager

    session_manager = SessionManager()

    try:
        return jsonify({'accounts': session_manager.get_all_accounts()})
    except Exception as e:
        logger.error(f"[GET_ACCOUNTS_ERROR] {e}")
        return jsonify({'error': str(e)}), 500


@accounts_bp.post('/accounts')
def add_account():
    """
    Add new account

    Request Body:
        {
            "account": "123456",
            "nickname": "My Account"
        }

    Returns:
        JSON response with success status
    """
    # Import services and utilities
    from app.services.accounts import SessionManager

    session_manager = SessionManager()

    try:
        data = request.get_json() or {}
        account = str(data.get('account', '')).strip()
        nickname = str(data.get('nickname', '')).strip()

        if not account:
            return jsonify({'error': 'Account number is required'}), 400

        if session_manager.account_exists(account):
            # Log to system logs if available
            try:
                from server import add_system_log
                add_system_log('warning', f'⚠️ [400] Account creation failed - {account} already exists')
            except:
                pass
            return jsonify({'error': 'Account already exists'}), 400

        # Add remote account (API mode)
        if session_manager.add_remote_account(account, nickname):
            logger.info(f"[REMOTE_ACCOUNT_ADDED] {account} ({nickname})")

            # Log to system logs if available
            try:
                from server import add_system_log
                add_system_log('success', f'✅ Account {account} added (waiting for EA connection)')
            except:
                pass

            return jsonify({
                'success': True,
                'message': 'Account added successfully. Status: Wait for Activate'
            })

        return jsonify({'error': 'Failed to add account'}), 500

    except Exception as e:
        logger.error(f"[ADD_ACCOUNT_ERROR] {e}")
        return jsonify({'error': str(e)}), 500


@accounts_bp.post('/accounts/<account>/restart')
def restart_account(account):
    """Restart account (not available in remote mode)"""
    return jsonify({'error': 'Not available in remote mode'}), 400


@accounts_bp.post('/accounts/<account>/stop')
def stop_account(account):
    """Stop account (not available in remote mode)"""
    return jsonify({'error': 'Not available in remote mode'}), 400


@accounts_bp.post('/accounts/<account>/open')
def open_account(account):
    """Open account (not available in remote mode)"""
    return jsonify({'error': 'Not available in remote mode'}), 400


@accounts_bp.post('/accounts/<account>/pause')
def pause_account(account):
    """
    Pause account - block incoming signals

    Args:
        account: Account number

    Returns:
        JSON response with success status
    """
    from app.services.accounts import SessionManager

    session_manager = SessionManager()

    try:
        account = str(account).strip()

        if not session_manager.account_exists(account):
            return jsonify({'error': 'Account not found'}), 404

        # Update status to PAUSE
        session_manager.update_account_status(account, 'PAUSE')
        logger.info(f"[PAUSE_ACCOUNT] Account {account} has been paused")

        # Log to system logs if available
        try:
            from server import add_system_log
            add_system_log('warning', f'⏸️ [200] Account paused: {account}')
        except:
            pass

        return jsonify({
            'success': True,
            'message': 'Account paused successfully'
        }), 200

    except Exception as e:
        logger.error(f"[PAUSE_ACCOUNT_ERROR] {e}")
        return jsonify({'error': str(e)}), 500


@accounts_bp.post('/accounts/<account>/resume')
def resume_account(account):
    """
    Resume account - re-enable incoming signals

    Args:
        account: Account number

    Returns:
        JSON response with success status
    """
    from app.services.accounts import SessionManager

    session_manager = SessionManager()

    try:
        account = str(account).strip()

        if not session_manager.account_exists(account):
            return jsonify({'error': 'Account not found'}), 404

        # Get current status
        account_info = session_manager.get_account_info(account)
        if not account_info or account_info.get('status') != 'PAUSE':
            return jsonify({'error': 'Account is not paused'}), 400

        # Update status to Online
        session_manager.update_account_status(account, 'Online')
        logger.info(f"[RESUME_ACCOUNT] Account {account} has been resumed")

        # Log to system logs if available
        try:
            from server import add_system_log
            add_system_log('success', f'▶️ [200] Account resumed: {account}')
        except:
            pass

        return jsonify({
            'success': True,
            'message': 'Account resumed successfully'
        }), 200

    except Exception as e:
        logger.error(f"[RESUME_ACCOUNT_ERROR] {e}")
        return jsonify({'error': str(e)}), 500


@accounts_bp.delete('/accounts/<account>')
def delete_account(account):
    """
    Delete account and clean up related data

    Cleans up:
    - Account from session manager
    - Trade history
    - Webhook allowlist
    - Master/slave accounts
    - Copy trading pairs
    - Copy trading history

    Args:
        account: Account number

    Returns:
        JSON response with cleanup summary
    """
    from app.services.accounts import SessionManager
    from app.modules.webhooks.services import get_webhook_allowlist, save_webhook_allowlist

    session_manager = SessionManager()

    try:
        account = str(account)
        ok = session_manager.delete_account(account)
        current_app.logger.info(f'[DELETE_ACCOUNT] account={account} ok={ok}')

        if ok:
            cleanup_logs = []

            # 1. Delete trade history
            try:
                from app.trades import delete_account_history
                deleted = delete_account_history(account)
                current_app.logger.info(f'[HISTORY_DELETED] {deleted} events for {account}')
                cleanup_logs.append(f'{deleted} history records')
            except Exception as e:
                current_app.logger.warning(f'[HISTORY_DELETE_ERROR] {e}')

            # 2. Remove from webhook_accounts.json
            try:
                webhook_list = get_webhook_allowlist()
                original_count = len(webhook_list)
                webhook_list = [it for it in webhook_list if it["account"] != account]
                if len(webhook_list) < original_count:
                    save_webhook_allowlist(webhook_list)
                    current_app.logger.info(f'[WEBHOOK_CLEANUP] Removed account {account} from webhook accounts')
                    cleanup_logs.append('webhook account')
            except Exception as e:
                current_app.logger.warning(f'[WEBHOOK_CLEANUP_ERROR] {e}')

            # 3. Remove from master_accounts.json
            try:
                master_file = Path('data/master_accounts.json')
                if master_file.exists():
                    with open(master_file, 'r', encoding='utf-8') as f:
                        masters = json.load(f)
                    original_count = len(masters)
                    masters = [m for m in masters if m.get('account') != account]
                    if len(masters) < original_count:
                        with open(master_file, 'w', encoding='utf-8') as f:
                            json.dump(masters, f, indent=2, ensure_ascii=False)
                        current_app.logger.info(f'[MASTER_CLEANUP] Removed account {account} from master accounts')
                        cleanup_logs.append('master account')
            except Exception as e:
                current_app.logger.warning(f'[MASTER_CLEANUP_ERROR] {e}')

            # 4. Remove from slave_accounts.json
            try:
                slave_file = Path('data/slave_accounts.json')
                if slave_file.exists():
                    with open(slave_file, 'r', encoding='utf-8') as f:
                        slaves = json.load(f)
                    original_count = len(slaves)
                    slaves = [s for s in slaves if s.get('account') != account]
                    if len(slaves) < original_count:
                        with open(slave_file, 'w', encoding='utf-8') as f:
                            json.dump(slaves, f, indent=2, ensure_ascii=False)
                        current_app.logger.info(f'[SLAVE_CLEANUP] Removed account {account} from slave accounts')
                        cleanup_logs.append('slave account')
            except Exception as e:
                current_app.logger.warning(f'[SLAVE_CLEANUP_ERROR] {e}')

            # 5. Delete copy pairs that use this account
            deleted_pairs_count = 0
            try:
                from app.copy_trading.copy_manager import CopyManager
                from app.core.email import EmailHandler

                email_handler = EmailHandler()
                copy_manager = CopyManager(email_handler=email_handler)
                deleted_pairs_count = copy_manager.delete_pairs_by_account(account)

                if deleted_pairs_count > 0:
                    current_app.logger.info(f'[PAIR_CLEANUP] Deleted {deleted_pairs_count} pairs for account {account}')
                    cleanup_logs.append(f'{deleted_pairs_count} pairs deleted')
            except Exception as e:
                current_app.logger.warning(f'[PAIR_CLEANUP_ERROR] {e}')

            # 6. Delete copy trading history for this account
            deleted_history_count = 0
            try:
                from app.copy_trading.copy_history import CopyHistory
                copy_history = CopyHistory()
                deleted_history_count = copy_history.delete_by_account(account)

                if deleted_history_count > 0:
                    current_app.logger.info(f'[HISTORY_CLEANUP] Deleted {deleted_history_count} copy history events for account {account}')
                    cleanup_logs.append(f'{deleted_history_count} copy history events')
            except Exception as e:
                current_app.logger.warning(f'[COPY_HISTORY_CLEANUP_ERROR] {e}')

            # Log summary
            try:
                from server import add_system_log
                if cleanup_logs:
                    cleanup_summary = ', '.join(cleanup_logs)
                    add_system_log('warning', f'🗑️ [200] Account deleted: {account} (cleaned: {cleanup_summary})')
                else:
                    add_system_log('warning', f'🗑️ [200] Account deleted: {account}')
            except:
                pass

            return jsonify({
                'ok': True,
                'deleted_pairs': deleted_pairs_count,
                'message': f'Account deleted with {deleted_pairs_count} copy pair(s) removed'
            }), 200
        else:
            return jsonify({'ok': False}), 200

    except Exception as e:
        current_app.logger.exception('[DELETE_ACCOUNT_ERROR]')
        return jsonify({'ok': False, 'error': str(e)}), 500


@accounts_bp.get('/accounts/stats')
def accounts_stats():
    """
    Get account statistics

    Returns:
        JSON response with total, online, and offline counts
    """
    from app.services.accounts import SessionManager

    session_manager = SessionManager()

    accounts = session_manager.get_all_accounts()
    total = len(accounts)
    online = sum(1 for a in accounts if a.get('status') == 'Online')
    offline = max(total - online, 0)

    return jsonify({'ok': True, 'total': total, 'online': online, 'offline': offline})

