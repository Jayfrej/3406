"""
Copy Trading Routes - Flask Blueprint

All copy trading HTTP endpoints:
- Pair Management (CRUD operations)
- Master/Slave Account Management
- Copy Trade Signal Endpoint
- History Management
- SSE Events
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app

logger = logging.getLogger(__name__)

# Create Blueprint
copy_trading_bp = Blueprint('copy_trading', __name__)


# =================== Copy Trading Pair Management ===================

@copy_trading_bp.get('/api/pairs')
def list_pairs():
    """List all copy trading pairs"""
    from app.copy_trading.copy_manager import CopyManager
    from app.core.email import EmailHandler

    email_handler = EmailHandler()
    copy_manager = CopyManager(email_handler=email_handler)

    try:
        # Support both list_pairs() and get_all_pairs()
        if hasattr(copy_manager, 'list_pairs'):
            pairs = copy_manager.list_pairs()
        else:
            pairs = copy_manager.get_all_pairs()
        return jsonify({'pairs': pairs}), 200
    except Exception as e:
        current_app.logger.exception('[PAIRS_LIST_ERROR]')
        return jsonify({'error': str(e)}), 500


@copy_trading_bp.post('/api/pairs')
def create_copy_pair():
    """Create new copy trading pair"""
    from app.copy_trading.copy_manager import CopyManager
    from app.services.accounts import SessionManager
    from app.core.email import EmailHandler

    email_handler = EmailHandler()
    copy_manager = CopyManager(email_handler=email_handler)
    session_manager = SessionManager()

    try:
        data = request.get_json() or {}

        master = str(data.get('master_account', '')).strip()
        slave = str(data.get('slave_account', '')).strip()

        if not master or not slave:
            return jsonify({'error': 'Master and slave accounts are required'}), 400

        if master == slave:
            # Log to system if available
            try:
                from server import add_system_log
                add_system_log('error', f'❌ [400] Copy pair creation failed - Master and slave cannot be the same ({master})')
            except:
                pass
            return jsonify({'error': 'Master and slave accounts must be different'}), 400

        if not session_manager.account_exists(master):
            try:
                from server import add_system_log
                add_system_log('error', f'❌ [404] Copy pair creation failed - Master account {master} not found')
            except:
                pass
            return jsonify({'error': f'Master account {master} not found'}), 404

        if not session_manager.account_exists(slave):
            try:
                from server import add_system_log
                add_system_log('error', f'❌ [404] Copy pair creation failed - Slave account {slave} not found')
            except:
                pass
            return jsonify({'error': f'Slave account {slave} not found'}), 404

        master_nickname = str(data.get('master_nickname', '')).strip()
        slave_nickname = str(data.get('slave_nickname', '')).strip()
        settings = data.get('settings', {})

        pair = copy_manager.create_pair(
            master_account=master,
            slave_account=slave,
            settings=settings,
            master_nickname=master_nickname,
            slave_nickname=slave_nickname
        )

        logger.info(f"[API] Created copy pair: {master} -> {slave}")

        try:
            from server import add_system_log
            add_system_log('success', f'✅ [201] Copy pair created: {master} → {slave} ({master_nickname} → {slave_nickname})')
        except:
            pass

        return jsonify({'success': True, 'pair': pair}), 201

    except Exception as e:
        logger.error(f"[API] Create pair error: {e}")
        return jsonify({'error': str(e)}), 500


@copy_trading_bp.put('/api/pairs/<pair_id>')
def update_copy_pair(pair_id):
    """Update copy trading pair settings"""
    from app.copy_trading.copy_manager import CopyManager
    from app.core.email import EmailHandler

    email_handler = EmailHandler()
    copy_manager = CopyManager(email_handler=email_handler)

    try:
        data = request.get_json() or {}
        success = copy_manager.update_pair(pair_id, data)

        if success:
            pair = copy_manager.get_pair_by_id(pair_id)
            master = pair.get('master_account', '')
            slave = pair.get('slave_account', '')

            try:
                from server import add_system_log
                add_system_log('info', f'✏️ [200] Copy pair updated: {master} → {slave}')
            except:
                pass

            return jsonify({'success': True, 'pair': pair})
        else:
            try:
                from server import add_system_log
                add_system_log('warning', f'⚠️ [404] Copy pair update failed - Pair {pair_id} not found')
            except:
                pass
            return jsonify({'error': 'Pair not found'}), 404

    except Exception as e:
        logger.error(f"[API] Update pair error: {e}")
        return jsonify({'error': str(e)}), 500


@copy_trading_bp.delete('/api/pairs/<pair_id>')
def delete_pair(pair_id):
    """Delete copy trading pair"""
    from app.copy_trading.copy_manager import CopyManager
    from app.core.email import EmailHandler

    email_handler = EmailHandler()
    copy_manager = CopyManager(email_handler=email_handler)

    try:
        deleted = copy_manager.delete_pair(pair_id)
        if not deleted:
            current_app.logger.warning(f'[PAIR_DELETE_NOT_FOUND] {pair_id}')
            try:
                from server import add_system_log
                add_system_log('warning', f'⚠️ [404] Copy pair deletion failed - Pair {pair_id} not found')
            except:
                pass
            return jsonify({'ok': False, 'error': 'Pair not found'}), 404

        current_app.logger.info(f'[PAIR_DELETE] {pair_id}')
        try:
            from server import add_system_log
            add_system_log('warning', f'🗑️ [200] Copy pair deleted: {pair_id}')
        except:
            pass

        return jsonify({'ok': True}), 200
    except Exception as e:
        current_app.logger.exception('[PAIR_DELETE_ERROR]')
        return jsonify({'ok': False, 'error': str(e)}), 500


@copy_trading_bp.post('/api/pairs/<pair_id>/toggle')
def toggle_copy_pair(pair_id):
    """Toggle copy trading pair active/inactive"""
    from app.copy_trading.copy_manager import CopyManager
    from app.core.email import EmailHandler

    email_handler = EmailHandler()
    copy_manager = CopyManager(email_handler=email_handler)

    try:
        new_status = copy_manager.toggle_pair_status(pair_id)

        if new_status:
            status_emoji = "✅" if new_status == "active" else "⏸️"
            status_text = "enabled" if new_status == "active" else "disabled"

            try:
                from server import add_system_log
                add_system_log('info', f'{status_emoji} [200] Copy pair {status_text}: {pair_id}')
            except:
                pass

            return jsonify({'success': True, 'status': new_status})
        else:
            try:
                from server import add_system_log
                add_system_log('warning', f'⚠️ [404] Copy pair toggle failed - Pair {pair_id} not found')
            except:
                pass
            return jsonify({'error': 'Pair not found'}), 404

    except Exception as e:
        logger.error(f"[API] Toggle pair error: {e}")
        return jsonify({'error': str(e)}), 500


@copy_trading_bp.post('/api/pairs/<pair_id>/add-master')
def add_master_to_pair(pair_id):
    """
    Add Master Account to existing pair group
    Uses same API key as existing pair
    """
    from app.copy_trading.copy_manager import CopyManager
    from app.services.accounts import SessionManager
    from app.core.email import EmailHandler

    email_handler = EmailHandler()
    copy_manager = CopyManager(email_handler=email_handler)
    session_manager = SessionManager()

    try:
        data = request.get_json() or {}
        master_account = str(data.get('master_account', '')).strip()

        if not master_account:
            try:
                from server import add_system_log
                add_system_log('error', '❌ [400] Add master failed - Account number required')
            except:
                pass
            return jsonify({'error': 'Master account is required'}), 400

        # Check if account exists
        if not session_manager.account_exists(master_account):
            try:
                from server import add_system_log
                add_system_log('error', f'❌ [404] Add master failed - Account {master_account} not found')
            except:
                pass
            return jsonify({'error': f'Master account {master_account} not found'}), 404

        # Get existing pair
        pair = copy_manager.get_pair_by_id(pair_id)
        if not pair:
            try:
                from server import add_system_log
                add_system_log('error', f'❌ [404] Add master failed - Pair {pair_id} not found')
            except:
                pass
            return jsonify({'error': 'Pair not found'}), 404

        # Use API key from existing pair
        api_key = pair.get('api_key') or pair.get('apiKey')

        # Get all pairs with same API key
        existing_pairs = [p for p in copy_manager.pairs
                         if (p.get('api_key') or p.get('apiKey')) == api_key]

        if not existing_pairs:
            try:
                from server import add_system_log
                add_system_log('error', f'❌ [404] Add master failed - No existing pairs with API key')
            except:
                pass
            return jsonify({'error': 'No existing pairs found with this API key'}), 404

        # Use first slave
        first_slave = existing_pairs[0].get('slave_account')
        settings = existing_pairs[0].get('settings', {})

        # Check if pair already exists
        for p in copy_manager.pairs:
            if (p.get('master_account') == master_account and
                p.get('slave_account') == first_slave and
                (p.get('api_key') or p.get('apiKey')) == api_key):
                try:
                    from server import add_system_log
                    add_system_log('warning', f'⚠️ [400] Add master failed - Pair already exists')
                except:
                    pass
                return jsonify({'error': 'This master-slave pair already exists'}), 400

        # Create new pair with same API key
        new_pair = {
            'id': f"{master_account}_{first_slave}_{int(datetime.now().timestamp())}",
            'master_account': master_account,
            'slave_account': first_slave,
            'api_key': api_key,
            'settings': settings.copy(),
            'status': 'active',
            'created': datetime.now().isoformat(),
            'updated': datetime.now().isoformat()
        }

        # Add new pair
        copy_manager.pairs.append(new_pair)
        copy_manager._save_pairs()

        # Update API key mapping
        if hasattr(copy_manager, 'api_keys'):
            if api_key not in copy_manager.api_keys:
                copy_manager.api_keys[api_key] = []
            if isinstance(copy_manager.api_keys[api_key], list):
                copy_manager.api_keys[api_key].append(new_pair['id'])
            else:
                # Convert string to list
                old_id = copy_manager.api_keys[api_key]
                copy_manager.api_keys[api_key] = [old_id, new_pair['id']]
            if hasattr(copy_manager, '_save_api_keys'):
                copy_manager._save_api_keys()

        logger.info(f"[API] Added master {master_account} to pair group with API key {api_key[:8]}...")

        try:
            from server import add_system_log
            add_system_log('success', f'✅ [201] Master {master_account} added to pair {pair_id}')
        except:
            pass

        return jsonify({'success': True, 'pair': new_pair}), 201

    except Exception as e:
        logger.error(f"[API] Add master to pair error: {e}")
        try:
            from server import add_system_log
            add_system_log('error', f'❌ [500] Add master failed: {str(e)}')
        except:
            pass
        return jsonify({'error': str(e)}), 500


@copy_trading_bp.post('/api/pairs/<pair_id>/add-slave')
def add_slave_to_pair(pair_id):
    """
    Add Slave Account to existing pair group
    Uses same API key with custom settings
    """
    from app.copy_trading.copy_manager import CopyManager
    from app.services.accounts import SessionManager
    from app.core.email import EmailHandler

    email_handler = EmailHandler()
    copy_manager = CopyManager(email_handler=email_handler)
    session_manager = SessionManager()

    try:
        data = request.get_json() or {}
        slave_account = str(data.get('slave_account', '')).strip()
        settings = data.get('settings', {})

        if not slave_account:
            try:
                from server import add_system_log
                add_system_log('error', '❌ [400] Add slave failed - Account number required')
            except:
                pass
            return jsonify({'error': 'Slave account is required'}), 400

        # Check if account exists
        if not session_manager.account_exists(slave_account):
            try:
                from server import add_system_log
                add_system_log('error', f'❌ [404] Add slave failed - Account {slave_account} not found')
            except:
                pass
            return jsonify({'error': f'Slave account {slave_account} not found'}), 404

        # Get existing pair
        pair = copy_manager.get_pair_by_id(pair_id)
        if not pair:
            try:
                from server import add_system_log
                add_system_log('error', f'❌ [404] Add slave failed - Pair {pair_id} not found')
            except:
                pass
            return jsonify({'error': 'Pair not found'}), 404

        # Use API key and master from existing pair
        api_key = pair.get('api_key') or pair.get('apiKey')
        master_account = pair.get('master_account')

        # Check if pair already exists
        for p in copy_manager.pairs:
            if (p.get('master_account') == master_account and
                p.get('slave_account') == slave_account and
                (p.get('api_key') or p.get('apiKey')) == api_key):
                try:
                    from server import add_system_log
                    add_system_log('warning', f'⚠️ [400] Add slave failed - Pair already exists')
                except:
                    pass
                return jsonify({'error': 'This master-slave pair already exists'}), 400

        # Create new pair for new slave
        new_pair = {
            'id': f"{master_account}_{slave_account}_{int(datetime.now().timestamp())}",
            'master_account': master_account,
            'slave_account': slave_account,
            'api_key': api_key,
            'settings': {
                'auto_map_symbol': settings.get('auto_map_symbol', True),
                'auto_map_volume': settings.get('auto_map_volume', True),
                'copy_psl': settings.get('copy_psl', True),
                'volume_mode': settings.get('volume_mode', 'multiply'),
                'multiplier': float(settings.get('multiplier', 2))
            },
            'status': 'active',
            'created': datetime.now().isoformat(),
            'updated': datetime.now().isoformat()
        }

        # Add new pair
        copy_manager.pairs.append(new_pair)
        copy_manager._save_pairs()

        # Update API key mapping
        if hasattr(copy_manager, 'api_keys'):
            if api_key not in copy_manager.api_keys:
                copy_manager.api_keys[api_key] = []
            if isinstance(copy_manager.api_keys[api_key], list):
                copy_manager.api_keys[api_key].append(new_pair['id'])
            else:
                # Convert string to list
                old_id = copy_manager.api_keys[api_key]
                copy_manager.api_keys[api_key] = [old_id, new_pair['id']]
            if hasattr(copy_manager, '_save_api_keys'):
                copy_manager._save_api_keys()

        logger.info(f"[API] Added slave {slave_account} to pair group with API key {api_key[:8]}...")

        try:
            from server import add_system_log
            add_system_log('success', f'✅ [201] Slave {slave_account} added to pair {pair_id}')
        except:
            pass

        return jsonify({'success': True, 'pair': new_pair}), 201

    except Exception as e:
        logger.error(f"[API] Add slave to pair error: {e}")
        try:
            from server import add_system_log
            add_system_log('error', f'❌ [500] Add slave failed: {str(e)}')
        except:
            pass
        return jsonify({'error': str(e)}), 500


# =================== Master/Slave Account Management ===================

@copy_trading_bp.get('/api/copy/master-accounts')
def get_master_accounts():
    """Get all master accounts"""
    try:
        master_file = Path('data/master_accounts.json')
        if master_file.exists():
            with open(master_file, 'r', encoding='utf-8') as f:
                masters = json.load(f)
        else:
            masters = []

        return jsonify({'accounts': masters})

    except Exception as e:
        logger.error(f"[API] Get master accounts error: {e}")
        return jsonify({'error': str(e)}), 500


@copy_trading_bp.post('/api/copy/master-accounts')
def add_master_account():
    """Add master account"""
    from app.services.accounts import SessionManager

    session_manager = SessionManager()

    try:
        data = request.get_json() or {}
        account = str(data.get('account', '')).strip()
        nickname = str(data.get('nickname', '')).strip()

        if not account:
            return jsonify({'error': 'Account number is required'}), 400

        # Create account in Account Management if doesn't exist
        if not session_manager.account_exists(account):
            if not session_manager.add_remote_account(account, nickname):
                return jsonify({'error': f'Failed to create account {account}'}), 500
            logger.info(f"[API] Created new account in Account Management: {account}")

        # Load existing masters
        master_file = Path('data/master_accounts.json')
        if master_file.exists():
            with open(master_file, 'r', encoding='utf-8') as f:
                masters = json.load(f)
        else:
            masters = []

        # Check if already exists
        if any(m.get('account') == account for m in masters):
            return jsonify({'error': 'Master account already exists'}), 400

        # Add new master
        new_master = {
            'id': str(int(datetime.now().timestamp() * 1000)),
            'account': account,
            'nickname': nickname
        }

        masters.append(new_master)

        # Save to file
        master_file.parent.mkdir(parents=True, exist_ok=True)
        with open(master_file, 'w', encoding='utf-8') as f:
            json.dump(masters, f, indent=2, ensure_ascii=False)

        logger.info(f"[API] Added master account: {account}")

        try:
            from server import add_system_log
            add_system_log('success', f'✅ [201] Master account {account} added')
        except:
            pass

        return jsonify({'success': True, 'account': new_master}), 201

    except Exception as e:
        logger.error(f"[API] Add master account error: {e}")
        try:
            from server import add_system_log
            add_system_log('error', f'❌ [500] Add master failed: {str(e)}')
        except:
            pass
        return jsonify({'error': str(e)}), 500


@copy_trading_bp.delete('/api/copy/master-accounts/<account_id>')
def delete_master_account(account_id):
    """Delete master account"""
    try:
        master_file = Path('data/master_accounts.json')
        if not master_file.exists():
            return jsonify({'error': 'No master accounts found'}), 404

        with open(master_file, 'r', encoding='utf-8') as f:
            masters = json.load(f)

        # Find and remove account
        original_count = len(masters)
        masters = [m for m in masters if m.get('id') != account_id and m.get('account') != account_id]

        if len(masters) == original_count:
            return jsonify({'error': 'Master account not found'}), 404

        # Save
        with open(master_file, 'w', encoding='utf-8') as f:
            json.dump(masters, f, indent=2, ensure_ascii=False)

        logger.info(f"[API] Deleted master account: {account_id}")

        try:
            from server import add_system_log
            add_system_log('success', f'✅ [200] Master account {account_id} deleted')
        except:
            pass

        return jsonify({'success': True})

    except Exception as e:
        logger.error(f"[API] Delete master account error: {e}")
        return jsonify({'error': str(e)}), 500


@copy_trading_bp.get('/api/copy/slave-accounts')
def get_slave_accounts():
    """Get all slave accounts"""
    try:
        slave_file = Path('data/slave_accounts.json')
        if slave_file.exists():
            with open(slave_file, 'r', encoding='utf-8') as f:
                slaves = json.load(f)
        else:
            slaves = []

        return jsonify({'accounts': slaves})

    except Exception as e:
        logger.error(f"[API] Get slave accounts error: {e}")
        return jsonify({'error': str(e)}), 500


@copy_trading_bp.post('/api/copy/slave-accounts')
def add_slave_account():
    """Add slave account"""
    from app.services.accounts import SessionManager

    session_manager = SessionManager()

    try:
        data = request.get_json() or {}
        account = str(data.get('account', '')).strip()
        nickname = str(data.get('nickname', '')).strip()

        if not account:
            return jsonify({'error': 'Account number is required'}), 400

        # Create account in Account Management if doesn't exist
        if not session_manager.account_exists(account):
            if not session_manager.add_remote_account(account, nickname):
                return jsonify({'error': f'Failed to create account {account}'}), 500
            logger.info(f"[API] Created new account in Account Management: {account}")

        # Load existing slaves
        slave_file = Path('data/slave_accounts.json')
        if slave_file.exists():
            with open(slave_file, 'r', encoding='utf-8') as f:
                slaves = json.load(f)
        else:
            slaves = []

        # Check if already exists
        if any(s.get('account') == account for s in slaves):
            return jsonify({'error': 'Slave account already exists'}), 400

        # Add new slave
        new_slave = {
            'id': str(int(datetime.now().timestamp() * 1000)),
            'account': account,
            'nickname': nickname
        }

        slaves.append(new_slave)

        # Save to file
        slave_file.parent.mkdir(parents=True, exist_ok=True)
        with open(slave_file, 'w', encoding='utf-8') as f:
            json.dump(slaves, f, indent=2, ensure_ascii=False)

        logger.info(f"[API] Added slave account: {account}")

        try:
            from server import add_system_log
            add_system_log('success', f'✅ [201] Slave account {account} added')
        except:
            pass

        return jsonify({'success': True, 'account': new_slave}), 201

    except Exception as e:
        logger.error(f"[API] Add slave account error: {e}")
        try:
            from server import add_system_log
            add_system_log('error', f'❌ [500] Add slave failed: {str(e)}')
        except:
            pass
        return jsonify({'error': str(e)}), 500


@copy_trading_bp.delete('/api/copy/slave-accounts/<account_id>')
def delete_slave_account(account_id):
    """Delete slave account"""
    try:
        slave_file = Path('data/slave_accounts.json')
        if not slave_file.exists():
            return jsonify({'error': 'No slave accounts found'}), 404

        with open(slave_file, 'r', encoding='utf-8') as f:
            slaves = json.load(f)

        # Find and remove account
        original_count = len(slaves)
        slaves = [s for s in slaves if s.get('id') != account_id and s.get('account') != account_id]

        if len(slaves) == original_count:
            return jsonify({'error': 'Slave account not found'}), 404

        # Save
        with open(slave_file, 'w', encoding='utf-8') as f:
            json.dump(slaves, f, indent=2, ensure_ascii=False)

        logger.info(f"[API] Deleted slave account: {account_id}")

        try:
            from server import add_system_log
            add_system_log('success', f'✅ [200] Slave account {account_id} deleted')
        except:
            pass

        return jsonify({'success': True})

    except Exception as e:
        logger.error(f"[API] Delete slave account error: {e}")
        return jsonify({'error': str(e)}), 500


# =================== Copy Trade Signal Endpoint ===================

@copy_trading_bp.post('/api/copy/trade')
def copy_trade_endpoint():
    """
    Receive trading signal from Master EA (Copy Trading)

    Version 2.0: Supports Multiple Pairs per API Key
    Uses copy_handler.process_master_signal() to handle all logic
    """
    from app.copy_trading.copy_handler import CopyHandler
    from app.copy_trading.copy_manager import CopyManager
    from app.copy_trading.copy_executor import CopyExecutor
    from app.copy_trading.copy_history import CopyHistory
    from app.services.accounts import SessionManager
    from app.services.symbols import SymbolMapper
    from app.services.broker import BrokerDataManager
    from app.services.balance import balance_manager
    from app.core.email import EmailHandler

    # Initialize components
    session_manager = SessionManager()
    symbol_mapper = SymbolMapper()
    broker_manager = BrokerDataManager(data_dir='data')
    email_handler = EmailHandler()
    copy_manager = CopyManager(email_handler=email_handler)
    copy_history = CopyHistory()
    copy_executor = CopyExecutor(session_manager, copy_history)
    copy_handler = CopyHandler(copy_manager, symbol_mapper, copy_executor, session_manager, broker_manager, balance_manager, email_handler)

    try:
        # 1) Log raw payload
        raw_data = request.get_data(as_text=True)
        logger.info(f"[COPY_TRADE] Raw request data: {raw_data}")

        content_type = request.headers.get('Content-Type', '')
        logger.info(f"[COPY_TRADE] Content-Type: {content_type}")

        # 2) Parse JSON safely
        try:
            data = request.get_json(force=True)
        except Exception as json_err:
            logger.error(f"[COPY_TRADE] JSON Parse Error: {json_err}")
            return jsonify({'error': 'Invalid JSON'}), 400

        logger.info(f"[COPY_TRADE] Parsed data: {json.dumps(data)}")

        # 3) Log event summary
        action = data.get('event', 'UNKNOWN')
        symbol = data.get('symbol', '-')
        account = data.get('account', '-')

        try:
            from server import add_system_log
            add_system_log('info', f'📡 [200] Copy signal received: {action} {symbol} from {account}')
        except:
            pass

        # 4) Basic validation
        api_key = str(data.get('api_key', '')).strip()
        if not api_key:
            try:
                from server import add_system_log
                add_system_log('error', '❌ [400] Copy trade failed - API key missing')
            except:
                pass
            return jsonify({'error': 'api_key is required'}), 400

        # 5) Use copy_handler to process signal
        result = copy_handler.process_master_signal(api_key, data)

        if not result or not result.get('success'):
            error_msg = (result or {}).get('error', 'Processing failed')
            try:
                from server import add_system_log
                add_system_log('error', f'❌ [500] Copy trade failed: {error_msg}')
            except:
                pass
            return jsonify({'error': error_msg}), 500

        # 6) Success!
        master_account = data.get('account', '-')
        symbol = data.get('symbol', '-')
        volume = data.get('volume', '-')

        try:
            from server import add_system_log
            add_system_log(
                'success',
                f'✅ [200] Copy trade executed: {master_account} → Slave ({action} {symbol} Vol:{volume})'
            )
        except:
            pass

        return jsonify({
            'success': True,
            'message': 'Copy trade executed successfully'
        }), 200

    except Exception as e:
        logger.error(f"[COPY_TRADE_ERROR] {e}", exc_info=True)
        try:
            from server import add_system_log
            add_system_log('error', f'❌ [500] Copy trade error: {str(e)[:80]}')
        except:
            pass
        return jsonify({'error': str(e)}), 500


# =================== Copy Trading History ===================

@copy_trading_bp.get('/api/copy/history')
def get_copy_history():
    """Get copy trading history"""
    from app.copy_trading.copy_history import CopyHistory

    copy_history = CopyHistory()

    try:
        limit = int(request.args.get('limit', 100))
        status = request.args.get('status')

        limit = max(1, min(limit, 1000))

        history = copy_history.get_history(limit=limit, status=status)

        return jsonify({'history': history, 'count': len(history)})

    except Exception as e:
        logger.error(f"[API] Get copy history error: {e}")
        return jsonify({'error': str(e)}), 500


@copy_trading_bp.post('/api/copy/history/clear')
def clear_copy_history():
    """Clear all copy trading history"""
    from app.copy_trading.copy_history import CopyHistory

    copy_history = CopyHistory()

    try:
        confirm = request.args.get('confirm')
        if confirm != '1':
            try:
                from server import add_system_log
                add_system_log('warning', '⚠️ [400] Clear history failed - Missing confirmation')
            except:
                pass
            return jsonify({'error': 'Missing confirm=1'}), 400

        success = copy_history.clear_history()

        if success:
            try:
                from server import add_system_log
                add_system_log('warning', '🗑️ [200] Copy history cleared')
            except:
                pass
            return jsonify({'success': True})
        else:
            try:
                from server import add_system_log
                add_system_log('error', '❌ [500] Failed to clear copy history')
            except:
                pass
            return jsonify({'error': 'Failed to clear history'}), 500

    except Exception as e:
        logger.error(f"[API] Clear copy history error: {e}")
        return jsonify({'error': str(e)}), 500


# Legacy endpoint for backward compatibility
@copy_trading_bp.post('/copy-history/clear')
def clear_copy_history_legacy():
    """Backward-compat: Support old /copy-history/clear endpoint"""
    try:
        from app.copy_trading.copy_history import CopyHistory
        copy_history = CopyHistory()

        confirm = request.args.get('confirm')
        if confirm != '1':
            try:
                from server import add_system_log
                add_system_log('warning', '⚠️ [400] Clear history failed - Missing confirmation')
            except:
                pass
            return jsonify({'error': 'Missing confirm=1'}), 400

        success = copy_history.clear_history()
        if success:
            try:
                from server import add_system_log
                add_system_log('warning', '🗑️ [200] Copy history cleared')
            except:
                pass
            return jsonify({'success': True})
        else:
            try:
                from server import add_system_log
                add_system_log('error', '❌ [500] Failed to clear copy history')
            except:
                pass
            return jsonify({'error': 'Failed to clear history'}), 500
    except Exception as e:
        logger.error(f"[API] Legacy clear copy history error: {e}")
        return jsonify({'error': str(e)}), 500

