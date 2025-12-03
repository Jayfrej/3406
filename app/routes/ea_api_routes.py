"""
EA API Routes
Endpoints for Expert Advisor (EA) communication
"""
import logging
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

# Create blueprint
ea_api_bp = Blueprint('ea_api', __name__)

# Dependencies (will be injected)
command_queue = None
balance_manager = None
session_manager = None
limiter = None


def init_ea_api_routes(cq, bm, sm, lim=None):
    """Initialize EA API routes with dependencies"""
    global command_queue, balance_manager, session_manager, limiter
    command_queue = cq
    balance_manager = bm
    session_manager = sm
    limiter = lim


@ea_api_bp.route('/api/commands/<account>', methods=['GET'])
def get_commands(account):
    """
    EA polls this endpoint to get pending commands
    GET /api/commands/279289341?limit=10
    """
    try:
        limit = int(request.args.get('limit', 10))

        if not command_queue:
            return jsonify({'commands': []}), 200

        # Get pending commands for this account
        commands = command_queue.get_pending_commands(account, limit=limit)

        return jsonify({'commands': commands}), 200

    except Exception as e:
        logger.error(f"[EA_API] Error getting commands for {account}: {e}")
        return jsonify({'error': str(e), 'commands': []}), 500


@ea_api_bp.route('/api/ea/heartbeat', methods=['POST'])
def ea_heartbeat():
    """
    EA sends heartbeat every few seconds
    POST /api/ea/heartbeat
    Body: {"account": "279289341", "status": "online"}
    """
    try:
        data = request.json or {}
        account = data.get('account')
        status = data.get('status', 'online')

        if not account:
            return jsonify({'error': 'Missing account'}), 400

        if session_manager:
            # Update last seen timestamp
            session_manager.update_account_heartbeat(account)

        logger.debug(f"[EA_HEARTBEAT] Account {account}: {status}")
        return jsonify({'ok': True}), 200

    except Exception as e:
        logger.error(f"[EA_HEARTBEAT] Error: {e}")
        return jsonify({'error': str(e)}), 500


@ea_api_bp.route('/api/balance/need-update/<account>', methods=['GET'])
def check_balance_update_needed(account):
    """
    EA checks if balance needs to be updated
    GET /api/balance/need-update/279289341
    """
    try:
        if not balance_manager:
            return jsonify({'need_update': False}), 200

        # Check if balance data exists and is fresh
        balance_info = balance_manager.get_balance_info(account)

        if not balance_info:
            # No balance data - need update
            return jsonify({'need_update': True}), 200

        # Check if data is stale (older than cache_expiry_seconds)
        import time
        timestamp = balance_info.get('timestamp', 0)
        age_seconds = time.time() - timestamp
        need_update = age_seconds > balance_manager.cache_expiry_seconds

        return jsonify({'need_update': need_update}), 200

    except Exception as e:
        logger.error(f"[BALANCE_CHECK] Error for {account}: {e}")
        return jsonify({'need_update': False}), 500


@ea_api_bp.route('/debug/commands/<account>', methods=['GET'])
def debug_commands(account):
    """
    Debug endpoint to check queued commands
    GET /debug/commands/279289341

    Note: This endpoint requires authentication in production
    """
    try:
        if not command_queue:
            return jsonify({
                'account': account,
                'queue_size': 0,
                'commands': [],
                'error': 'Command queue not initialized'
            }), 500

        # Get all commands for this account
        commands = command_queue.get_commands(str(account))

        return jsonify({
            'account': account,
            'queue_size': len(commands),
            'commands': commands,
            'timestamp': import_time()
        }), 200

    except Exception as e:
        logger.error(f"[DEBUG_COMMANDS] Error for {account}: {e}")
        return jsonify({
            'account': account,
            'error': str(e),
            'queue_size': 0,
            'commands': []
        }), 500


def import_time():
    """Helper to get current timestamp"""
    import time
    return time.time()


