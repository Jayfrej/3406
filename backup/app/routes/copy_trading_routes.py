"""
Copy Trading Routes
Handles all copy trading pair management, master/slave accounts, and copy signal endpoints
"""
import json
import logging
import time
import queue
from datetime import datetime
from pathlib import Path
from flask import Blueprint, request, jsonify, Response, stream_with_context
from app.middleware.auth import require_auth

logger = logging.getLogger(__name__)

# Create blueprint
copy_trading_bp = Blueprint('copy_trading', __name__)

# These will be injected by the app factory
copy_manager = None
copy_history = None
copy_executor = None
copy_handler = None
session_manager = None
system_logs_service = None
limiter = None


def init_copy_trading_routes(cm, ch, ce, chand, sm, sls, lim):
    """
    Initialize copy trading routes with dependencies

    Args:
        cm: CopyManager instance
        ch: CopyHistory instance
        ce: CopyExecutor instance
        chand: CopyHandler instance
        sm: SessionManager instance
        sls: SystemLogsService instance
        lim: Limiter instance
    """
    global copy_manager, copy_history, copy_executor, copy_handler
    global session_manager, system_logs_service, limiter

    copy_manager = cm
    copy_history = ch
    copy_executor = ce
    copy_handler = chand
    session_manager = sm
    system_logs_service = sls
    limiter = lim


# =================== Copy Pairs Management ===================

@copy_trading_bp.route('/api/pairs', methods=['GET'])
@require_auth
def list_pairs():
    """ดึงรายการ Copy Pairs ทั้งหมด (ใช้ตอนรีเฟรชหน้า)"""
    try:
        # รองรับทั้ง list_pairs() และ get_all_pairs()
        if hasattr(copy_manager, 'list_pairs'):
            pairs = copy_manager.list_pairs()
        else:
            pairs = copy_manager.get_all_pairs()
        return jsonify({'pairs': pairs}), 200
    except Exception as e:
        logger.exception('[PAIRS_LIST_ERROR]')
        return jsonify({'error': str(e)}), 500


@copy_trading_bp.route('/api/pairs', methods=['POST'])
@require_auth
def create_copy_pair():
    """สร้าง Copy Pair ใหม่"""
    try:
        data = request.get_json() or {}

        master = str(data.get('master_account', '')).strip()
        slave = str(data.get('slave_account', '')).strip()

        if not master or not slave:
            return jsonify({'error': 'Master and slave accounts are required'}), 400

        if master == slave:
            system_logs_service.add_log('error', f'❌ [400] Copy pair creation failed - Master and slave cannot be the same ({master})')
            return jsonify({'error': 'Master and slave accounts must be different'}), 400

        if not session_manager.account_exists(master):
            system_logs_service.add_log('error', f'❌ [404] Copy pair creation failed - Master account {master} not found')
            return jsonify({'error': f'Master account {master} not found'}), 404

        if not session_manager.account_exists(slave):
            system_logs_service.add_log('error', f'❌ [404] Copy pair creation failed - Slave account {slave} not found')
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
        system_logs_service.add_log('success', f'✅ [201] Copy pair created: {master} → {slave} ({master_nickname} → {slave_nickname})')
        return jsonify({'success': True, 'pair': pair}), 201

    except Exception as e:
        logger.error(f"[API] Create pair error: {e}")
        return jsonify({'error': str(e)}), 500


@copy_trading_bp.route('/api/pairs/<pair_id>', methods=['PUT'])
@require_auth
def update_copy_pair(pair_id):
    """อัพเดต Copy Pair"""
    try:
        data = request.get_json() or {}
        success = copy_manager.update_pair(pair_id, data)

        if success:
            pair = copy_manager.get_pair_by_id(pair_id)
            master = pair.get('master_account', '')
            slave = pair.get('slave_account', '')
            system_logs_service.add_log('info', f'✏️ [200] Copy pair updated: {master} → {slave}')
            return jsonify({'success': True, 'pair': pair})
        else:
            system_logs_service.add_log('warning', f'⚠️ [404] Copy pair update failed - Pair {pair_id} not found')
            return jsonify({'error': 'Pair not found'}), 404

    except Exception as e:
        logger.error(f"[API] Update pair error: {e}")
        return jsonify({'error': str(e)}), 500


@copy_trading_bp.route('/api/pairs/<pair_id>', methods=['DELETE'])
@require_auth
def delete_pair(pair_id):
    """ลบ Copy Pair + log + save"""
    try:
        deleted = copy_manager.delete_pair(pair_id)
        if not deleted:
            logger.warning(f'[PAIR_DELETE_NOT_FOUND] {pair_id}')
            system_logs_service.add_log('warning', f'⚠️ [404] Copy pair deletion failed - Pair {pair_id} not found')
            return jsonify({'ok': False, 'error': 'Pair not found'}), 404

        logger.info(f'[PAIR_DELETE] {pair_id}')
        system_logs_service.add_log('warning', f'🗑️ [200] Copy pair deleted: {pair_id}')
        return jsonify({'ok': True}), 200
    except Exception as e:
        logger.exception('[PAIR_DELETE_ERROR]')
        return jsonify({'ok': False, 'error': str(e)}), 500


@copy_trading_bp.route('/api/pairs/<pair_id>/toggle', methods=['POST'])
@require_auth
def toggle_copy_pair(pair_id):
    """เปิด/ปิด Copy Pair"""
    try:
        new_status = copy_manager.toggle_pair_status(pair_id)

        if new_status:
            status_emoji = "✅" if new_status == "active" else "⏸️"
            status_text = "enabled" if new_status == "active" else "disabled"
            system_logs_service.add_log('info', f'{status_emoji} [200] Copy pair {status_text}: {pair_id}')
            return jsonify({'success': True, 'status': new_status})
        else:
            system_logs_service.add_log('warning', f'⚠️ [404] Copy pair toggle failed - Pair {pair_id} not found')
            return jsonify({'error': 'Pair not found'}), 404

    except Exception as e:
        logger.error(f"[API] Toggle pair error: {e}")
        return jsonify({'error': str(e)}), 500


@copy_trading_bp.route('/api/pairs/<pair_id>/add-master', methods=['POST'])
@require_auth
def add_master_to_pair(pair_id):
    '''
    เพิ่ม Master Account เข้าไปในคู่ที่มีอยู่แล้ว
    จะใช้ API key เดียวกันกับคู่เดิม

    Request Body:
    {
        "master_account": "9999888"
    }

    Response:
    {
        "success": true,
        "pair": { ...ข้อมูลคู่ใหม่... }
    }
    '''
    try:
        data = request.get_json() or {}
        master_account = str(data.get('master_account', '')).strip()

        if not master_account:
            system_logs_service.add_log('error', '❌ [400] Add master failed - Account number required')
            return jsonify({'error': 'Master account is required'}), 400

        # ตรวจสอบว่า account มีอยู่ใน session_manager หรือไม่
        if not session_manager.account_exists(master_account):
            system_logs_service.add_log('error', f'❌ [404] Add master failed - Account {master_account} not found')
            return jsonify({'error': f'Master account {master_account} not found'}), 404

        # ดึงข้อมูลคู่ที่มีอยู่
        pair = copy_manager.get_pair_by_id(pair_id)
        if not pair:
            system_logs_service.add_log('error', f'❌ [404] Add master failed - Pair {pair_id} not found')
            return jsonify({'error': 'Pair not found'}), 404

        # ใช้ API key จากคู่เดิม
        api_key = pair.get('api_key') or pair.get('apiKey')

        # ดึง slaves ทั้งหมดที่ใช้ API key เดียวกัน
        existing_pairs = [p for p in copy_manager.pairs
                         if (p.get('api_key') or p.get('apiKey')) == api_key]

        if not existing_pairs:
            system_logs_service.add_log('error', f'❌ [404] Add master failed - No existing pairs with API key')
            return jsonify({'error': 'No existing pairs found with this API key'}), 404

        # เอา slave แรกมาใช้ (สร้างคู่ใหม่ Master ใหม่ -> Slave เดิม)
        first_slave = existing_pairs[0].get('slave_account')
        settings = existing_pairs[0].get('settings', {})

        # ตรวจสอบว่าคู่นี้มีอยู่แล้วหรือไม่
        for p in copy_manager.pairs:
            if (p.get('master_account') == master_account and
                p.get('slave_account') == first_slave and
                (p.get('api_key') or p.get('apiKey')) == api_key):
                system_logs_service.add_log('warning', f'⚠️ [400] Add master failed - Pair already exists')
                return jsonify({'error': 'This master-slave pair already exists'}), 400

        # สร้างคู่ใหม่ด้วย API key เดียวกัน
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

        # เพิ่มคู่ใหม่
        copy_manager.pairs.append(new_pair)
        copy_manager._save_pairs()

        # อัพเดท API key mapping
        if hasattr(copy_manager, 'api_keys'):
            if api_key not in copy_manager.api_keys:
                copy_manager.api_keys[api_key] = []
            if isinstance(copy_manager.api_keys[api_key], list):
                copy_manager.api_keys[api_key].append(new_pair['id'])
            else:
                # แปลงจาก string เป็น list
                old_id = copy_manager.api_keys[api_key]
                copy_manager.api_keys[api_key] = [old_id, new_pair['id']]
            if hasattr(copy_manager, '_save_api_keys'):
                copy_manager._save_api_keys()

        logger.info(f"[API] Added master {master_account} to pair group with API key {api_key[:8]}...")
        system_logs_service.add_log('success', f'✅ [201] Master {master_account} added to pair {pair_id}')

        return jsonify({'success': True, 'pair': new_pair}), 201

    except Exception as e:
        logger.error(f"[API] Add master to pair error: {e}")
        system_logs_service.add_log('error', f'❌ [500] Add master failed: {str(e)}')
        return jsonify({'error': str(e)}), 500


@copy_trading_bp.route('/api/pairs/<pair_id>/add-slave', methods=['POST'])
@require_auth
def add_slave_to_pair(pair_id):
    '''
    เพิ่ม Slave Account เข้าไปในคู่ที่มีอยู่แล้ว
    จะใช้ API key เดียวกันกับคู่เดิม และใช้ settings ที่ระบุ

    Request Body:
    {
        "slave_account": "5555444",
        "settings": {
            "auto_map_symbol": true,
            "auto_map_volume": true,
            "copy_psl": true,
            "volume_mode": "multiply",
            "multiplier": 3
        }
    }

    Response:
    {
        "success": true,
        "pair": { ...ข้อมูลคู่ใหม่... }
    }
    '''
    try:
        data = request.get_json() or {}
        slave_account = str(data.get('slave_account', '')).strip()
        settings = data.get('settings', {})

        if not slave_account:
            system_logs_service.add_log('error', '❌ [400] Add slave failed - Account number required')
            return jsonify({'error': 'Slave account is required'}), 400

        # ตรวจสอบว่า account มีอยู่ใน session_manager หรือไม่
        if not session_manager.account_exists(slave_account):
            system_logs_service.add_log('error', f'❌ [404] Add slave failed - Account {slave_account} not found')
            return jsonify({'error': f'Slave account {slave_account} not found'}), 404

        # ดึงข้อมูลคู่ที่มีอยู่
        pair = copy_manager.get_pair_by_id(pair_id)
        if not pair:
            system_logs_service.add_log('error', f'❌ [404] Add slave failed - Pair {pair_id} not found')
            return jsonify({'error': 'Pair not found'}), 404

        # ใช้ API key และ master จากคู่เดิม
        api_key = pair.get('api_key') or pair.get('apiKey')
        master_account = pair.get('master_account')

        # ตรวจสอบว่าคู่นี้มีอยู่แล้วหรือไม่
        for p in copy_manager.pairs:
            if (p.get('master_account') == master_account and
                p.get('slave_account') == slave_account and
                (p.get('api_key') or p.get('apiKey')) == api_key):
                system_logs_service.add_log('warning', f'⚠️ [400] Add slave failed - Pair already exists')
                return jsonify({'error': 'This master-slave pair already exists'}), 400

        # สร้างคู่ใหม่สำหรับ Slave ตัวใหม่
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

        # เพิ่มคู่ใหม่
        copy_manager.pairs.append(new_pair)
        copy_manager._save_pairs()

        # อัพเดท API key mapping
        if hasattr(copy_manager, 'api_keys'):
            if api_key not in copy_manager.api_keys:
                copy_manager.api_keys[api_key] = []
            if isinstance(copy_manager.api_keys[api_key], list):
                copy_manager.api_keys[api_key].append(new_pair['id'])
            else:
                # แปลงจาก string เป็น list
                old_id = copy_manager.api_keys[api_key]
                copy_manager.api_keys[api_key] = [old_id, new_pair['id']]
            if hasattr(copy_manager, '_save_api_keys'):
                copy_manager._save_api_keys()

        logger.info(f"[API] Added slave {slave_account} to pair group with API key {api_key[:8]}...")
        system_logs_service.add_log('success', f'✅ [201] Slave {slave_account} added to pair {pair_id}')

        return jsonify({'success': True, 'pair': new_pair}), 201

    except Exception as e:
        logger.error(f"[API] Add slave to pair error: {e}")
        system_logs_service.add_log('error', f'❌ [500] Add slave failed: {str(e)}')
        return jsonify({'error': str(e)}), 500


# =================== Master/Slave Accounts Management ===================

@copy_trading_bp.route('/api/copy/master-accounts', methods=['GET'])
@require_auth
def get_master_accounts():
    """ดึงรายการ Master Accounts ทั้งหมด"""
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


@copy_trading_bp.route('/api/copy/master-accounts', methods=['POST'])
@require_auth
def add_master_account():
    """เพิ่ม Master Account"""
    try:
        data = request.get_json() or {}
        account = str(data.get('account', '')).strip()
        nickname = str(data.get('nickname', '')).strip()

        if not account:
            return jsonify({'error': 'Account number is required'}), 400

        # ถ้า account ยังไม่มีใน Account Management ให้สร้างใหม่
        if not session_manager.account_exists(account):
            if not session_manager.add_remote_account(account, nickname):
                return jsonify({'error': f'Failed to create account {account}'}), 500
            logger.info(f"[API] Created new account in Account Management: {account}")

        # โหลดรายการเดิม
        master_file = Path('data/master_accounts.json')
        if master_file.exists():
            with open(master_file, 'r', encoding='utf-8') as f:
                masters = json.load(f)
        else:
            masters = []

        # ตรวจสอบว่ามีอยู่แล้วหรือไม่
        if any(m.get('account') == account for m in masters):
            return jsonify({'error': 'Master account already exists'}), 400

        # เพิ่ม account ใหม่
        new_master = {
            'id': str(int(datetime.now().timestamp() * 1000)),
            'account': account,
            'nickname': nickname
        }

        masters.append(new_master)

        # บันทึกลงไฟล์
        master_file.parent.mkdir(parents=True, exist_ok=True)
        with open(master_file, 'w', encoding='utf-8') as f:
            json.dump(masters, f, indent=2, ensure_ascii=False)

        logger.info(f"[API] Added master account: {account}")
        system_logs_service.add_log('success', f'✅ [201] Master account {account} added')

        return jsonify({'success': True, 'account': new_master}), 201

    except Exception as e:
        logger.error(f"[API] Add master account error: {e}")
        system_logs_service.add_log('error', f'❌ [500] Add master failed: {str(e)}')
        return jsonify({'error': str(e)}), 500


@copy_trading_bp.route('/api/copy/master-accounts/<account_id>', methods=['DELETE'])
@require_auth
def delete_master_account(account_id):
    """ลบ Master Account พร้อม Cascade Delete (ลบ Pairs และ History ที่เกี่ยวข้อง)"""
    try:
        master_file = Path('data/master_accounts.json')
        if not master_file.exists():
            return jsonify({'error': 'No master accounts found'}), 404

        with open(master_file, 'r', encoding='utf-8') as f:
            masters = json.load(f)

        # หา account ที่จะลบ
        original_count = len(masters)
        # Find the actual account number from masters
        account_number = None
        for m in masters:
            if m.get('id') == account_id or m.get('account') == account_id:
                account_number = m.get('account')
                break

        masters = [m for m in masters if m.get('id') != account_id and m.get('account') != account_id]

        if len(masters) == original_count:
            return jsonify({'error': 'Master account not found'}), 404

        # บันทึก master_accounts.json
        with open(master_file, 'w', encoding='utf-8') as f:
            json.dump(masters, f, indent=2, ensure_ascii=False)

        # 🔥 CASCADE DELETE: ลบ Pairs และ History ที่เกี่ยวข้อง
        deleted_pairs = 0
        deleted_history = 0

        if account_number:
            try:
                # ลบ Copy Pairs ทั้งหมดที่เกี่ยวข้องกับ account นี้
                deleted_pairs = copy_manager.delete_pairs_by_account(account_number)
                logger.info(f"[CASCADE_DELETE] Deleted {deleted_pairs} pairs for master account {account_number}")
            except Exception as e:
                logger.warning(f"[CASCADE_DELETE] Failed to delete pairs: {e}")

            try:
                # ลบ Copy Trading History ทั้งหมดที่เกี่ยวข้องกับ account นี้
                deleted_history = copy_history.delete_by_account(account_number)
                logger.info(f"[CASCADE_DELETE] Deleted {deleted_history} history events for master account {account_number}")
            except Exception as e:
                logger.warning(f"[CASCADE_DELETE] Failed to delete history: {e}")

        logger.info(f"[API] Deleted master account: {account_id} (Pairs: {deleted_pairs}, History: {deleted_history})")
        system_logs_service.add_log('success', f'✅ [200] Master account {account_id} deleted (cleaned: {deleted_pairs} pairs, {deleted_history} history events)')

        return jsonify({
            'success': True,
            'deleted_pairs': deleted_pairs,
            'deleted_history': deleted_history
        })

    except Exception as e:
        logger.error(f"[API] Delete master account error: {e}")
        return jsonify({'error': str(e)}), 500


@copy_trading_bp.route('/api/copy/slave-accounts', methods=['GET'])
@require_auth
def get_slave_accounts():
    """ดึงรายการ Slave Accounts ทั้งหมด"""
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


@copy_trading_bp.route('/api/copy/slave-accounts', methods=['POST'])
@require_auth
def add_slave_account():
    """เพิ่ม Slave Account"""
    try:
        data = request.get_json() or {}
        account = str(data.get('account', '')).strip()
        nickname = str(data.get('nickname', '')).strip()

        if not account:
            return jsonify({'error': 'Account number is required'}), 400

        # ถ้า account ยังไม่มีใน Account Management ให้สร้างใหม่
        if not session_manager.account_exists(account):
            if not session_manager.add_remote_account(account, nickname):
                return jsonify({'error': f'Failed to create account {account}'}), 500
            logger.info(f"[API] Created new account in Account Management: {account}")

        # โหลดรายการเดิม
        slave_file = Path('data/slave_accounts.json')
        if slave_file.exists():
            with open(slave_file, 'r', encoding='utf-8') as f:
                slaves = json.load(f)
        else:
            slaves = []

        # ตรวจสอบว่ามีอยู่แล้วหรือไม่
        if any(s.get('account') == account for s in slaves):
            return jsonify({'error': 'Slave account already exists'}), 400

        # เพิ่ม account ใหม่
        new_slave = {
            'id': str(int(datetime.now().timestamp() * 1000)),
            'account': account,
            'nickname': nickname
        }

        slaves.append(new_slave)

        # บันทึกลงไฟล์
        slave_file.parent.mkdir(parents=True, exist_ok=True)
        with open(slave_file, 'w', encoding='utf-8') as f:
            json.dump(slaves, f, indent=2, ensure_ascii=False)

        logger.info(f"[API] Added slave account: {account}")
        system_logs_service.add_log('success', f'✅ [201] Slave account {account} added')

        return jsonify({'success': True, 'account': new_slave}), 201

    except Exception as e:
        logger.error(f"[API] Add slave account error: {e}")
        system_logs_service.add_log('error', f'❌ [500] Add slave failed: {str(e)}')
        return jsonify({'error': str(e)}), 500


@copy_trading_bp.route('/api/copy/slave-accounts/<account_id>', methods=['DELETE'])
@require_auth
def delete_slave_account(account_id):
    """ลบ Slave Account พร้อม Cascade Delete (ลบ Pairs และ History ที่เกี่ยวข้อง)"""
    try:
        slave_file = Path('data/slave_accounts.json')
        if not slave_file.exists():
            return jsonify({'error': 'No slave accounts found'}), 404

        with open(slave_file, 'r', encoding='utf-8') as f:
            slaves = json.load(f)

        # หา account ที่จะลบ
        original_count = len(slaves)
        # Find the actual account number from slaves
        account_number = None
        for s in slaves:
            if s.get('id') == account_id or s.get('account') == account_id:
                account_number = s.get('account')
                break

        slaves = [s for s in slaves if s.get('id') != account_id and s.get('account') != account_id]

        if len(slaves) == original_count:
            return jsonify({'error': 'Slave account not found'}), 404

        # บันทึก slave_accounts.json
        with open(slave_file, 'w', encoding='utf-8') as f:
            json.dump(slaves, f, indent=2, ensure_ascii=False)

        # 🔥 CASCADE DELETE: ลบ Pairs และ History ที่เกี่ยวข้อง
        deleted_pairs = 0
        deleted_history = 0

        if account_number:
            try:
                # ลบ Copy Pairs ทั้งหมดที่เกี่ยวข้องกับ account นี้
                deleted_pairs = copy_manager.delete_pairs_by_account(account_number)
                logger.info(f"[CASCADE_DELETE] Deleted {deleted_pairs} pairs for slave account {account_number}")
            except Exception as e:
                logger.warning(f"[CASCADE_DELETE] Failed to delete pairs: {e}")

            try:
                # ลบ Copy Trading History ทั้งหมดที่เกี่ยวข้องกับ account นี้
                deleted_history = copy_history.delete_by_account(account_number)
                logger.info(f"[CASCADE_DELETE] Deleted {deleted_history} history events for slave account {account_number}")
            except Exception as e:
                logger.warning(f"[CASCADE_DELETE] Failed to delete history: {e}")

        logger.info(f"[API] Deleted slave account: {account_id} (Pairs: {deleted_pairs}, History: {deleted_history})")
        system_logs_service.add_log('success', f'✅ [200] Slave account {account_id} deleted (cleaned: {deleted_pairs} pairs, {deleted_history} history events)')

        return jsonify({
            'success': True,
            'deleted_pairs': deleted_pairs,
            'deleted_history': deleted_history
        })

    except Exception as e:
        logger.error(f"[API] Delete slave account error: {e}")
        return jsonify({'error': str(e)}), 500


# =================== Copy Trading Signal Endpoint ===================

@copy_trading_bp.route('/api/copy/trade', methods=['POST'])
def copy_trade_endpoint():
    """
    Receive trading signal from Master EA (Copy Trading)

    🆕 Version 2.0: รองรับ Multiple Pairs ต่อ API Key
    ใช้ copy_handler.process_master_signal() เพื่อ handle logic ทั้งหมด
    """
    # Apply rate limit
    limiter.limit("100 per minute")(lambda: None)()

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
        system_logs_service.add_log('info', f'📡 [200] Copy signal received: {action} {symbol} from {account}')

        # 4) Basic validation
        api_key = str(data.get('api_key', '')).strip()
        if not api_key:
            system_logs_service.add_log('error', '❌ [400] Copy trade failed - API key missing')
            return jsonify({'error': 'api_key is required'}), 400

        # 5) 🔥 ใช้ copy_handler แทน - มันจะ handle ทุกอย่างเอง
        #    - ตรวจสอบ API Key
        #    - เลือก Pair ตาม Master Account
        #    - ตรวจสอบ Slave status
        #    - แปลง Signal เป็น Command
        #    - ส่งคำสั่งไปยัง Slave
        result = copy_handler.process_master_signal(api_key, data)

        if not result or not result.get('success'):
            error_msg = (result or {}).get('error', 'Processing failed')
            system_logs_service.add_log('error', f'❌ [500] Copy trade failed: {error_msg}')
            return jsonify({'error': error_msg}), 500

        # 6) Success!
        master_account = data.get('account', '-')
        symbol = data.get('symbol', '-')
        volume = data.get('volume', '-')

        system_logs_service.add_log(
            'success',
            f'✅ [200] Copy trade executed: {master_account} → Slave ({action} {symbol} Vol:{volume})'
        )

        return jsonify({
            'success': True,
            'message': 'Copy trade executed successfully'
        }), 200

    except Exception as e:
        logger.error(f"[COPY_TRADE_ERROR] {e}", exc_info=True)
        system_logs_service.add_log('error', f'❌ [500] Copy trade error: {str(e)[:80]}')
        return jsonify({'error': str(e)}), 500


@copy_trading_bp.route('/api/copy/history', methods=['GET'])
@require_auth
def get_copy_history():
    """ดึงประวัติการคัดลอก"""
    try:
        limit = int(request.args.get('limit', 100))
        status = request.args.get('status')

        limit = max(1, min(limit, 1000))

        history = copy_history.get_history(limit=limit, status=status)

        return jsonify({'history': history, 'count': len(history)})

    except Exception as e:
        logger.error(f"[API] Get copy history error: {e}")
        return jsonify({'error': str(e)}), 500


@copy_trading_bp.route('/api/copy/history/clear', methods=['POST'])
@require_auth
def clear_copy_history():
    """ลบประวัติการคัดลอกทั้งหมด"""
    try:
        confirm = request.args.get('confirm')
        if confirm != '1':
            system_logs_service.add_log('warning', '⚠️ [400] Clear history failed - Missing confirmation')
            return jsonify({'error': 'Missing confirm=1'}), 400

        success = copy_history.clear_history()

        if success:
            system_logs_service.add_log('warning', '🗑️ [200] Copy history cleared')
            return jsonify({'success': True})
        else:
            system_logs_service.add_log('error', '❌ [500] Failed to clear copy history')
            return jsonify({'error': 'Failed to clear history'}), 500

    except Exception as e:
        logger.error(f"[API] Clear copy history error: {e}")
        return jsonify({'error': str(e)}), 500


@copy_trading_bp.route('/copy-history/clear', methods=['POST'])
@require_auth
def clear_copy_history_legacy():
    """Backward-compat: รองรับเส้นทางเก่า /copy-history/clear"""
    try:
        confirm = request.args.get('confirm')
        if confirm != '1':
            system_logs_service.add_log('warning', '⚠️ [400] Clear history failed - Missing confirmation')
            return jsonify({'error': 'Missing confirm=1'}), 400

        success = copy_history.clear_history()
        if success:
            system_logs_service.add_log('warning', '🗑️ [200] Copy history cleared')
            return jsonify({'success': True})
        else:
            system_logs_service.add_log('error', '❌ [500] Failed to clear copy history')
            return jsonify({'error': 'Failed to clear history'}), 500
    except Exception as e:
        logger.error(f"[API] Legacy clear copy history error: {e}")
        return jsonify({'error': str(e)}), 500


# =================== Copy Trading SSE ===================

@copy_trading_bp.route('/events/copy-trades', methods=['GET'])
def sse_copy_trades():
    """Server-Sent Events stream สำหรับ Copy Trading history"""
    client_queue = queue.Queue(maxsize=256)
    copy_history.add_sse_client(client_queue)

    last_beat = time.time()
    HEARTBEAT_SECS = 20

    def gen():
        nonlocal last_beat
        try:
            yield "retry: 3000\\n\\n"

            while True:
                try:
                    now = time.time()
                    if now - last_beat >= HEARTBEAT_SECS:
                        last_beat = now
                        yield ": keep-alive\\n\\n"

                    msg = client_queue.get(timeout=1.0)
                    yield msg

                except queue.Empty:
                    continue

        finally:
            copy_history.remove_sse_client(client_queue)

    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        "X-Accel-Buffering": "no",
    }

    return Response(stream_with_context(gen()), headers=headers)

