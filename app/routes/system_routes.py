"""
System Routes
Handles system logs, health checks, and static file serving
"""
import time
import queue
import json
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, send_from_directory, Response, stream_with_context

logger = logging.getLogger(__name__)

# Create blueprint
system_bp = Blueprint('system', __name__)

# These will be injected by the app factory
system_logs_service = None
session_manager = None


def init_system_routes(sls, sm):
    """
    Initialize system routes with dependencies

    Args:
        sls: SystemLogsService instance
        sm: SessionManager instance
    """
    global system_logs_service, session_manager

    system_logs_service = sls
    session_manager = sm


# =================== System Logs API ===================

@system_bp.route('/api/system/logs', methods=['GET'])
def get_system_logs():
    """ดึง system logs"""
    from app.middleware.auth import session_login_required

    @session_login_required
    def _handler():
        try:
            limit = int(request.args.get('limit', 300))
            limit = max(1, min(limit, 300))

            logs = system_logs_service.get_logs(limit=limit)

            return jsonify({
                'success': True,
                'logs': logs,
                'total': len(logs)
            }), 200
        except Exception as e:
            logger.error(f"[SYSTEM_LOGS] Error getting logs: {e}")
            return jsonify({'error': str(e)}), 500

    return _handler()


@system_bp.route('/api/system/logs/clear', methods=['POST'])
def clear_system_logs():
    """ล้าง system logs ทั้งหมด"""
    from app.middleware.auth import session_login_required

    @session_login_required
    def _handler():
        try:
            system_logs_service.clear_logs()

            system_logs_service.add_log('info', 'System logs cleared')

            return jsonify({'success': True}), 200
        except Exception as e:
            logger.error(f"[SYSTEM_LOGS] Error clearing logs: {e}")
            return jsonify({'error': str(e)}), 500

    return _handler()


@system_bp.route('/events/system-logs', methods=['GET'])
def sse_system_logs():
    """Server-Sent Events stream สำหรับ real-time system logs"""
    client_queue = queue.Queue(maxsize=256)

    system_logs_service.add_sse_client(client_queue)

    last_beat = time.time()
    HEARTBEAT_SECS = 20

    def gen():
        nonlocal last_beat
        try:
            yield "retry: 3000\n\n"

            # ส่ง initial message
            init_msg = {
                'type': 'info',
                'message': 'Connected to system logs stream',
                'timestamp': datetime.now().isoformat()
            }
            yield f"data: {json.dumps(init_msg)}\n\n"

            while True:
                try:
                    now = time.time()
                    if now - last_beat >= HEARTBEAT_SECS:
                        last_beat = now
                        yield ": keep-alive\n\n"

                    msg = client_queue.get(timeout=1.0)
                    yield msg

                except queue.Empty:
                    continue

        finally:
            system_logs_service.remove_sse_client(client_queue)

    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        "X-Accel-Buffering": "no",
    }

    return Response(stream_with_context(gen()), headers=headers)


# =================== Health & Stats ===================

@system_bp.route('/health', methods=['GET', 'HEAD'])
def health_check():
    """สำหรับหน้า Account Management → Usage Statistics"""
    try:
        accounts = session_manager.get_all_accounts()
        total = len(accounts)
        online = sum(1 for a in accounts if a.get('status') == 'Online')
        offline = max(total - online, 0)
        return jsonify({
            'ok': True,
            'timestamp': datetime.now().isoformat(),
            'total_accounts': total,
            'online_accounts': online,
            'offline_accounts': offline,
            'instances': [{
                'account': acc['account'],
                'status': acc.get('status', 'Unknown'),
                'nickname': acc.get('nickname', ''),
                'pid': acc.get('pid'),
                'created': acc.get('created')
            } for acc in accounts]
        })
    except Exception as e:
        logger.error(f"[HEALTH_CHECK_ERROR] {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500


@system_bp.route('/accounts/stats', methods=['GET'])
def accounts_stats():
    """ทางเลือกเบากว่า /health (ส่งตัวเลขล้วน)"""
    accounts = session_manager.get_all_accounts()
    total = len(accounts)
    online = sum(1 for a in accounts if a.get('status') == 'Online')
    offline = max(total - online, 0)
    return jsonify({'ok': True, 'total': total, 'online': online, 'offline': offline})


# =================== Static Files ===================

@system_bp.route('/', methods=['GET'])
def index():
    """Serve index.html"""
    return send_from_directory('static', 'index.html')


@system_bp.route('/static/<path:filename>', methods=['GET'])
def static_files(filename):
    """Serve static files"""
    return send_from_directory('static', filename)


# =================== Error Handlers ===================
# Note: These will be registered at app level, not blueprint level

def register_error_handlers(app):
    """Register error handlers to the Flask app"""

    @app.errorhandler(405)
    def method_not_allowed(_):
        return jsonify({'error': 'Method not allowed'}), 405

    @app.errorhandler(404)
    def not_found(_):
        return jsonify({'error': 'Endpoint not found'}), 404

