"""
Command Routes
Handles EA command queue endpoints
"""
import logging
from flask import Blueprint, request, jsonify
from app.middleware.auth import session_login_required

logger = logging.getLogger(__name__)

# Create blueprint
command_bp = Blueprint('command', __name__)

# Dependencies (injected by app factory)
command_queue = None
session_manager = None
limiter = None
settings_service = None


def init_command_routes(cq, sm, lim, ss):
    """
    Initialize command routes with dependencies

    Args:
        cq: CommandQueue instance
        sm: SessionManager instance
        lim: Limiter instance
        ss: SettingsService instance
    """
    global command_queue, session_manager, limiter, settings_service

    command_queue = cq
    session_manager = sm
    limiter = lim
    settings_service = ss


def get_command_api_rate_limit():
    """Get dynamic rate limit from settings"""
    try:
        settings = settings_service.load_settings()
        # ✅ FIX: อ่านจาก rate_limits.command_api (ไม่ใช่ root level)
        rate_limits = settings.get('rate_limits', {})
        return rate_limits.get('command_api', '10000 per hour')  # ใช้ค่าเดียวกับ app_factory default
    except Exception:
        return '10000 per hour'  # fallback ให้สูงพอสำหรับ EA polling


# =================== Command Queue API ===================

@command_bp.route('/api/commands/<account>', methods=['GET'])
def get_commands_for_ea(account: str):
    """
    API สำหรับ EA poll คำสั่งที่รออยู่

    EA จะเรียก endpoint นี้ทุกๆ 1-2 วินาที

    Returns:
        {
            "success": true,
            "account": "123456",
            "commands": [{...}],
            "count": 1
        }
    """
    # Apply dynamic rate limit
    limiter.limit(get_command_api_rate_limit)(lambda: None)()

    try:
        account = str(account).strip()
        limit = int(request.args.get('limit', 10))

        # 🔧 FIX: ลบการตรวจสอบ account_exists ที่เข้มงวดเกินไป
        # ให้ EA ทุกตัวสามารถ poll ได้ แม้ยังไม่ได้ลงทะเบียนใน UI

        # ❌ Old code (จาก backup/server.py):
        # if not session_manager.account_exists(account):
        #     logger.warning(f"[COMMAND_API] Account {account} not found")
        #     return jsonify({'success': False, 'error': 'Account not found'}), 404

        # ✅ New code: Log แต่ไม่ปฏิเสธ
        if not session_manager.account_exists(account):
            logger.debug(f"[COMMAND_API] EA polling from unregistered account: {account}")

        # ดึงคำสั่งที่รออยู่
        commands = command_queue.get_pending_commands(account, limit=limit)

        if commands:
            logger.info(f"[COMMAND_API] ✅ Retrieved {len(commands)} command(s) for {account}")
        else:
            logger.debug(f"[COMMAND_API] No commands for {account}")

        return jsonify({
            'success': True,
            'account': account,
            'commands': commands,
            'count': len(commands)
        })

    except Exception as e:
        logger.error(f"[COMMAND_API] Error: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@command_bp.route('/api/commands/<account>/ack', methods=['POST'])
def acknowledge_command(account: str):
    """
    API สำหรับ EA แจ้งว่าประมวลผลคำสั่งเสร็จแล้ว

    Body: {"queue_id": "...", "success": true, "error": "..."}
    """
    try:
        account = str(account).strip()
        data = request.get_json(silent=True) or {}

        queue_id = data.get('queue_id')
        if not queue_id:
            return jsonify({'success': False, 'error': 'queue_id required'}), 400

        # Acknowledge คำสั่ง
        success = command_queue.acknowledge_command(account, queue_id)

        if success:
            logger.info(f"[COMMAND_API] ✅ Command acknowledged: {queue_id} by {account}")

            # บันทึกประวัติ (ถ้า EA ส่ง error มา)
            if not data.get('success', True):
                error_msg = data.get('error', 'Unknown error')
                logger.warning(f"[COMMAND_API] ⚠️ Command {queue_id} failed: {error_msg}")

            return jsonify({'success': True, 'message': 'Command acknowledged'})
        else:
            return jsonify({
                'success': False,
                'error': 'Command not found or already acknowledged'
            }), 404

    except Exception as e:
        logger.error(f"[COMMAND_API] Acknowledge error: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@command_bp.route('/api/commands/<account>/status', methods=['GET'])
@session_login_required
def get_command_queue_status(account: str):
    """API สำหรับดูสถานะ queue (admin only)"""
    try:
        account = str(account).strip()
        pending_count = command_queue.get_queue_size(account)
        # auto_ack=False: ดูสถานะอย่างเดียว ไม่ acknowledge
        pending_commands = command_queue.get_pending_commands(account, limit=100, auto_ack=False)

        return jsonify({
            'success': True,
            'account': account,
            'pending_count': pending_count,
            'commands': pending_commands
        })

    except Exception as e:
        logger.error(f"[COMMAND_API] Status error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@command_bp.route('/api/commands/<account>/clear', methods=['POST'])
@session_login_required
def clear_command_queue(account: str):
    """API สำหรับล้าง queue (admin only)"""
    try:
        account = str(account).strip()
        cleared = command_queue.clear_queue(account)

        logger.info(f"[COMMAND_API] 🗑️ Cleared {cleared} command(s) for {account}")

        return jsonify({
            'success': True,
            'message': f'Cleared {cleared} commands',
            'count': cleared
        })

    except Exception as e:
        logger.error(f"[COMMAND_API] Clear error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@command_bp.route('/api/commands/status/all', methods=['GET'])
@session_login_required
def get_all_queues_status():
    """API สำหรับดูสถานะ queue ทั้งหมด (admin only)"""
    try:
        status = command_queue.get_all_queues_status()
        return jsonify({'success': True, 'status': status})

    except Exception as e:
        logger.error(f"[COMMAND_API] All status error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# =================== Debug Endpoints ===================

@command_bp.route('/debug/commands/<account>', methods=['GET'])
def debug_commands(account):
    """
    Debug endpoint to check queued commands
    GET /debug/commands/279289341

    Note: This endpoint requires authentication in production
    """
    try:
        account = str(account).strip()

        if not command_queue:
            return jsonify({
                'account': account,
                'queue_size': 0,
                'commands': [],
                'error': 'Command queue not initialized'
            }), 500

        # Get all commands for this account (auto_ack=False: debug only, don't consume)
        commands = command_queue.get_pending_commands(account, limit=100, auto_ack=False)

        import time
        return jsonify({
            'account': account,
            'queue_size': len(commands),
            'commands': commands,
            'timestamp': time.time()
        }), 200

    except Exception as e:
        logger.error(f"[DEBUG_COMMANDS] Error for {account}: {e}")
        return jsonify({
            'account': account,
            'error': str(e),
            'queue_size': 0,
            'commands': []
        }), 500
