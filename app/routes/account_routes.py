"""
Account Routes
Handles account management endpoints and webhook account allowlist management
"""
import json
import logging
from pathlib import Path
from flask import Blueprint, request, jsonify
from app.middleware.auth import session_login_required

logger = logging.getLogger(__name__)

# Create blueprint
account_bp = Blueprint('account', __name__)

# These will be injected by the app factory
session_manager = None
system_logs_service = None
account_allowlist_service = None
copy_manager = None
copy_history = None
delete_account_history_fn = None


def init_account_routes(sm, sls, aas, cm, ch, dah_fn):
    """
    Initialize account routes with dependencies

    Args:
        sm: SessionManager instance
        sls: SystemLogsService instance
        aas: AccountAllowlistService instance
        cm: CopyManager instance
        ch: CopyHistory instance
        dah_fn: delete_account_history function
    """
    global session_manager, system_logs_service, account_allowlist_service
    global copy_manager, copy_history, delete_account_history_fn

    session_manager = sm
    system_logs_service = sls
    account_allowlist_service = aas
    copy_manager = cm
    copy_history = ch
    delete_account_history_fn = dah_fn


# =================== Account Management Routes ===================

@account_bp.route('/accounts', methods=['GET'])
@session_login_required
def get_accounts():
    """Get all accounts"""
    try:
        return jsonify({'accounts': session_manager.get_all_accounts()})
    except Exception as e:
        logger.error(f"[GET_ACCOUNTS_ERROR] {e}")
        return jsonify({'error': str(e)}), 500


@account_bp.route('/accounts', methods=['POST'])
@session_login_required
def add_account():
    """Add a new account"""
    try:
        data = request.get_json() or {}
        account = str(data.get('account', '')).strip()
        nickname = str(data.get('nickname', '')).strip()

        if not account:
            return jsonify({'error': 'Account number is required'}), 400

        if session_manager.account_exists(account):
            system_logs_service.add_log('warning', f'⚠️ [400] Account creation failed - {account} already exists')
            return jsonify({'error': 'Account already exists'}), 400

        # Add remote account (waits for EA connection)
        if session_manager.add_remote_account(account, nickname):
            logger.info(f"[REMOTE_ACCOUNT_ADDED] {account} ({nickname})")
            system_logs_service.add_log('success', f'✅ Account {account} added (waiting for EA connection)')
            return jsonify({
                'success': True,
                'message': 'Account added successfully. Status: Wait for Activate'
            })

        return jsonify({'error': 'Failed to add account'}), 500
    except Exception as e:
        logger.error(f"[ADD_ACCOUNT_ERROR] {e}")
        return jsonify({'error': str(e)}), 500


@account_bp.route('/accounts/<account>/restart', methods=['POST'])
@session_login_required
def restart_account(account):
    """Restart account (not available in remote mode)"""
    return jsonify({'error': 'Not available in remote mode'}), 400


@account_bp.route('/accounts/<account>/stop', methods=['POST'])
@session_login_required
def stop_account(account):
    """Stop account (not available in remote mode)"""
    return jsonify({'error': 'Not available in remote mode'}), 400


@account_bp.route('/accounts/<account>/open', methods=['POST'])
@session_login_required
def open_account(account):
    """Open account (not available in remote mode)"""
    return jsonify({'error': 'Not available in remote mode'}), 400


@account_bp.route('/accounts/<account>/pause', methods=['POST'])
@session_login_required
def pause_account(account):
    """Pause account - set status to PAUSE to block incoming signals"""
    try:
        account = str(account).strip()
        if not session_manager.account_exists(account):
            return jsonify({'error': 'Account not found'}), 404

        # Update status to PAUSE
        session_manager.update_account_status(account, 'PAUSE')
        logger.info(f"[PAUSE_ACCOUNT] Account {account} has been paused")
        system_logs_service.add_log('warning', f'⏸️ [200] Account paused: {account}')

        return jsonify({
            'success': True,
            'message': 'Account paused successfully'
        }), 200
    except Exception as e:
        logger.error(f"[PAUSE_ACCOUNT_ERROR] {e}")
        return jsonify({'error': str(e)}), 500


@account_bp.route('/accounts/<account>/resume', methods=['POST'])
@session_login_required
def resume_account(account):
    """Resume account - set status back to Online"""
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
        system_logs_service.add_log('success', f'▶️ [200] Account resumed: {account}')

        return jsonify({
            'success': True,
            'message': 'Account resumed successfully'
        }), 200
    except Exception as e:
        logger.error(f"[RESUME_ACCOUNT_ERROR] {e}")
        return jsonify({'error': str(e)}), 500


@account_bp.route('/accounts/<account>', methods=['DELETE'])
@session_login_required
def delete_account(account):
    """Delete account and cleanup all associated data"""
    try:
        account = str(account)
        ok = session_manager.delete_account(account)
        logger.info(f'[DELETE_ACCOUNT] account={account} ok={ok}')

        if ok:
            cleanup_logs = []

            # 1. Delete trade history
            try:
                deleted = delete_account_history_fn(account)
                logger.info(f'[HISTORY_DELETED] {deleted} events for {account}')
                cleanup_logs.append(f'{deleted} history records')
            except Exception as e:
                logger.warning(f'[HISTORY_DELETE_ERROR] {e}')

            # 2. Remove from webhook_accounts.json
            try:
                if account_allowlist_service.delete_webhook_account(account):
                    logger.info(f'[WEBHOOK_CLEANUP] Removed account {account} from webhook accounts')
                    cleanup_logs.append('webhook account')
            except Exception as e:
                logger.warning(f'[WEBHOOK_CLEANUP_ERROR] {e}')

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
                        logger.info(f'[MASTER_CLEANUP] Removed account {account} from master accounts')
                        cleanup_logs.append('master account')
            except Exception as e:
                logger.warning(f'[MASTER_CLEANUP_ERROR] {e}')

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
                        logger.info(f'[SLAVE_CLEANUP] Removed account {account} from slave accounts')
                        cleanup_logs.append('slave account')
            except Exception as e:
                logger.warning(f'[SLAVE_CLEANUP_ERROR] {e}')

            # 5. Delete copy pairs that use this account
            deleted_pairs_count = 0
            try:
                deleted_pairs_count = copy_manager.delete_pairs_by_account(account)
                if deleted_pairs_count > 0:
                    logger.info(f'[PAIR_CLEANUP] Deleted {deleted_pairs_count} pairs for account {account}')
                    cleanup_logs.append(f'{deleted_pairs_count} pairs deleted')
            except Exception as e:
                logger.warning(f'[PAIR_CLEANUP_ERROR] {e}')

            # 6. Delete copy trading history for this account
            deleted_history_count = 0
            try:
                deleted_history_count = copy_history.delete_by_account(account)
                if deleted_history_count > 0:
                    logger.info(f'[HISTORY_CLEANUP] Deleted {deleted_history_count} copy history events for account {account}')
                    cleanup_logs.append(f'{deleted_history_count} copy history events')
            except Exception as e:
                logger.warning(f'[COPY_HISTORY_CLEANUP_ERROR] {e}')

            # Log summary
            if cleanup_logs:
                cleanup_summary = ', '.join(cleanup_logs)
                system_logs_service.add_log('warning', f'🗑️ [200] Account deleted: {account} (cleaned: {cleanup_summary})')
            else:
                system_logs_service.add_log('warning', f'🗑️ [200] Account deleted: {account}')

            return jsonify({
                'ok': True,
                'deleted_pairs': deleted_pairs_count,
                'message': f'Account deleted with {deleted_pairs_count} copy pair(s) removed'
            }), 200
        else:
            return jsonify({'ok': False}), 200
    except Exception as e:
        logger.exception('[DELETE_ACCOUNT_ERROR]')
        return jsonify({'ok': False, 'error': str(e)}), 500


# =================== Webhook Account Allowlist Management Routes ===================

@account_bp.route('/webhook-accounts', methods=['GET'])
@session_login_required
def list_webhook_accounts():
    """Get list of webhook allowed accounts"""
    return jsonify({"accounts": account_allowlist_service.get_webhook_allowlist()})


@account_bp.route('/webhook-accounts', methods=['POST'])
@session_login_required
def add_webhook_account():
    """Add or update webhook allowed account"""
    data = request.get_json(silent=True) or {}
    account = str(data.get("account") or data.get("id") or "").strip()

    if not account:
        system_logs_service.add_log('error', '❌ [400] Webhook account creation failed - Account number required')
        return jsonify({"error": "account required"}), 400

    nickname = str(data.get("nickname") or "").strip()
    enabled = bool(data.get("enabled", True))

    # If account doesn't exist in Account Management, create it
    if not session_manager.account_exists(account):
        if not session_manager.add_remote_account(account, nickname):
            return jsonify({'error': f'Failed to create account {account}'}), 500
        logger.info(f"[API] Created new account in Account Management: {account}")

    # Add to webhook allowlist
    if account_allowlist_service.add_webhook_account(account, nickname, enabled):
        status_text = "updated" if any(it["account"] == account for it in account_allowlist_service.get_webhook_allowlist()[:-1]) else "added"
        system_logs_service.add_log('success', f'✅ [200] Webhook account {status_text}: {account} ({nickname})')
        return jsonify({"ok": True, "account": account})
    else:
        return jsonify({"error": "Failed to save webhook account"}), 500


@account_bp.route('/webhook-accounts/<account>', methods=['DELETE'])
@session_login_required
def delete_webhook_account(account):
    """Remove account from webhook allowlist"""
    if account_allowlist_service.delete_webhook_account(account):
        system_logs_service.add_log('warning', f'🗑️ [200] Webhook account removed: {account}')
        return jsonify({"ok": True})
    else:
        return jsonify({"error": "Failed to delete webhook account"}), 500

