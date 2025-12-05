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
from app.middleware.auth import require_auth, session_login_required

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
@require_auth
def get_system_logs():
    """
    ดึง system logs (Multi-User SaaS: filtered by user's accounts)

    Users see only logs related to their own accounts.
    Admins see all logs.
    """
    try:
        from flask import session
        from app.middleware.auth import get_current_user_id

        user_id = get_current_user_id()
        is_admin = session.get('is_admin', False)

        limit = int(request.args.get('limit', 300))
        limit = max(1, min(limit, 300))

        if is_admin:
            # Admins see all logs
            logs = system_logs_service.get_logs(limit=limit)
        else:
            # Get user's accounts for filtering
            user_accounts = set()
            try:
                from app.services.account_allowlist_service import AccountAllowlistService
                allowlist_service = AccountAllowlistService()
                user_webhook_accounts = allowlist_service.get_webhook_allowlist_by_user(user_id)
                user_accounts = set(str(a.get('account', '')) for a in user_webhook_accounts)
            except Exception as e:
                logger.warning(f"[SYSTEM_LOGS] Failed to get user accounts: {e}")

            logs = system_logs_service.get_logs_by_user(
                user_id=user_id,
                user_accounts=user_accounts,
                limit=limit
            )

        return jsonify({
            'success': True,
            'logs': logs,
            'total': len(logs)
        }), 200
    except Exception as e:
        logger.error(f"[SYSTEM_LOGS] Error getting logs: {e}")
        return jsonify({'error': str(e)}), 500



@system_bp.route('/api/system/logs/clear', methods=['POST'])
@require_auth
def clear_system_logs():
    """ล้าง system logs (Users clear only their own logs, Admins clear all)"""
    try:
        from flask import session
        from app.middleware.auth import get_current_user_id

        user_id = get_current_user_id()
        is_admin = session.get('is_admin', False)

        if is_admin:
            # Admin clears all logs
            system_logs_service.clear_logs()
        else:
            # User clears only their own logs
            system_logs_service.clear_logs(user_id=user_id)

        system_logs_service.add_log('info', 'System logs cleared', user_id=user_id)

        return jsonify({'success': True}), 200
    except Exception as e:
        logger.error(f"[SYSTEM_LOGS] Error clearing logs: {e}")
        return jsonify({'error': str(e)}), 500



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


# ✅ Add this function for SSE broadcasting
def broadcast_to_sse_clients(data: dict, event_type: str = 'message'):
    """
    Broadcast event to all connected SSE clients

    Args:
        data: Data to broadcast (will be JSON serialized)
        event_type: SSE event type
    """
    try:
        message = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"

        # Broadcast to all system log SSE clients via the service
        if system_logs_service:
            with system_logs_service.sse_lock:
                dead_clients = []

                for client_queue in system_logs_service.sse_clients:
                    try:
                        client_queue.put_nowait(message)
                    except:
                        dead_clients.append(client_queue)

                # Remove dead clients
                for dead in dead_clients:
                    try:
                        system_logs_service.sse_clients.remove(dead)
                    except:
                        pass

                logger.debug(f"[SSE_BROADCAST] Sent {event_type} to {len(system_logs_service.sse_clients)} client(s)")

    except Exception as e:
        logger.error(f"[SSE_BROADCAST_ERROR] {e}")


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


# =================== Authentication ===================

@system_bp.route('/login', methods=['POST'])
def login_api():
    """Login endpoint for UI authentication"""
    from flask import session
    from dotenv import load_dotenv
    import os

    try:
        # Load environment variables explicitly
        load_dotenv(override=True)

        data = request.json or {}
        username = data.get("username", "")
        password = data.get("password", "")

        BASIC_USER = os.getenv('BASIC_USER')
        BASIC_PASS = os.getenv('BASIC_PASS')

        # Validate credentials are configured
        if not BASIC_USER or not BASIC_PASS:
            logger.error("[LOGIN] Credentials not found in .env file")
            system_logs_service.add_log('error', '❌ [500] Login failed - Server configuration error (missing BASIC_USER or BASIC_PASS in .env)')
            return jsonify({"ok": False, "error": "Server configuration error"}), 500

        if username == BASIC_USER and password == BASIC_PASS:
            session["auth"] = True
            ip = request.remote_addr
            system_logs_service.add_log('success', f'🔓 [200] Login successful - User: {username}, IP: {ip}')
            logger.info(f"[LOGIN] Successful login from {ip} - User: {username}")
            return jsonify({"ok": True}), 200

        ip = request.remote_addr
        system_logs_service.add_log('warning', f'🔒 [401] Login failed - User: {username}, IP: {ip}')
        logger.warning(f"[LOGIN] Failed login attempt from {ip} - User: {username}")
        return jsonify({"ok": False, "error": "Invalid credentials"}), 401

    except Exception as e:
        logger.error(f"[LOGIN] Error: {e}")
        return jsonify({"ok": False, "error": "Login error"}), 500


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

