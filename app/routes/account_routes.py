"""
Account Routes
Handles account management endpoints and webhook account allowlist management
"""
import json
import logging
from pathlib import Path
from flask import Blueprint, request, jsonify
from app.middleware.auth import require_auth, session_login_required

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
@require_auth
def get_accounts():
    """Get all accounts"""
    try:
        return jsonify({'accounts': session_manager.get_all_accounts()})
    except Exception as e:
        logger.error(f"[GET_ACCOUNTS_ERROR] {e}")
        return jsonify({'error': str(e)}), 500


@account_bp.route('/accounts', methods=['POST'])
@require_auth
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
@require_auth
def restart_account(account):
    """Restart account (not available in remote mode)"""
    return jsonify({'error': 'Not available in remote mode'}), 400


@account_bp.route('/accounts/<account>/stop', methods=['POST'])
@require_auth
def stop_account(account):
    """Stop account (not available in remote mode)"""
    return jsonify({'error': 'Not available in remote mode'}), 400


@account_bp.route('/accounts/<account>/open', methods=['POST'])
@require_auth
def open_account(account):
    """Open account (not available in remote mode)"""
    return jsonify({'error': 'Not available in remote mode'}), 400


@account_bp.route('/accounts/<account>/pause', methods=['POST'])
@require_auth
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
@require_auth
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
@require_auth
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

            # ✅ FIX: Broadcast account deletion event via SSE
            try:
                from app.services.sse_service import broadcast_account_deleted
                broadcast_account_deleted(account, deleted_pairs_count)
                logger.info(f'[SSE_BROADCAST] Account deletion event sent for {account}')
            except Exception as e:
                logger.warning(f'[SSE_BROADCAST_ERROR] {e}')

            # Log summary
            if cleanup_logs:
                cleanup_summary = ', '.join(cleanup_logs)
                system_logs_service.add_log('warning', f'🗑️ [200] Account deleted: {account} (cleaned: {cleanup_summary})')
            else:
                system_logs_service.add_log('warning', f'🗑️ [200] Account deleted: {account}')

            return jsonify({
                'ok': True,
                'deleted_pairs': deleted_pairs_count,
                'deleted_history': deleted_history_count,
                'message': f'Account deleted with {deleted_pairs_count} copy pair(s) removed',
                # ✅ FIX: Return cleanup details for UI
                'cleanup': {
                    'pairs': deleted_pairs_count,
                    'history': deleted_history_count,
                    'logs': cleanup_logs
                }
            }), 200
        else:
            return jsonify({'ok': False}), 200
    except Exception as e:
        logger.exception('[DELETE_ACCOUNT_ERROR]')
        return jsonify({'ok': False, 'error': str(e)}), 500


# =================== Secret Key Management Routes ===================

@account_bp.route('/settings/secret', methods=['GET'])
@require_auth
def get_global_secret():
    """Get Global Secret Key"""
    try:
        secret = session_manager.get_global_secret()
        return jsonify({
            'secret': secret or '',
            'enabled': bool(secret)
        })
    except Exception as e:
        logger.error(f"[GET_GLOBAL_SECRET_ERROR] {e}")
        return jsonify({'error': str(e)}), 500


@account_bp.route('/settings/secret', methods=['POST'])
@require_auth
def update_global_secret():
    """Update Global Secret Key"""
    try:
        data = request.get_json() or {}
        secret = data.get('secret', '').strip()

        if session_manager.update_global_secret(secret):
            action = 'updated' if secret else 'removed'
            system_logs_service.add_log('success', f'🔐 Global secret key {action}')
            logger.info(f"[GLOBAL_SECRET] {action.capitalize()}")
            return jsonify({
                'success': True,
                'message': f'Secret key {action} successfully'
            })
        else:
            return jsonify({'error': 'Failed to update secret key'}), 500

    except Exception as e:
        logger.error(f"[UPDATE_GLOBAL_SECRET_ERROR] {e}")
        return jsonify({'error': str(e)}), 500


@account_bp.route('/accounts/<account>/secret', methods=['GET'])
def get_account_secret(account):
    """Get per-account secret (for backward compatibility)"""
    try:
        return jsonify({'secret': ''})
    except Exception as e:
        logger.error(f"[GET_ACCOUNT_SECRET_ERROR] {e}")
        return jsonify({'error': str(e)}), 500


@account_bp.route('/accounts/<account>/secret', methods=['POST'])
def update_account_secret(account):
    """Update per-account secret (for backward compatibility)"""
    try:
        return jsonify({
            'success': True,
            'message': 'Please use global secret key instead'
        })
    except Exception as e:
        logger.error(f"[UPDATE_ACCOUNT_SECRET_ERROR] {e}")
        return jsonify({'error': str(e)}), 500


# =================== Symbol Mapping Management Routes ===================

@account_bp.route('/accounts/<account>/symbols', methods=['GET'])
def get_symbol_mappings(account):
    """Get symbol mappings for account"""
    try:
        if not session_manager.account_exists(account):
            return jsonify({'error': 'Account not found'}), 404

        mappings = session_manager.get_symbol_mappings(account)

        # Convert list to dict if needed
        if isinstance(mappings, list):
            mapping_dict = {}
            for item in mappings:
                if isinstance(item, dict):
                    from_sym = item.get('from', '')
                    to_sym = item.get('to', '')
                    if from_sym and to_sym:
                        mapping_dict[from_sym] = to_sym
            return jsonify({'mappings': mapping_dict})

        return jsonify({'mappings': mappings or {}})

    except Exception as e:
        logger.error(f"[GET_SYMBOL_MAPPINGS_ERROR] {e}")
        return jsonify({'error': str(e)}), 500


@account_bp.route('/accounts/<account>/symbols', methods=['POST'])
@require_auth
def update_symbol_mappings(account):
    """Update symbol mappings"""
    try:
        if not session_manager.account_exists(account):
            return jsonify({'error': 'Account not found'}), 404

        data = request.get_json() or {}

        # Handle single add
        if 'from_symbol' in data and 'to_symbol' in data:
            from_symbol = str(data.get('from_symbol', '')).strip().upper()
            to_symbol = str(data.get('to_symbol', '')).strip().upper()

            if not from_symbol or not to_symbol:
                return jsonify({'error': 'Both symbols required'}), 400

            current_mappings = session_manager.get_symbol_mappings(account)
            if isinstance(current_mappings, dict):
                current_mappings = [{'from': k, 'to': v} for k, v in current_mappings.items()]

            # Check duplicate
            for mapping in current_mappings:
                if mapping.get('from', '').upper() == from_symbol:
                    return jsonify({'error': 'Mapping exists'}), 400

            current_mappings.append({'from': from_symbol, 'to': to_symbol})

            if session_manager.update_symbol_mappings(account, current_mappings):
                system_logs_service.add_log('success', f'✅ Mapping added: {from_symbol}→{to_symbol} ({account})')
                return jsonify({
                    'success': True,
                    'message': f'Added: {from_symbol} → {to_symbol}'
                })
            return jsonify({'error': 'Failed to add'}), 500

        # Handle bulk update
        mappings = data.get('mappings', [])
        mapping_list = []

        if isinstance(mappings, list):
            for item in mappings:
                if isinstance(item, dict):
                    from_sym = str(item.get('from', '')).strip().upper()
                    to_sym = str(item.get('to', '')).strip().upper()
                    if from_sym and to_sym:
                        mapping_list.append({'from': from_sym, 'to': to_sym})

        elif isinstance(mappings, dict):
            for from_sym, to_sym in mappings.items():
                from_sym = str(from_sym).strip().upper()
                to_sym = str(to_sym).strip().upper()
                if from_sym and to_sym:
                    mapping_list.append({'from': from_sym, 'to': to_sym})

        if session_manager.update_symbol_mappings(account, mapping_list):
            system_logs_service.add_log('success', f'🔄 Mappings updated: {account} ({len(mapping_list)} items)')
            mapping_dict = {m['from']: m['to'] for m in mapping_list}
            return jsonify({
                'success': True,
                'message': 'Mappings updated',
                'count': len(mapping_list),
                'mappings': mapping_dict
            })
        return jsonify({'error': 'Failed to update'}), 500

    except Exception as e:
        logger.error(f"[UPDATE_MAPPINGS_ERROR] {e}")
        return jsonify({'error': str(e)}), 500


@account_bp.route('/accounts/<account>/symbols/<from_symbol>', methods=['DELETE'])
@require_auth
def delete_symbol_mapping(account, from_symbol):
    """Delete symbol mapping"""
    try:
        if not session_manager.account_exists(account):
            return jsonify({'error': 'Account not found'}), 404

        from_symbol = from_symbol.upper()
        mappings = session_manager.get_symbol_mappings(account)

        if isinstance(mappings, dict):
            mappings = [{'from': k, 'to': v} for k, v in mappings.items()]

        original_count = len(mappings)
        mappings = [m for m in mappings if m.get('from', '').upper() != from_symbol]

        if len(mappings) == original_count:
            return jsonify({'error': 'Not found'}), 404

        if session_manager.update_symbol_mappings(account, mappings):
            system_logs_service.add_log('success', f'🗑️ Mapping deleted: {from_symbol} ({account})')
            return jsonify({
                'success': True,
                'remaining_count': len(mappings)
            })
        return jsonify({'error': 'Failed to delete'}), 500

    except Exception as e:
        logger.error(f"[DELETE_MAPPING_ERROR] {e}")
        return jsonify({'error': str(e)}), 500


@account_bp.route('/accounts/symbols/overview', methods=['GET'])
@require_auth
def get_all_symbol_mappings():
    """Get all symbol mappings overview"""
    try:
        accounts = session_manager.get_all_accounts()
        overview = {}

        for acc in accounts:
            account_num = acc['account']
            mappings = session_manager.get_symbol_mappings(account_num)

            if isinstance(mappings, list) and len(mappings) > 0:
                mapping_dict = {}
                for item in mappings:
                    if isinstance(item, dict):
                        from_sym = item.get('from', '')
                        to_sym = item.get('to', '')
                        if from_sym and to_sym:
                            mapping_dict[from_sym] = to_sym
                mappings = mapping_dict

            if mappings:
                overview[account_num] = {
                    'nickname': acc.get('nickname', ''),
                    'mappings': mappings
                }

        return jsonify({
            'success': True,
            'data': overview
        })

    except Exception as e:
        logger.error(f"[GET_ALL_MAPPINGS_ERROR] {e}")
        return jsonify({'error': str(e)}), 500


# =================== Webhook Account Allowlist Management Routes ===================

@account_bp.route('/webhook-accounts', methods=['GET'])
@require_auth
def list_webhook_accounts():
    """Get list of webhook allowed accounts"""
    return jsonify({"accounts": account_allowlist_service.get_webhook_allowlist()})


@account_bp.route('/webhook-accounts', methods=['POST'])
@require_auth
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
@require_auth
def delete_webhook_account(account):
    """Remove account from webhook allowlist"""
    if account_allowlist_service.delete_webhook_account(account):
        system_logs_service.add_log('warning', f'🗑️ [200] Webhook account removed: {account}')
        return jsonify({"ok": True})
    else:
        return jsonify({"error": "Failed to delete webhook account"}), 500


# =================== Symbol Mapping API Routes (New Endpoints) ===================

@account_bp.route('/api/symbol-mappings/<account>', methods=['GET'])
@session_login_required
def get_symbol_mappings_api(account):
    """
    Get symbol mappings for account (API endpoint alias)

    This is an alias for /accounts/<account>/symbols
    to maintain compatibility with frontend
    """
    try:
        if not session_manager.account_exists(account):
            return jsonify({'error': 'Account not found'}), 404

        mappings = session_manager.get_symbol_mappings(account)

        # Convert list to dict if needed (frontend expects dict format)
        if isinstance(mappings, list):
            mapping_dict = {}
            for item in mappings:
                if isinstance(item, dict):
                    from_sym = item.get('from', '')
                    to_sym = item.get('to', '')
                    if from_sym and to_sym:
                        mapping_dict[from_sym] = to_sym
            mappings = mapping_dict

        return jsonify({
            'success': True,
            'account': account,
            'mappings': mappings or {},
            'count': len(mappings) if mappings else 0
        }), 200

    except Exception as e:
        logger.error(f"[GET_SYMBOL_MAPPINGS_API_ERROR] {e}")
        return jsonify({'error': str(e)}), 500


@account_bp.route('/api/symbol-mappings/<account>', methods=['POST'])
@session_login_required
def add_symbol_mapping_api(account):
    """
    Add a single symbol mapping (API endpoint)
    """
    try:
        data = request.get_json() or {}
        from_symbol = str(data.get('from', '')).strip().upper()
        to_symbol = str(data.get('to', '')).strip().upper()

        if not from_symbol or not to_symbol:
            return jsonify({'error': 'Both from and to symbols are required'}), 400

        if not session_manager.account_exists(account):
            return jsonify({'error': 'Account not found'}), 404

        # Get existing mappings
        mappings = session_manager.get_symbol_mappings(account)
        if not isinstance(mappings, list):
            mappings = []

        # Check for duplicate
        for mapping in mappings:
            if isinstance(mapping, dict) and mapping.get('from', '').upper() == from_symbol:
                return jsonify({'error': f'Mapping for {from_symbol} already exists'}), 400

        # Add new mapping
        new_mapping = {'from': from_symbol, 'to': to_symbol}
        mappings.append(new_mapping)

        # Save
        if session_manager.update_symbol_mappings(account, mappings):
            logger.info(f"[SYMBOL_MAPPING] Added {from_symbol} → {to_symbol} for account {account}")
            system_logs_service.add_log('success',
                f'✅ [201] Symbol mapping added: {from_symbol} → {to_symbol} (Account: {account})')

            return jsonify({
                'success': True,
                'message': f'Mapping added: {from_symbol} → {to_symbol}',
                'mapping': new_mapping
            }), 201
        else:
            return jsonify({'error': 'Failed to add symbol mapping'}), 500

    except Exception as e:
        logger.error(f"[ADD_SYMBOL_MAPPING_API_ERROR] {e}")
        return jsonify({'error': str(e)}), 500


@account_bp.route('/api/symbol-mappings/<account>/<from_symbol>', methods=['DELETE'])
@session_login_required
def delete_symbol_mapping_api(account, from_symbol):
    """
    Delete a symbol mapping (API endpoint)
    """
    try:
        from_symbol = from_symbol.upper()

        if not session_manager.account_exists(account):
            return jsonify({'error': 'Account not found'}), 404

        # Get existing mappings
        mappings = session_manager.get_symbol_mappings(account)
        if not isinstance(mappings, list):
            mappings = []

        # Find and remove mapping
        original_count = len(mappings)
        mappings = [m for m in mappings if isinstance(m, dict) and m.get('from', '').upper() != from_symbol]

        if len(mappings) == original_count:
            return jsonify({'error': f'Mapping for {from_symbol} not found'}), 404

        # Save
        if session_manager.update_symbol_mappings(account, mappings):
            logger.info(f"[SYMBOL_MAPPING] Deleted mapping for {from_symbol} (Account: {account})")
            system_logs_service.add_log('warning',
                f'🗑️ [200] Symbol mapping deleted: {from_symbol} (Account: {account})')

            return jsonify({
                'success': True,
                'message': f'Mapping for {from_symbol} deleted'
            }), 200
        else:
            return jsonify({'error': 'Failed to delete symbol mapping'}), 500

    except Exception as e:
        logger.error(f"[DELETE_SYMBOL_MAPPING_API_ERROR] {e}")
        return jsonify({'error': str(e)}), 500


