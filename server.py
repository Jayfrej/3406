import smtplib
import ssl
# server.py â€” full fixed version

import os
import json
import logging
import threading
import time
import queue
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import Flask, request, jsonify, send_from_directory, session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv

# ==== import app modules ====
try:
    from app.trades import trades_bp, init_trades, record_and_broadcast, delete_account_history
except Exception:
    from trades import trades_bp, init_trades, record_and_broadcast, delete_account_history

try:
    from app.session_manager import SessionManager
    from app.symbol_mapper import SymbolMapper
    from app.email_handler import EmailHandler
except Exception:
    from session_manager import SessionManager
    from symbol_mapper import SymbolMapper
    from email_handler import EmailHandler



from app.broker_data_manager import BrokerDataManager
from app.signal_translator import SignalTranslator
from app.account_balance import balance_manager
# ==== env ====
load_dotenv()
BASIC_USER = os.getenv('BASIC_USER', 'admin')
BASIC_PASS = os.getenv('BASIC_PASS', 'pass')
WEBHOOK_TOKEN = os.getenv('WEBHOOK_TOKEN', 'default-token')
EXTERNAL_BASE_URL = os.getenv('EXTERNAL_BASE_URL', 'http://localhost:5000')

# ==== flask app ====
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-here')
SESSION_COOKIE_SECURE = False
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=SESSION_COOKIE_SECURE,
)

# ==== rate limiter ====
try:
    limiter = Limiter(key_func=get_remote_address, default_limits=["100 per hour"])
    limiter.init_app(app)
except TypeError:
    limiter = Limiter(app, key_func=get_remote_address, default_limits=["100 per hour"])

# Helper function for dynamic rate limits from settings
def get_command_api_rate_limit():
    """Get command API rate limit from settings (called at runtime by flask-limiter)"""
    try:
        settings = load_settings()
        return settings.get('rate_limits', {}).get('command_api', '60 per minute')
    except:
        return '60 per minute'

# ==== components ====
session_manager = SessionManager()
symbol_mapper = SymbolMapper()

broker_manager = BrokerDataManager(data_dir='data')
signal_translator = SignalTranslator(broker_manager, symbol_mapper)
email_handler = EmailHandler()

def _email_send_alert(subject: str, message: str) -> bool:
    """Wrapper to support email_handler.send_alert(...) when class lacks it."""
    try:
        from datetime import datetime
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        body = f"""MT5 Trading Bot Alert
=====================

Time: {ts}
Subject: {subject}

{message}

---
This is an automated message from MT5 Trading Bot."""
        # à¹€à¸£à¸µà¸¢à¸à¹ƒà¸Šà¹‰ send_alert à¹à¸—à¸™ send_email
        email_handler.send_alert(subject, body)
        return True
    except Exception as e:
        try:
            logger.error(f"[EMAIL_ALERT] Failed to send alert: {e}")
        except Exception:
            pass
        return False

if not hasattr(email_handler, 'send_alert'):
    try:
        email_handler.send_alert = _email_send_alert
        logger.info('[EMAIL] send_alert wrapper attached to EmailHandler instance')
    except Exception:
        pass


# =================== Copy Trading Setup (à¹€à¸žà¸´à¹ˆà¸¡à¸«à¸¥à¸±à¸‡ email_handler) ===================
from app.copy_trading.copy_manager import CopyManager
from app.copy_trading.copy_handler import CopyHandler
from app.copy_trading.copy_executor import CopyExecutor
from app.copy_trading.copy_history import CopyHistory

# Initialize Copy Trading components
copy_manager = CopyManager(email_handler=email_handler)
copy_history = CopyHistory()
copy_executor = CopyExecutor(session_manager, copy_history)
copy_handler = CopyHandler(copy_manager, symbol_mapper, copy_executor, session_manager, broker_manager, balance_manager, email_handler)

try:
    logger
except NameError:
    import logging
    logger = logging.getLogger(__name__)
logger.info("[COPY_TRADING] Components initialized successfully")


# =================== Background Scheduler for Monitoring ===================
try:
    from apscheduler.schedulers.background import BackgroundScheduler

    scheduler = BackgroundScheduler()

    def check_all_accounts_balance():
        """
        ตรวจสอบ balance ของทุก account ทุกๆ 5 นาที
        แจ้งเตือนเฉพาะเมื่อ account ONLINE แต่ balance หมดอายุ
        """
        try:
            accounts = session_manager.get_all_accounts()

            for account_info in accounts:
                account_id = account_info.get('account')
                if not account_id:
                    continue

                # ⭐ เช็คว่า account online ไหม
                is_online = session_manager.is_instance_alive(account_id)

                # ถ้า offline อยู่แล้ว ไม่ต้องเช็ค balance (มีการแจ้งเตือน online/offline อยู่แล้ว)
                if not is_online:
                    continue

                # เช็ค balance health (เฉพาะ account online)
                health = balance_manager.check_balance_health(account_id)

                # ถ้าไม่ healthy และ account online ให้แจ้งเตือน
                if not health.get('healthy') and email_handler:
                    try:
                        warnings_text = "\n".join(f"- {w}" for w in health.get('warnings', []))
                        email_handler.send_alert(
                            f"⚠️ Balance Alert - Account {account_id}",
                            f"""
Account Balance Warning

Account: {account_id}
Status: Online (but balance data issue)
Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

Warnings:
{warnings_text}

Please check if the EA is properly configured to send balance updates.
                            """.strip(),
                            priority='high'
                        )
                        logger.warning(f"[BALANCE_MONITOR] Balance alert sent for account {account_id}")
                    except Exception as e:
                        logger.error(f"[BALANCE_MONITOR] Failed to send balance alert: {e}")

        except Exception as e:
            logger.error(f"[BALANCE_MONITOR] Error in scheduled balance check: {e}", exc_info=True)

    # เพิ่ม scheduled job: ตรวจสอบ balance ทุกๆ 5 นาที
    scheduler.add_job(check_all_accounts_balance, 'interval', minutes=5, id='balance_monitor')
    scheduler.start()

    logger.info("[SCHEDULER] Background scheduler started - Balance monitoring every 5 minutes")

except ImportError:
    logger.warning("[SCHEDULER] APScheduler not installed - Balance monitoring disabled")
    logger.warning("[SCHEDULER] Install with: pip install apscheduler")
except Exception as e:
    logger.error(f"[SCHEDULER] Failed to start scheduler: {e}")


# ==== logging ====
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/trading_bot.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# ==== register trades blueprint + warm buffer à¹ƒà¸™ app context ====
app.register_blueprint(trades_bp)
with app.app_context():
    init_trades()

# ==== data paths (à¸ªà¸³à¸«à¸£à¸±à¸š webhook allowlist / command files) ====
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)
WEBHOOK_ACCOUNTS_FILE = os.path.join(DATA_DIR, "webhook_accounts.json")


def _load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def get_webhook_allowlist():
    """
    à¹‚à¸„à¸£à¸‡à¸ªà¸£à¹‰à¸²à¸‡: [{"account":"111", "nickname":"A", "enabled": true}, ...]
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
    account = str(account).strip()
    for it in get_webhook_allowlist():
        if it["account"] == account and it.get("enabled", True):
            return True
    return False


# =================== auth helpers ===================
def session_login_required(f):
    @wraps(f)
    def _wrap(*args, **kwargs):
        if not session.get('auth'):
            return jsonify({'error': 'Auth required'}), 401
        return f(*args, **kwargs)
    return _wrap


@app.post("/login")
def login_api():
    data = request.get_json(silent=True) or {}
    if data.get("username") == BASIC_USER and data.get("password") == BASIC_PASS:
        session["auth"] = True
        username = data.get("username", "unknown")
        ip = request.remote_addr
        add_system_log('success', f'ðŸ”“ [200] Login successful - User: {username}, IP: {ip}')
        return jsonify({"ok": True})
    username = data.get("username", "unknown")
    ip = request.remote_addr
    add_system_log('warning', f'ðŸ”’ [401] Login failed - User: {username}, IP: {ip}')
    return jsonify({"ok": False, "error": "Invalid credentials"}), 401


# =================== monitor instances ===================
def monitor_instances():
    """
    âœ… à¸›à¸£à¸±à¸šà¸›à¸£à¸¸à¸‡: à¸ªà¹ˆà¸‡ Email à¹€à¸‰à¸žà¸²à¸°à¹€à¸¡à¸·à¹ˆà¸­ Status à¹€à¸›à¸¥à¸µà¹ˆà¸¢à¸™
    - à¹€à¸›à¸´à¸”: Offline â†’ Online
    - à¸›à¸´à¸”: Online â†’ Offline
    """
    # à¹€à¸à¹‡à¸š Status à¹€à¸”à¸´à¸¡
    last_status = {}
    
    while True:
        try:
            accounts = session_manager.get_all_accounts()
            
            for info in accounts:
                account = info["account"]
                nickname = info.get("nickname", "")
                current_db_status = info.get("status", "")
                
                # ⚠️ ถ้า Account เป็น PAUSE ให้ข้ามไป - ไม่เปลี่ยนสถานะ
                if current_db_status == "PAUSE":
                    last_status[account] = "PAUSE"
                    continue

                # ⚠️ ถ้า Account ยังไม่ได้ Activate (Wait for Activate) ให้ข้ามไป
                # ต้องรอ Symbol data จาก EA ก่อนถึงจะเริ่ม monitor Online/Offline
                if current_db_status == "Wait for Activate":
                    last_status[account] = "Wait for Activate"
                    continue

                # เช็ค Status ปัจจุบัน
                is_alive = session_manager.is_instance_alive(account)
                new_status = "Online" if is_alive else "Offline"
                
                # ดึง Status เก่า
                old_status = last_status.get(account, None)
                
                # à¸–à¹‰à¸² Status à¹€à¸›à¸¥à¸µà¹ˆà¸¢à¸™ â†’ à¸ªà¹ˆà¸‡ Email
                if old_status and new_status != old_status:
                    display_name = f"{account} ({nickname})" if nickname else account
                    
                    if new_status == "Offline":
                        # Account à¸›à¸´à¸”
                        email_handler.send_error_alert(
                            f"Account Offline - {display_name}",
                            f"""
MT5 Account went offline:

Account: {account}
Nickname: {nickname or '-'}
Previous Status: {old_status}
Current Status: {new_status}
Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

The MT5 instance has stopped or crashed. Please check the system.
                            """.strip()
                        )
                        add_system_log('warning', f'âš ï¸ Account {account} went offline')
                        logger.warning(f"[STATUS_CHANGE] {account}: {old_status} -> {new_status}")
                        
                    elif new_status == "Online":
                        # Account à¹€à¸›à¸´à¸”
                        email_handler.send_alert(
                            f"Account Online - {display_name}",
                            f"""
MT5 Account is now online:

Account: {account}
Nickname: {nickname or '-'}
Previous Status: {old_status}
Current Status: {new_status}
Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

The MT5 instance has started successfully.
                            """.strip(),
                            priority="low"
                        )
                        add_system_log('success', f'âœ… Account {account} is now online')
                        logger.info(f"[STATUS_CHANGE] {account}: {old_status} -> {new_status}")
                
                # à¸­à¸±à¸›à¹€à¸”à¸• Status à¹ƒà¸™ DB
                session_manager.update_account_status(account, new_status)
                
                # à¸šà¸±à¸™à¸—à¸¶à¸ Status à¸›à¸±à¸ˆà¸ˆà¸¸à¸šà¸±à¸™
                last_status[account] = new_status
            
            time.sleep(30)
            
        except Exception as e:
            logger.error(f"[MONITOR_ERROR] {e}", exc_info=True)
            time.sleep(60)


threading.Thread(target=monitor_instances, daemon=True).start()


# =================== static & errors ===================
@app.errorhandler(405)
def method_not_allowed(_):
    return jsonify({'error': 'Method not allowed'}), 405


@app.errorhandler(404)
def not_found(_):
    return jsonify({'error': 'Endpoint not found'}), 404


@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)


# =================== health & stats ===================
@app.route('/health', methods=['GET', 'HEAD'])
def health_check():
    """à¸ªà¸³à¸«à¸£à¸±à¸šà¸«à¸™à¹‰à¸² Account Management â†’ Usage Statistics"""
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


@app.get("/accounts/stats")
def accounts_stats():
    """à¸—à¸²à¸‡à¹€à¸¥à¸·à¸­à¸à¹€à¸šà¸²à¸à¸§à¹ˆà¸² /health (à¸ªà¹ˆà¸‡à¸•à¸±à¸§à¹€à¸¥à¸‚à¸¥à¹‰à¸§à¸™)"""
    accounts = session_manager.get_all_accounts()
    total = len(accounts)
    online = sum(1 for a in accounts if a.get('status') == 'Online')
    offline = max(total - online, 0)
    return jsonify({'ok': True, 'total': total, 'online': online, 'offline': offline})


# =================== accounts REST ===================
@app.get('/accounts')
@limiter.exempt
@session_login_required
def get_accounts():
    try:
        return jsonify({'accounts': session_manager.get_all_accounts()})
    except Exception as e:
        logger.error(f"[GET_ACCOUNTS_ERROR] {e}")
        return jsonify({'error': str(e)}), 500


@app.post('/accounts')
@session_login_required
def add_account():
    try:
        data = request.get_json() or {}
        account = str(data.get('account', '')).strip()
        nickname = str(data.get('nickname', '')).strip()
        if not account:
            return jsonify({'error': 'Account number is required'}), 400
        if session_manager.account_exists(account):
            add_system_log('warning', f'âš ï¸ [400] Account creation failed - {account} already exists')
            return jsonify({'error': 'Account already exists'}), 400
        # ✅ เปลี่ยนจาก create_instance เป็น add_remote_account
        if session_manager.add_remote_account(account, nickname):
            logger.info(f"[REMOTE_ACCOUNT_ADDED] {account} ({nickname})")
            add_system_log('success', f'✅ Account {account} added (waiting for EA connection)')
            return jsonify({
                'success': True,
                'message': 'Account added successfully. Status: Wait for Activate'
            })
        return jsonify({'error': 'Failed to add account'}), 500
    except Exception as e:
        logger.error(f"[ADD_ACCOUNT_ERROR] {e}")
        return jsonify({'error': str(e)}), 500


@app.post('/accounts/<account>/restart')
@session_login_required
def restart_account(account):
    return jsonify({'error': 'Not available in remote mode'}), 400


@app.post('/accounts/<account>/stop')
@session_login_required
def stop_account(account):
    return jsonify({'error': 'Not available in remote mode'}), 400


@app.post('/accounts/<account>/open')
@session_login_required
def open_account(account):
    return jsonify({'error': 'Not available in remote mode'}), 400


@app.post('/accounts/<account>/pause')
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
        add_system_log('warning', f'⏸️ [200] Account paused: {account}')

        return jsonify({
            'success': True,
            'message': 'Account paused successfully'
        }), 200
    except Exception as e:
        logger.error(f"[PAUSE_ACCOUNT_ERROR] {e}")
        return jsonify({'error': str(e)}), 500


@app.post('/accounts/<account>/resume')
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
        add_system_log('success', f'▶️ [200] Account resumed: {account}')

        return jsonify({
            'success': True,
            'message': 'Account resumed successfully'
        }), 200
    except Exception as e:
        logger.error(f"[RESUME_ACCOUNT_ERROR] {e}")
        return jsonify({'error': str(e)}), 500


@app.delete('/accounts/<account>')
@session_login_required
def delete_account(account):
    """à¸¥à¸šà¸šà¸±à¸à¸Šà¸µ Master/Slave à¸ˆà¸£à¸´à¸‡ à¹à¸¥à¸°à¸¥à¹‰à¸²à¸‡ history/allowlist (à¸–à¹‰à¸²à¸¡à¸µ)"""
    try:
        account = str(account)
        ok = session_manager.delete_account(account)
        app.logger.info(f'[DELETE_ACCOUNT] account={account} ok={ok}')
        if ok:
            # à¹€à¸à¹‡à¸š logic à¹€à¸”à¸´à¸¡à¹„à¸§à¹‰ (history/allowlist) à¹à¸•à¹ˆà¹„à¸¡à¹ˆà¹ƒà¸«à¹‰ error à¸—à¸³à¹ƒà¸«à¹‰à¸¥à¹‰à¸¡
            cleanup_logs = []

            # 1. Delete trade history
            try:
                deleted = delete_account_history(account)
                app.logger.info(f'[HISTORY_DELETED] {deleted} events for {account}')
                cleanup_logs.append(f'{deleted} history records')
            except Exception as e:
                app.logger.warning(f'[HISTORY_DELETE_ERROR] {e}')

            # 2. Remove from webhook_accounts.json
            try:
                webhook_list = get_webhook_allowlist()
                original_count = len(webhook_list)
                webhook_list = [it for it in webhook_list if it["account"] != account]
                if len(webhook_list) < original_count:
                    _save_json(WEBHOOK_ACCOUNTS_FILE, webhook_list)
                    app.logger.info(f'[WEBHOOK_CLEANUP] Removed account {account} from webhook accounts')
                    cleanup_logs.append('webhook account')
            except Exception as e:
                app.logger.warning(f'[WEBHOOK_CLEANUP_ERROR] {e}')

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
                        app.logger.info(f'[MASTER_CLEANUP] Removed account {account} from master accounts')
                        cleanup_logs.append('master account')
            except Exception as e:
                app.logger.warning(f'[MASTER_CLEANUP_ERROR] {e}')

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
                        app.logger.info(f'[SLAVE_CLEANUP] Removed account {account} from slave accounts')
                        cleanup_logs.append('slave account')
            except Exception as e:
                app.logger.warning(f'[SLAVE_CLEANUP_ERROR] {e}')

            # 5. Delete copy pairs that use this account
            deleted_pairs_count = 0
            try:
                deleted_pairs_count = copy_manager.delete_pairs_by_account(account)
                if deleted_pairs_count > 0:
                    app.logger.info(f'[PAIR_CLEANUP] Deleted {deleted_pairs_count} pairs for account {account}')
                    cleanup_logs.append(f'{deleted_pairs_count} pairs deleted')
            except Exception as e:
                app.logger.warning(f'[PAIR_CLEANUP_ERROR] {e}')

            # 6. Delete copy trading history for this account
            deleted_history_count = 0
            try:
                deleted_history_count = copy_history.delete_by_account(account)
                if deleted_history_count > 0:
                    app.logger.info(f'[HISTORY_CLEANUP] Deleted {deleted_history_count} copy history events for account {account}')
                    cleanup_logs.append(f'{deleted_history_count} copy history events')
            except Exception as e:
                app.logger.warning(f'[COPY_HISTORY_CLEANUP_ERROR] {e}')

            # Log summary
            if cleanup_logs:
                cleanup_summary = ', '.join(cleanup_logs)
                add_system_log('warning', f'🗑️ [200] Account deleted: {account} (cleaned: {cleanup_summary})')
            else:
                add_system_log('warning', f'🗑️ [200] Account deleted: {account}')

            return jsonify({
                'ok': True,
                'deleted_pairs': deleted_pairs_count,
                'message': f'Account deleted with {deleted_pairs_count} copy pair(s) removed'
            }), 200
        else:
            return jsonify({'ok': False}), 200
    except Exception as e:
        app.logger.exception('[DELETE_ACCOUNT_ERROR]')
        return jsonify({'ok': False, 'error': str(e)}), 500


# =================== webhook mgmt (allowlist) ===================
@app.get("/webhook-accounts")
@session_login_required
def list_webhook_accounts():
    return jsonify({"accounts": get_webhook_allowlist()})


@app.post("/webhook-accounts")
@session_login_required
def add_webhook_account():
    data = request.get_json(silent=True) or {}
    account = str(data.get("account") or data.get("id") or "").strip()
    if not account:
        add_system_log('error', '❌ [400] Webhook account creation failed - Account number required')
        return jsonify({"error": "account required"}), 400
    nickname = str(data.get("nickname") or "").strip()
    enabled = bool(data.get("enabled", True))

    # ถ้า account ยังไม่มีใน Account Management ให้สร้างใหม่
    if not session_manager.account_exists(account):
        if not session_manager.add_remote_account(account, nickname):
            return jsonify({'error': f'Failed to create account {account}'}), 500
        logger.info(f"[API] Created new account in Account Management: {account}")

    lst = get_webhook_allowlist()
    found = False
    for it in lst:
        if it["account"] == account:
            it["nickname"] = nickname or it.get("nickname", "")
            it["enabled"] = enabled
            found = True
            break
    if not found:
        lst.append({"account": account, "nickname": nickname, "enabled": enabled})

    _save_json(WEBHOOK_ACCOUNTS_FILE, lst)
    status_text = "updated" if found else "added"
    add_system_log('success', f'✅ [200] Webhook account {status_text}: {account} ({nickname})')
    return jsonify({"ok": True, "account": account})




@app.delete("/webhook-accounts/<account>")
@session_login_required
def delete_webhook_account(account):
    lst = [it for it in get_webhook_allowlist() if it["account"] != str(account)]
    _save_json(WEBHOOK_ACCOUNTS_FILE, lst)
    add_system_log('warning', f'ðŸ—‘ï¸ [200] Webhook account removed: {account}')
    return jsonify({"ok": True})


# =================== webhook basics ===================
@app.get('/webhook-url')
@session_login_required
def get_webhook_url():
    return jsonify({'url': f"{EXTERNAL_BASE_URL}/webhook/{WEBHOOK_TOKEN}"})


@app.get('/webhook')
@app.get('/webhook/')
def webhook_info():
    return jsonify({
        'message': 'Webhook endpoint active',
        'supported_methods': ['POST'],
        'health_check': '/webhook/health',
        'endpoint_format': '/webhook/{token}',
        'supported_actions': ['BUY', 'SELL', 'LONG', 'SHORT', 'CALL', 'PUT', 'CLOSE', 'CLOSE_ALL', 'CLOSE_SYMBOL'],
        'timestamp': datetime.now().isoformat()
    })


@app.get('/webhook/health')
def webhook_health():
    return jsonify({'status': 'ok', 'webhook_status': 'active', 'timestamp': datetime.now().isoformat()})


# =================== webhook handler (à¹€à¸Šà¹‡à¸„ allowlist) ===================
# =================== webhook handler (à¹€à¸Šà¹‡à¸„ allowlist) ===================

@app.post('/webhook/<token>')
@limiter.limit("10 per minute")
def webhook_handler(token):
    if token != WEBHOOK_TOKEN:
        logger.warning("[UNAUTHORIZED] invalid webhook token")
        add_system_log('error', 'ðŸ”’ [401] Webhook unauthorized - Invalid token')
        email_handler.send_alert("Unauthorized Webhook Access", "Invalid token")
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        data = request.get_json()
        if not data:
            raise ValueError("No JSON data received")
    except Exception as e:
        logger.error(f"[BAD_PAYLOAD] {e}")
        add_system_log('error', f'âŒ [400] Webhook bad request - Invalid JSON: {str(e)[:80]}')
        email_handler.send_alert("Bad Webhook Payload", f"Invalid JSON: {e}")

        # พยายามดึงข้อมูลจาก raw request data
        raw_data = request.get_data(as_text=True)
        account = '-'
        action = 'UNKNOWN'
        symbol = '-'
        volume = ''
        price = ''
        tp = ''
        sl = ''

        # พยายาม parse แบบหละหลวม
        try:
            import re
            # ดึง account number
            acc_match = re.search(r'"account(?:_number)?"\s*:\s*"?(\d+)"?', raw_data)
            if acc_match:
                account = acc_match.group(1)

            # ดึง action
            action_match = re.search(r'"action"\s*:\s*"([^"]+)"', raw_data)
            if action_match:
                action = action_match.group(1).upper()

            # ดึง symbol
            symbol_match = re.search(r'"symbol"\s*:\s*"([^"]+)"', raw_data)
            if symbol_match:
                symbol = symbol_match.group(1)

            # ดึง volume
            vol_match = re.search(r'"volume"\s*:\s*"?([0-9.]+)"?', raw_data)
            if vol_match:
                volume = vol_match.group(1)

            # ดึง price
            price_match = re.search(r'"price"\s*:\s*"?([0-9.]+)"?', raw_data)
            if price_match:
                price = price_match.group(1)

            # ดึง take_profit / tp
            tp_match = re.search(r'"(?:take_profit|tp)"\s*:\s*"?([0-9.]+)"?', raw_data)
            if tp_match:
                tp = tp_match.group(1)

            # ดึง stop_loss / sl
            sl_match = re.search(r'"(?:stop_loss|sl)"\s*:\s*"?([0-9.]+)"?', raw_data)
            if sl_match:
                sl = sl_match.group(1)
        except:
            pass

        # บันทึก Invalid JSON Error ลง Trading History
        record_and_broadcast({
            'status': 'error',
            'action': action,
            'symbol': symbol,
            'account': account,
            'volume': volume,
            'price': price,
            'tp': tp,
            'sl': sl,
            'message': 'Invalid JSON'
        })

        return jsonify({'error': 'Invalid JSON payload'}), 400

    logger.info(f"[WEBHOOK] {json.dumps(data, ensure_ascii=False)}")
    action = str(data.get('action', 'UNKNOWN')).upper()
    symbol = data.get('symbol', '-')
    volume = data.get('volume', '-')
    account = data.get('account_number') or (data.get('accounts', [None])[0] if data.get('accounts') else '-')
    add_system_log('info', f'ðŸ“¥ [200] Webhook received: {action} {symbol} Vol:{volume} Acc:{account}')

    valid = validate_webhook_payload(data)
    if not valid["valid"]:
        logger.error(f"[BAD_PAYLOAD] {valid['error']}")
        add_system_log('error', f'âŒ [400] Webhook validation failed: {valid["error"][:80]}')
        email_handler.send_alert("Bad Webhook Payload", f"Validation failed: {valid['error']}")
        return jsonify({'error': valid['error']}), 400

    # ============= Global Secret Key Validation =============
    # ตรวจสอบ Global Secret Key (ใช้ครั้งเดียวสำหรับทุก account)
    provided_secret = data.get('secret', '')
    if not session_manager.validate_global_secret(provided_secret):
        logger.warning("[UNAUTHORIZED] Invalid global secret key")
        add_system_log('error', '🔐 [403] Webhook unauthorized - Invalid global secret key')
        email_handler.send_alert("Webhook Secret Key Validation Failed",
                               "Invalid global secret key provided in webhook request")
        return jsonify({'error': 'Unauthorized - Invalid secret key'}), 403

    logger.info("[SECRET_VALIDATED] ✅ Global secret key validated")

    # ดึง account สำหรับ Symbol Mapping
    account_for_mapping = None
    if isinstance(data.get('account_number'), (str, int)):
        account_for_mapping = str(data.get('account_number')).strip()
    elif isinstance(data.get('accounts'), list) and len(data.get('accounts')) > 0:
        account_for_mapping = str(data['accounts'][0]).strip()

    # ============= Symbol Mapping =============
    # แปลง Symbol ตาม mapping ที่ตั้งไว้ (ถ้ามี)
    if account_for_mapping and 'symbol' in data:
        original_symbol = data['symbol']
        mapped_symbol = session_manager.map_symbol(account_for_mapping, original_symbol)

        if mapped_symbol != original_symbol:
            data['symbol'] = mapped_symbol
            logger.info(f"[SYMBOL_MAPPED] {original_symbol} → {mapped_symbol} for account {account_for_mapping}")
            add_system_log('info', f'🔄 Symbol mapped: {original_symbol} → {mapped_symbol} (Acc: {account_for_mapping})')
    # ⭐ Translate symbol for target account (immediately after token & payload validation)
    try:
        account = None
        if isinstance(data.get('account_number'), (str, int)):
            account = str(data.get('account_number')).strip()
        elif isinstance(data.get('accounts'), list) and len(data.get('accounts')) == 1:
            account = str(data['accounts'][0]).strip()
        if account and 'symbol' in data:
            translated_signal = signal_translator.translate_for_account(
                data,
                account,
                auto_map_symbol=True
            )
            if not translated_signal:
                logger.warning(f"[WEBHOOK] Symbol {data.get('symbol')} not available in account {account}")
                add_system_log('error', f'❌ [400] Symbol not available')
                return jsonify({'error': 'Symbol not available in target account'}), 400
            data['symbol'] = translated_signal.get('symbol', data['symbol'])
            data['original_symbol'] = translated_signal.get('original_symbol')
    except Exception as _e_tr:
        logger.error(f"[WEBHOOK_TRANSLATE_ERROR] {_e_tr}", exc_info=True)


    # ✅ อัพเดท heartbeat สำหรับบัญชีที่ส่ง webhook มา
    account = data.get('account_number') or (data.get('accounts', [None])[0] if data.get('accounts') else None)
    if account:
        session_manager.update_account_heartbeat(str(account))

    # target accounts
    target_accounts = data.get('accounts') or [data.get('account_number')]

    allowed, blocked = [], []

    # âœ… à¸•à¸£à¸§à¸ˆà¸ªà¸­à¸šà¹à¸•à¹ˆà¸¥à¸° account à¸§à¹ˆà¸²à¸­à¸¢à¸¹à¹ˆà¹ƒà¸™ Webhook Management à¸«à¸£à¸·à¸­à¹„à¸¡à¹ˆ
    for acc in target_accounts:
        acc_str = str(acc).strip()

        if not is_account_allowed_for_webhook(acc_str):
            blocked.append(acc_str)

            # ðŸ”´ à¸šà¸±à¸™à¸—à¸¶à¸ Error à¸¥à¸‡ Trade History
            record_and_broadcast({
                'status': 'error',
                'action': str(data.get('action', 'UNKNOWN')).upper(),
                'symbol': data.get('symbol', '-'),
                'account': acc_str,
                'volume': data.get('volume', ''),
                'price': data.get('price', ''),
                'tp': data.get('take_profit', ''),
                'sl': data.get('stop_loss', ''),
                'message': 'Account not in Webhook Management'
            })

            logger.error(f"[WEBHOOK_ERROR] Account {acc_str} not in Webhook Management")
            add_system_log('warning', f'âš ï¸ [403] Webhook blocked - Account {acc_str} not in whitelist')

            continue

        # Check if account is PAUSED
        account_info = session_manager.get_account_info(acc_str)
        if account_info and account_info.get("status") == "PAUSE":
            blocked.append(acc_str)
            record_and_broadcast({
                "status": "error",
                "action": str(data.get("action", "UNKNOWN")).upper(),
                "symbol": data.get("symbol", "-"),
                "account": acc_str,
                "volume": data.get("volume", ""),
                "price": data.get("price", ""),
                "tp": data.get("take_profit", ""),
                "sl": data.get("stop_loss", ""),
                "message": "Account Paused"
            })
            logger.warning(f"[WEBHOOK_BLOCKED] Account {acc_str} is PAUSED")
            add_system_log("warning", f"[403] Webhook blocked - Account {acc_str} is paused")
            continue

        # ⚠️ Check if account can receive orders (must have received Symbol data)
        can_receive, reason = session_manager.can_receive_orders(acc_str)
        if not can_receive:
            blocked.append(acc_str)
            record_and_broadcast({
                "status": "error",
                "action": str(data.get("action", "UNKNOWN")).upper(),
                "symbol": data.get("symbol", "-"),
                "account": acc_str,
                "volume": data.get("volume", ""),
                "price": data.get("price", ""),
                "tp": data.get("take_profit", ""),
                "sl": data.get("stop_loss", ""),
                "message": f"{reason}"
            })
            logger.warning(f"[WEBHOOK_BLOCKED] Account {acc_str} cannot receive orders: {reason}")
            add_system_log("warning", f"[403] Webhook blocked - Account {acc_str}: {reason}")
            continue

        # Account is allowed and not paused
        allowed.append(acc_str)
    if not allowed:
        error_msg = f"No allowed accounts for webhook. Blocked: {', '.join(blocked)}"
        logger.error(f"[WEBHOOK_ERROR] {error_msg}")
        add_system_log('error', f'âŒ [400] Webhook rejected - All accounts blocked ({len(blocked)} accounts)')
        return jsonify({'error': error_msg}), 400

    # à¸ªà¹ˆà¸‡à¸•à¹ˆà¸­à¹€à¸‰à¸žà¸²à¸°à¸šà¸±à¸à¸Šà¸µà¸—à¸µà¹ˆà¸œà¹ˆà¸²à¸™à¸à¸²à¸£à¸­à¸™à¸¸à¸¡à¸±à¸•à¸´
    data_processed = dict(data)
    if 'accounts' in data_processed:
        data_processed['accounts'] = allowed
    else:
        data_processed['account_number'] = allowed[0]


    result = process_webhook(data_processed)

    if result.get('success'):
        msg = result.get('message', 'Processed')
        action = data_processed.get('action', 'UNKNOWN')
        symbol = data_processed.get('symbol', '-')
        volume = data_processed.get('volume', '-')
        add_system_log('success', f'âœ… [200] Webhook processed: {action} {symbol} Vol:{volume} â†’ {len(allowed)} account(s)')
        if blocked:
            msg += f" (âš ï¸ Blocked {len(blocked)} account(s): {', '.join(blocked)})"
            add_system_log('warning', f'âš ï¸ Webhook partial: {len(blocked)} account(s) blocked')
        return jsonify({'success': True, 'message': msg})
    else:
        error_msg = result.get('error', 'Unknown error')
        add_system_log('error', f'âŒ [500] Webhook processing failed: {error_msg[:80]}')
        return jsonify({'error': result.get('error', 'Processing failed')}), 500

    try:
        data = request.get_json()
        if not data:
            raise ValueError("No JSON data received")
    except Exception as e:
        logger.error(f"[BAD_PAYLOAD] {e}")
        add_system_log('error', f'âŒ [400] Webhook bad request - Invalid JSON: {str(e)[:80]}')
        email_handler.send_alert("Bad Webhook Payload", f"Invalid JSON: {e}")

        # พยายามดึงข้อมูลจาก raw request data
        raw_data = request.get_data(as_text=True)
        account = '-'
        action = 'UNKNOWN'
        symbol = '-'
        volume = ''
        price = ''
        tp = ''
        sl = ''

        # พยายาม parse แบบหละหลวม
        try:
            import re
            # ดึง account number
            acc_match = re.search(r'"account(?:_number)?"\s*:\s*"?(\d+)"?', raw_data)
            if acc_match:
                account = acc_match.group(1)

            # ดึง action
            action_match = re.search(r'"action"\s*:\s*"([^"]+)"', raw_data)
            if action_match:
                action = action_match.group(1).upper()

            # ดึง symbol
            symbol_match = re.search(r'"symbol"\s*:\s*"([^"]+)"', raw_data)
            if symbol_match:
                symbol = symbol_match.group(1)

            # ดึง volume
            vol_match = re.search(r'"volume"\s*:\s*"?([0-9.]+)"?', raw_data)
            if vol_match:
                volume = vol_match.group(1)

            # ดึง price
            price_match = re.search(r'"price"\s*:\s*"?([0-9.]+)"?', raw_data)
            if price_match:
                price = price_match.group(1)

            # ดึง take_profit / tp
            tp_match = re.search(r'"(?:take_profit|tp)"\s*:\s*"?([0-9.]+)"?', raw_data)
            if tp_match:
                tp = tp_match.group(1)

            # ดึง stop_loss / sl
            sl_match = re.search(r'"(?:stop_loss|sl)"\s*:\s*"?([0-9.]+)"?', raw_data)
            if sl_match:
                sl = sl_match.group(1)
        except:
            pass

        # บันทึก Invalid JSON Error ลง Trading History
        record_and_broadcast({
            'status': 'error',
            'action': action,
            'symbol': symbol,
            'account': account,
            'volume': volume,
            'price': price,
            'tp': tp,
            'sl': sl,
            'message': 'Invalid JSON'
        })

        return jsonify({'error': 'Invalid JSON payload'}), 400

    logger.info(f"[WEBHOOK] {json.dumps(data, ensure_ascii=False)}")

    valid = validate_webhook_payload(data)
    if not valid["valid"]:
        logger.error(f"[BAD_PAYLOAD] {valid['error']}")
        add_system_log('error', f'âŒ [400] Webhook validation failed: {valid["error"][:80]}')
        email_handler.send_alert("Bad Webhook Payload", f"Validation failed: {valid['error']}")
        return jsonify({'error': valid['error']}), 400

    # target accounts (à¸£à¸­à¸‡à¸£à¸±à¸š accounts: [] à¸«à¸£à¸·à¸­ account_number à¹€à¸”à¸µà¹ˆà¸¢à¸§)
    target_accounts = data.get('accounts') or [data.get('account_number')]

    allowed, blocked = [], []
    for acc in target_accounts:
        if is_account_allowed_for_webhook(acc):
            allowed.append(acc)
        else:
            blocked.append(acc)
            record_and_broadcast({
                'status': 'error', 'action': str(data.get('action')).upper(),
                'symbol': data.get('symbol', '-'), 'account': str(acc),
                'volume': data.get('volume', ''), 'price': data.get('price', ''),
                'tp': data.get('take_profit', ''), 'sl': data.get('stop_loss', ''),
                'message': 'Account not allowed in Webhook Management'
            })

    if not allowed:
        return jsonify({'error': 'No allowed accounts for webhook'}), 400

    # à¸ªà¹ˆà¸‡à¸•à¹ˆà¸­à¹€à¸‰à¸žà¸²à¸°à¸šà¸±à¸à¸Šà¸µà¸—à¸µà¹ˆà¸œà¹ˆà¸²à¸™à¸à¸²à¸£à¸­à¸™à¸¸à¸à¸²à¸•
    data_processed = dict(data)
    if 'accounts' in data_processed:
        data_processed['accounts'] = allowed
    else:
        data_processed['account_number'] = allowed[0]

    result = process_webhook(data_processed)
    if result.get('success'):
        msg = result.get('message', 'Processed')
        if blocked:
            msg += f" (blocked {len(blocked)} account(s))"
        return jsonify({'success': True, 'message': msg})
    else:
        return jsonify({'error': result.get('error', 'Processing failed')}), 500

# =================== Broker Data Registration ===================

@app.post('/api/broker/register')
@limiter.limit("10 per minute")
def register_broker_data():
    """
    รับข้อมูลโบรกเกอร์จาก EA (Scanner)
    
    Payload:
    {
        "account": "12345678",
        "broker": "XM Global",
        "server": "XMGlobal-Real 1",
        "symbols": [
            {
                "name": "EURUSD",
                "contract_size": 100000,
                "volume_min": 0.01,
                "volume_max": 100.0,
                "volume_step": 0.01
            }
        ]
    }
    """
    try:
        data = request.get_json(force=True)
        
        account = str(data.get('account', '')).strip()
        
        if not account:
            logger.warning("[BROKER_REGISTER] Account number missing")
            return jsonify({'error': 'Account number required'}), 400
        
        # บันทึกข้อมูล
        success = broker_manager.save_broker_info(account, data)

        if success:
            symbol_count = len(data.get('symbols', []))
            broker_name = data.get('broker', 'Unknown')

            # ✅ Activate account เมื่อได้รับ Symbol data
            # นี่คือสิ่งที่ทำให้ account เปลี่ยนจาก "Wait for Activate" → "Online"
            if symbol_count > 0 and session_manager.account_exists(account):
                first_symbol = data.get('symbols', [{}])[0].get('name', '')
                account_info = session_manager.get_account_info(account)
                was_waiting = account_info and account_info.get('status') == 'Wait for Activate'

                session_manager.activate_by_symbol(account, broker_name, first_symbol)

                if was_waiting:
                    add_system_log('success', f'🟢 [EA] Account {account} activated by Symbol data (Broker: {broker_name}, {symbol_count} symbols)')
                    logger.info(f"[BROKER_REGISTER] ✅ Account {account} ACTIVATED by Symbol data")

                    # ส่ง email แจ้งเตือน
                    email_handler.send_alert(
                        "Account Activated by Symbol",
                        f"Account {account} activated by Symbol data\nBroker: {broker_name}\nSymbols: {symbol_count}"
                    )

            add_system_log(
                'success',
                f'✅ [200] Broker data registered: Account {account} '
                f'({broker_name}, {symbol_count} symbols)'
            )
            
            return jsonify({
                'success': True,
                'message': f'Broker data saved for account {account}',
                'symbol_count': symbol_count
            }), 200
        else:
            return jsonify({'error': 'Failed to save broker data'}), 500
            
    except Exception as e:
        logger.error(f"[BROKER_REGISTER] Error: {e}", exc_info=True)
        add_system_log('error', f'❌ [500] Broker data registration failed: {str(e)}')
        return jsonify({'error': str(e)}), 500


@app.get('/api/broker/<account>')
@session_login_required
def get_broker_data(account):
    """ดึงข้อมูลโบรกเกอร์ของบัญชี"""
    try:
        broker_info = broker_manager.get_broker_info(account)
        
        if broker_info:
            return jsonify({'success': True, 'data': broker_info}), 200
        else:
            return jsonify({'error': 'Broker data not found'}), 404
            
    except Exception as e:
        logger.error(f"[BROKER_DATA] Error: {e}")
        return jsonify({'error': str(e)}), 500


@app.get('/api/broker/stats')
@session_login_required
def get_broker_stats():
    """ดึงสถิติข้อมูลโบรกเกอร์"""
    try:
        stats = broker_manager.get_stats()
        return jsonify({'success': True, 'stats': stats}), 200
    except Exception as e:
        logger.error(f"[BROKER_STATS] Error: {e}")
        return jsonify({'error': str(e)}), 500


# =================== Account Balance API ===================

@app.post('/api/account/balance')
@limiter.limit("60 per minute")
def update_account_balance():
    """
    รับข้อมูล account balance จาก EA

    Payload:
    {
        "account": "12345678",
        "balance": 10000.50,
        "equity": 10050.25,
        "margin": 500.00,
        "free_margin": 9550.25,
        "currency": "USD"
    }
    """
    try:
        data = request.get_json(force=True)

        account = str(data.get('account', '')).strip()
        balance = data.get('balance')

        if not account:
            logger.warning("[BALANCE_UPDATE] Account number missing")
            return jsonify({'error': 'Account number required'}), 400

        if balance is None:
            logger.warning("[BALANCE_UPDATE] Balance missing")
            return jsonify({'error': 'Balance required'}), 400

        try:
            balance = float(balance)
        except (ValueError, TypeError):
            logger.warning(f"[BALANCE_UPDATE] Invalid balance value: {balance}")
            return jsonify({'error': 'Balance must be a number'}), 400

        # อัพเดท balance
        success = balance_manager.update_balance(
            account=account,
            balance=balance,
            equity=data.get('equity'),
            margin=data.get('margin'),
            free_margin=data.get('free_margin'),
            currency=data.get('currency')
        )

        if success:
            logger.info(
                f"[BALANCE_UPDATE] ✅ Account {account} "
                f"Balance={balance:.2f} Currency={data.get('currency', 'N/A')}"
            )

            return jsonify({
                'success': True,
                'message': f'Balance updated for account {account}'
            }), 200
        else:
            return jsonify({'error': 'Failed to update balance'}), 500

    except Exception as e:
        logger.error(f"[BALANCE_UPDATE] Error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.get('/api/account/<account>/balance')
@session_login_required
def get_account_balance(account):
    """ดึงข้อมูล balance ของ account"""
    try:
        balance_info = balance_manager.get_balance_info(account)

        if balance_info:
            return jsonify({'success': True, 'data': balance_info}), 200
        else:
            return jsonify({'error': 'Balance data not found or expired'}), 404

    except Exception as e:
        logger.error(f"[BALANCE_GET] Error: {e}")
        return jsonify({'error': str(e)}), 500


@app.get('/api/account/balance/all')
@session_login_required
def get_all_account_balances():
    """ดึงข้อมูล balance ของทุก account"""
    try:
        balances = balance_manager.get_all_balances()
        return jsonify({'success': True, 'data': balances}), 200
    except Exception as e:
        logger.error(f"[BALANCE_GET_ALL] Error: {e}")
        return jsonify({'error': str(e)}), 500


@app.get('/api/account/balance/status')
@session_login_required
def get_balance_manager_status():
    """ดึงสถานะของ Balance Manager"""
    try:
        status = balance_manager.get_status()
        return jsonify({'success': True, 'status': status}), 200
    except Exception as e:
        logger.error(f"[BALANCE_STATUS] Error: {e}")
        return jsonify({'error': str(e)}), 500


# =================== webhook utils ===================
def normalize_action(action: str) -> str:
    """
    Normalize action aliases to standard actions
    - CALL -> BUY
    - PUT -> SELL
    """
    if not action:
        return action

    action_upper = str(action).upper().strip()

    # Action aliases mapping
    action_aliases = {
        'CALL': 'BUY',
        'PUT': 'SELL',
    }

    return action_aliases.get(action_upper, action_upper)


def validate_webhook_payload(data):
    required_fields = ['action']
    if 'account_number' not in data and 'accounts' not in data:
        return {'valid': False, 'error': 'Missing field: account_number or accounts'}
    for field in required_fields:
        if field not in data:
            return {'valid': False, 'error': f'Missing field: {field}'}

    # Normalize action aliases (call->buy, put->sell)
    action = normalize_action(data['action'])
    data['action'] = action  # Update data with normalized action
    if action in ['BUY', 'SELL', 'LONG', 'SHORT']:
        if 'symbol' not in data:
            return {'valid': False, 'error': 'symbol required for trading actions'}
        if 'volume' not in data:
            return {'valid': False, 'error': 'volume required for trading actions'}
        data.setdefault('order_type', 'market')
        order_type = str(data.get('order_type', 'market')).lower()
        if order_type in ['limit', 'stop'] and 'price' not in data:
            return {'valid': False, 'error': f'price required for {order_type} orders'}
        try:
            vol = float(data['volume'])
            if vol <= 0:
                return {'valid': False, 'error': 'Volume must be positive'}
        except Exception:
            return {'valid': False, 'error': 'Volume must be a number'}

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
        if 'volume' in data:
            try:
                vol = float(data['volume'])
                if vol <= 0:
                    return {'valid': False, 'error': 'Volume must be positive'}
            except Exception:
                return {'valid': False, 'error': 'Volume must be a number'}
        if 'position_type' in data:
            pt = str(data['position_type']).upper()
            if pt not in ['BUY', 'SELL']:
                return {'valid': False, 'error': 'position_type must be BUY or SELL'}
    else:
        return {'valid': False, 'error': 'Invalid action. Must be one of: BUY, SELL, LONG, SHORT, CALL, PUT, CLOSE, CLOSE_ALL, CLOSE_SYMBOL'}

    return {'valid': True}


# =================== webhook core ===================
def process_webhook(data):
    """
    à¸ªà¹ˆà¸‡à¸„à¸³à¸ªà¸±à¹ˆà¸‡à¹„à¸›à¸¢à¸±à¸‡ EA à¸•à¸²à¸¡ accounts à¸—à¸µà¹ˆà¸à¸³à¸«à¸™à¸” à¸žà¸£à¹‰à¸­à¸¡à¸šà¸±à¸™à¸—à¸¶à¸à¸¥à¸‡ history
    """
    try:
        target_accounts = data['accounts'] if 'accounts' in data else [data['account_number']]
        action = str(data['action']).upper()

                # ✅ ใช้ symbol ที่ translate แล้วจาก webhook handler
        mapped_symbol = data.get('symbol')  # ใช้ symbol ที่ผ่าน translate แล้ว

        results = []

        for account in target_accounts:
            account_str = str(account).strip()

            # ðŸ”´ 1. à¸•à¸£à¸§à¸ˆà¸ªà¸­à¸šà¸§à¹ˆà¸²à¸šà¸±à¸à¸Šà¸µà¸¡à¸µà¸­à¸¢à¸¹à¹ˆà¹ƒà¸™à¸£à¸°à¸šà¸šà¸«à¸£à¸·à¸­à¹„à¸¡à¹ˆ
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
                    'message': f'âŒ {error_msg}'
                })

                results.append({'account': account_str, 'success': False, 'error': error_msg})
                continue

            # Check status column first (more reliable than heartbeat)
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

            # Backup check: heartbeat
            if not session_manager.is_instance_alive(account_str):
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


            # âœ… à¸šà¸±à¸à¸Šà¸µà¸œà¹ˆà¸²à¸™à¸à¸²à¸£à¸•à¸£à¸§à¸ˆà¸ªà¸­à¸š - à¸ªà¹ˆà¸‡à¸„à¸³à¸ªà¸±à¹ˆà¸‡
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

                results.append({'account': account_str, 'success': True, 'command': cmd, 'action': action})
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
                    'message': f'{error_msg}'
                })

                results.append({'account': account_str, 'success': False, 'error': error_msg})

        # à¸ªà¸£à¸¸à¸›à¸œà¸¥à¸¥à¸±à¸žà¸˜à¹Œ
        success_count = sum(1 for r in results if r['success'])
        total_count = len(results)

        if success_count == total_count:
            return {'success': True, 'message': f'{action} sent to {success_count}/{total_count} accounts'}
        elif success_count > 0:
            return {'success': True, 'message': f'{action} partial success: {success_count}/{total_count} accounts'}
        else:
            return {'success': False, 'error': f'Failed to send {action} to any account'}

    except Exception as e:
        logger.error(f"[WEBHOOK_ERROR] {e}", exc_info=True)
        return {'success': False, 'error': str(e)}

                # ✅ ใช้ symbol ที่ translate แล้วจาก webhook handler
        mapped_symbol = data.get('symbol')  # ใช้ symbol ที่ผ่าน translate แล้ว

        results = []
        for account in target_accounts:
            # à¸•à¸£à¸§à¸ˆà¸§à¹ˆà¸²à¸¡à¸µà¸šà¸±à¸à¸Šà¸µà¹ƒà¸™ server à¹à¸¥à¸° online
            if not session_manager.account_exists(account):
                record_and_broadcast({
                    'status': 'error', 'action': action,
                    'symbol': data.get('symbol', '-'), 'account': account,
                    'volume': data.get('volume', ''), 'price': data.get('price', ''),
                    'tp': data.get('take_profit', ''), 'sl': data.get('stop_loss', ''),
                    'message': 'Account not found'
                })
                results.append({'account': account, 'success': False, 'error': 'Account not found'})
                continue

            if not session_manager.is_instance_alive(account):
                record_and_broadcast({
                    'status': 'error', 'action': action,
                    'symbol': data.get('symbol', '-'), 'account': account,
                    'volume': data.get('volume', ''), 'price': data.get('price', ''),
                    'tp': data.get('take_profit', ''), 'sl': data.get('stop_loss', ''),
                    'message': 'Account is offline'
                })
                results.append({'account': account, 'success': False, 'error': 'Account is offline'})
                continue

            cmd = prepare_trading_command(data, mapped_symbol, account)
            ok = write_command_for_ea(account, cmd)

            if ok:
                record_and_broadcast({
                    'status': 'success', 'action': action,
                    'order_type': data.get('order_type', 'market'),
                    'symbol': mapped_symbol or data.get('symbol', '-'), 'account': account,
                    'volume': data.get('volume', ''), 'price': data.get('price', ''),
                    'tp': data.get('take_profit', ''), 'sl': data.get('stop_loss', ''),
                    'message': f'{action} command sent to EA'
                })

            results.append({'account': account, 'success': bool(ok), 'command': cmd, 'action': action})

        success_count = sum(1 for r in results if r['success'])
        total_count = len(results)
        if success_count == total_count:
            return {'success': True, 'message': f'{action} sent to {success_count}/{total_count} accounts'}
        elif success_count > 0:
            return {'success': True, 'message': f'{action} partial success: {success_count}/{total_count} accounts'}
        else:
            return {'success': False, 'error': f'Failed to send {action} to any account'}

    except Exception as e:
        return {'success': False, 'error': str(e)}


def prepare_trading_command(data, mapped_symbol, account):
    action = str(data['action']).upper()
    # Normalize LONG/SHORT to BUY/SELL for EA compatibility
    if action == 'LONG':
        action = 'BUY'
    elif action == 'SHORT':
        action = 'SELL'

    # Coerce volume to float if possible
    vol = data.get('volume')
    try:
        volume = float(vol) if vol is not None else None
    except Exception:
        volume = vol  # keep original; EA may handle/raise

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




def write_command_for_ea(account, command):
    """
    ส่งคำสั่งไปยัง EA ผ่าน API Command Queue

    EA จะ poll คำสั่งจาก GET /api/commands/<account> แทนการอ่านไฟล์

    Args:
        account: หมายเลขบัญชี
        command: คำสั่งการเทรด (dict)

    Returns:
        bool: True ถ้าส่งสำเร็จ
    """
    try:
        account = str(account)

        # ส่งคำสั่งเข้า Command Queue (API Mode เท่านั้น)
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





# =================== Copy Trading API Endpoints ===================

@app.get('/api/pairs')
@session_login_required
def list_pairs():
    """à¸”à¸¶à¸‡à¸£à¸²à¸¢à¸à¸²à¸£ Copy Pairs à¸—à¸±à¹‰à¸‡à¸«à¸¡à¸” (à¹ƒà¸Šà¹‰à¸•à¸­à¸™à¸£à¸µà¹€à¸Ÿà¸£à¸Šà¸«à¸™à¹‰à¸²)"""
    try:
        # à¸£à¸­à¸‡à¸£à¸±à¸šà¸—à¸±à¹‰à¸‡ list_pairs() à¹à¸¥à¸° get_all_pairs()
        if hasattr(copy_manager, 'list_pairs'):
            pairs = copy_manager.list_pairs()
        else:
            pairs = copy_manager.get_all_pairs()
        return jsonify({'pairs': pairs}), 200
    except Exception as e:
        app.logger.exception('[PAIRS_LIST_ERROR]')
        return jsonify({'error': str(e)}), 500


@app.post('/api/pairs')
@session_login_required
def create_copy_pair():
    """à¸ªà¸£à¹‰à¸²à¸‡ Copy Pair à¹ƒà¸«à¸¡à¹ˆ"""
    try:
        data = request.get_json() or {}

        master = str(data.get('master_account', '')).strip()
        slave = str(data.get('slave_account', '')).strip()

        if not master or not slave:
            return jsonify({'error': 'Master and slave accounts are required'}), 400

        if master == slave:
            add_system_log('error', f'âŒ [400] Copy pair creation failed - Master and slave cannot be the same ({master})')
            return jsonify({'error': 'Master and slave accounts must be different'}), 400

        if not session_manager.account_exists(master):
            add_system_log('error', f'âŒ [404] Copy pair creation failed - Master account {master} not found')
            return jsonify({'error': f'Master account {master} not found'}), 404

        if not session_manager.account_exists(slave):
            add_system_log('error', f'âŒ [404] Copy pair creation failed - Slave account {slave} not found')
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
        add_system_log('success', f'âœ… [201] Copy pair created: {master} â†’ {slave} ({master_nickname} â†’ {slave_nickname})')
        return jsonify({'success': True, 'pair': pair}), 201

    except Exception as e:
        logger.error(f"[API] Create pair error: {e}")
        return jsonify({'error': str(e)}), 500


@app.put('/api/pairs/<pair_id>')
@session_login_required
def update_copy_pair(pair_id):
    """à¸­à¸±à¸›à¹€à¸”à¸• Copy Pair"""
    try:
        data = request.get_json() or {}
        success = copy_manager.update_pair(pair_id, data)

        if success:
            pair = copy_manager.get_pair_by_id(pair_id)
            master = pair.get('master_account', '')
            slave = pair.get('slave_account', '')
            add_system_log('info', f'âœï¸ [200] Copy pair updated: {master} â†’ {slave}')
            return jsonify({'success': True, 'pair': pair})
        else:
            add_system_log('warning', f'âš ï¸ [404] Copy pair update failed - Pair {pair_id} not found')
            return jsonify({'error': 'Pair not found'}), 404

    except Exception as e:
        logger.error(f"[API] Update pair error: {e}")
        return jsonify({'error': str(e)}), 500


@app.delete('/api/pairs/<pair_id>')
@session_login_required
def delete_pair(pair_id):
    """à¸¥à¸š Copy Pair + log + save"""
    try:
        deleted = copy_manager.delete_pair(pair_id)
        if not deleted:
            app.logger.warning(f'[PAIR_DELETE_NOT_FOUND] {pair_id}')
            add_system_log('warning', f'âš ï¸ [404] Copy pair deletion failed - Pair {pair_id} not found')
            return jsonify({'ok': False, 'error': 'Pair not found'}), 404

        app.logger.info(f'[PAIR_DELETE] {pair_id}')
        add_system_log('warning', f'ðŸ—‘ï¸ [200] Copy pair deleted: {pair_id}')
        return jsonify({'ok': True}), 200
    except Exception as e:
        app.logger.exception('[PAIR_DELETE_ERROR]')
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.post('/api/pairs/<pair_id>/toggle')
@session_login_required
def toggle_copy_pair(pair_id):
    """à¹€à¸›à¸´à¸”/à¸›à¸´à¸” Copy Pair"""
    try:
        new_status = copy_manager.toggle_pair_status(pair_id)

        if new_status:
            status_emoji = "âœ…" if new_status == "active" else "â¸ï¸"
            status_text = "enabled" if new_status == "active" else "disabled"
            add_system_log('info', f'{status_emoji} [200] Copy pair {status_text}: {pair_id}')
            return jsonify({'success': True, 'status': new_status})
        else:
            add_system_log('warning', f'âš ï¸ [404] Copy pair toggle failed - Pair {pair_id} not found')
            return jsonify({'error': 'Pair not found'}), 404

    except Exception as e:
        logger.error(f"[API] Toggle pair error: {e}")
        return jsonify({'error': str(e)}), 500




@app.post('/api/pairs/<pair_id>/add-master')
@session_login_required
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
            add_system_log('error', '❌ [400] Add master failed - Account number required')
            return jsonify({'error': 'Master account is required'}), 400
        
        # ตรวจสอบว่า account มีอยู่ใน session_manager หรือไม่
        if not session_manager.account_exists(master_account):
            add_system_log('error', f'❌ [404] Add master failed - Account {master_account} not found')
            return jsonify({'error': f'Master account {master_account} not found'}), 404
        
        # ดึงข้อมูลคู่ที่มีอยู่
        pair = copy_manager.get_pair_by_id(pair_id)
        if not pair:
            add_system_log('error', f'❌ [404] Add master failed - Pair {pair_id} not found')
            return jsonify({'error': 'Pair not found'}), 404
        
        # ใช้ API key จากคู่เดิม
        api_key = pair.get('api_key') or pair.get('apiKey')
        
        # ดึง slaves ทั้งหมดที่ใช้ API key เดียวกัน
        existing_pairs = [p for p in copy_manager.pairs 
                         if (p.get('api_key') or p.get('apiKey')) == api_key]
        
        if not existing_pairs:
            add_system_log('error', f'❌ [404] Add master failed - No existing pairs with API key')
            return jsonify({'error': 'No existing pairs found with this API key'}), 404
        
        # เอา slave แรกมาใช้ (สร้างคู่ใหม่ Master ใหม่ -> Slave เดิม)
        first_slave = existing_pairs[0].get('slave_account')
        settings = existing_pairs[0].get('settings', {})
        
        # ตรวจสอบว่าคู่นี้มีอยู่แล้วหรือไม่
        for p in copy_manager.pairs:
            if (p.get('master_account') == master_account and 
                p.get('slave_account') == first_slave and
                (p.get('api_key') or p.get('apiKey')) == api_key):
                add_system_log('warning', f'⚠️ [400] Add master failed - Pair already exists')
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
        add_system_log('success', f'✅ [201] Master {master_account} added to pair {pair_id}')
        
        return jsonify({'success': True, 'pair': new_pair}), 201
        
    except Exception as e:
        logger.error(f"[API] Add master to pair error: {e}")
        add_system_log('error', f'❌ [500] Add master failed: {str(e)}')
        return jsonify({'error': str(e)}), 500


@app.post('/api/pairs/<pair_id>/add-slave')
@session_login_required
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
            add_system_log('error', '❌ [400] Add slave failed - Account number required')
            return jsonify({'error': 'Slave account is required'}), 400
        
        # ตรวจสอบว่า account มีอยู่ใน session_manager หรือไม่
        if not session_manager.account_exists(slave_account):
            add_system_log('error', f'❌ [404] Add slave failed - Account {slave_account} not found')
            return jsonify({'error': f'Slave account {slave_account} not found'}), 404
        
        # ดึงข้อมูลคู่ที่มีอยู่
        pair = copy_manager.get_pair_by_id(pair_id)
        if not pair:
            add_system_log('error', f'❌ [404] Add slave failed - Pair {pair_id} not found')
            return jsonify({'error': 'Pair not found'}), 404
        
        # ใช้ API key และ master จากคู่เดิม
        api_key = pair.get('api_key') or pair.get('apiKey')
        master_account = pair.get('master_account')
        
        # ตรวจสอบว่าคู่นี้มีอยู่แล้วหรือไม่
        for p in copy_manager.pairs:
            if (p.get('master_account') == master_account and 
                p.get('slave_account') == slave_account and
                (p.get('api_key') or p.get('apiKey')) == api_key):
                add_system_log('warning', f'⚠️ [400] Add slave failed - Pair already exists')
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
        add_system_log('success', f'✅ [201] Slave {slave_account} added to pair {pair_id}')
        
        return jsonify({'success': True, 'pair': new_pair}), 201
        
    except Exception as e:
        logger.error(f"[API] Add slave to pair error: {e}")
        add_system_log('error', f'❌ [500] Add slave failed: {str(e)}')
        return jsonify({'error': str(e)}), 500


# =================== Master/Slave Accounts Management ===================

@app.get('/api/copy/master-accounts')
@session_login_required
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


@app.post('/api/copy/master-accounts')
@session_login_required
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
        add_system_log('success', f'✅ [201] Master account {account} added')

        return jsonify({'success': True, 'account': new_master}), 201

    except Exception as e:
        logger.error(f"[API] Add master account error: {e}")
        add_system_log('error', f'❌ [500] Add master failed: {str(e)}')
        return jsonify({'error': str(e)}), 500


@app.delete('/api/copy/master-accounts/<account_id>')
@session_login_required
def delete_master_account(account_id):
    """ลบ Master Account"""
    try:
        master_file = Path('data/master_accounts.json')
        if not master_file.exists():
            return jsonify({'error': 'No master accounts found'}), 404

        with open(master_file, 'r', encoding='utf-8') as f:
            masters = json.load(f)

        # หา account ที่จะลบ
        original_count = len(masters)
        masters = [m for m in masters if m.get('id') != account_id and m.get('account') != account_id]

        if len(masters) == original_count:
            return jsonify({'error': 'Master account not found'}), 404

        # บันทึก
        with open(master_file, 'w', encoding='utf-8') as f:
            json.dump(masters, f, indent=2, ensure_ascii=False)

        logger.info(f"[API] Deleted master account: {account_id}")
        add_system_log('success', f'✅ [200] Master account {account_id} deleted')

        return jsonify({'success': True})

    except Exception as e:
        logger.error(f"[API] Delete master account error: {e}")
        return jsonify({'error': str(e)}), 500


@app.get('/api/copy/slave-accounts')
@session_login_required
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


@app.post('/api/copy/slave-accounts')
@session_login_required
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
        add_system_log('success', f'✅ [201] Slave account {account} added')

        return jsonify({'success': True, 'account': new_slave}), 201

    except Exception as e:
        logger.error(f"[API] Add slave account error: {e}")
        add_system_log('error', f'❌ [500] Add slave failed: {str(e)}')
        return jsonify({'error': str(e)}), 500


@app.delete('/api/copy/slave-accounts/<account_id>')
@session_login_required
def delete_slave_account(account_id):
    """ลบ Slave Account"""
    try:
        slave_file = Path('data/slave_accounts.json')
        if not slave_file.exists():
            return jsonify({'error': 'No slave accounts found'}), 404

        with open(slave_file, 'r', encoding='utf-8') as f:
            slaves = json.load(f)

        # หา account ที่จะลบ
        original_count = len(slaves)
        slaves = [s for s in slaves if s.get('id') != account_id and s.get('account') != account_id]

        if len(slaves) == original_count:
            return jsonify({'error': 'Slave account not found'}), 404

        # บันทึก
        with open(slave_file, 'w', encoding='utf-8') as f:
            json.dump(slaves, f, indent=2, ensure_ascii=False)

        logger.info(f"[API] Deleted slave account: {account_id}")
        add_system_log('success', f'✅ [200] Slave account {account_id} deleted')

        return jsonify({'success': True})

    except Exception as e:
        logger.error(f"[API] Delete slave account error: {e}")
        return jsonify({'error': str(e)}), 500


# =================== Copy Trading Signal Endpoint ===================



@app.post('/api/copy/trade')
@limiter.limit("100 per minute")
def copy_trade_endpoint():
    """
    Receive trading signal from Master EA (Copy Trading)

    🆕 Version 2.0: รองรับ Multiple Pairs ต่อ API Key
    ใช้ copy_handler.process_master_signal() เพื่อ handle logic ทั้งหมด
    """
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
        add_system_log('info', f'📡 [200] Copy signal received: {action} {symbol} from {account}')

        # 4) Basic validation
        api_key = str(data.get('api_key', '')).strip()
        if not api_key:
            add_system_log('error', '❌ [400] Copy trade failed - API key missing')
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
            add_system_log('error', f'❌ [500] Copy trade failed: {error_msg}')
            return jsonify({'error': error_msg}), 500

        # 6) Success!
        master_account = data.get('account', '-')
        symbol = data.get('symbol', '-')
        volume = data.get('volume', '-')

        add_system_log(
            'success', 
            f'✅ [200] Copy trade executed: {master_account} → Slave ({action} {symbol} Vol:{volume})'
        )

        return jsonify({
            'success': True,
            'message': 'Copy trade executed successfully'
        }), 200

    except Exception as e:
        logger.error(f"[COPY_TRADE_ERROR] {e}", exc_info=True)
        add_system_log('error', f'❌ [500] Copy trade error: {str(e)[:80]}')
        return jsonify({'error': str(e)}), 500
@app.get('/api/copy/history')
@session_login_required
def get_copy_history():
    """à¸”à¸¶à¸‡à¸›à¸£à¸°à¸§à¸±à¸•à¸´à¸à¸²à¸£à¸„à¸±à¸”à¸¥à¸­à¸"""
    try:
        limit = int(request.args.get('limit', 100))
        status = request.args.get('status')

        limit = max(1, min(limit, 1000))

        history = copy_history.get_history(limit=limit, status=status)

        return jsonify({'history': history, 'count': len(history)})

    except Exception as e:
        logger.error(f"[API] Get copy history error: {e}")
        return jsonify({'error': str(e)}), 500


@app.post('/api/copy/history/clear')
@session_login_required
def clear_copy_history():
    """à¸¥à¸šà¸›à¸£à¸°à¸§à¸±à¸•à¸´à¸à¸²à¸£à¸„à¸±à¸”à¸¥à¸­à¸à¸—à¸±à¹‰à¸‡à¸«à¸¡à¸”"""
    try:
        confirm = request.args.get('confirm')
        if confirm != '1':
            add_system_log('warning', 'âš ï¸ [400] Clear history failed - Missing confirmation')
            return jsonify({'error': 'Missing confirm=1'}), 400

        success = copy_history.clear_history()

        if success:
            add_system_log('warning', 'ðŸ—‘ï¸ [200] Copy history cleared')
            return jsonify({'success': True})
        else:
            add_system_log('error', 'âŒ [500] Failed to clear copy history')
            return jsonify({'error': 'Failed to clear history'}), 500

    except Exception as e:
        logger.error(f"[API] Clear copy history error: {e}")
        return jsonify({'error': str(e)}), 500


@app.post('/copy-history/clear')
@session_login_required
def clear_copy_history_legacy():
    """Backward-compat: à¸£à¸­à¸‡à¸£à¸±à¸šà¹€à¸ªà¹‰à¸™à¸—à¸²à¸‡à¹€à¸à¹ˆà¸² /copy-history/clear"""
    try:
        confirm = request.args.get('confirm')
        if confirm != '1':
            add_system_log('warning', 'âš ï¸ [400] Clear history failed - Missing confirmation')
            return jsonify({'error': 'Missing confirm=1'}), 400

        success = copy_history.clear_history()
        if success:
            add_system_log('warning', 'ðŸ—‘ï¸ [200] Copy history cleared')
            return jsonify({'success': True})
        else:
            add_system_log('error', 'âŒ [500] Failed to clear copy history')
            return jsonify({'error': 'Failed to clear history'}), 500
    except Exception as e:
        logger.error(f"[API] Legacy clear copy history error: {e}")
        return jsonify({'error': str(e)}), 500



# =================== Copy Trading SSE ===================

@app.get('/events/copy-trades')
def sse_copy_trades():
    """Server-Sent Events stream à¸ªà¸³à¸«à¸£à¸±à¸š Copy Trading history"""
    from flask import Response, stream_with_context

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


# ==================================================================================
# SETTINGS API (added after Copy Trading API, before __main__)
# ==================================================================================

# Global settings storage (à¹ƒà¸Šà¹‰à¹„à¸Ÿà¸¥à¹Œ JSON à¹à¸—à¸™ database)
SETTINGS_FILE = 'data/settings.json'


def load_settings():
    """à¹‚à¸«à¸¥à¸” settings à¸ˆà¸²à¸à¹„à¸Ÿà¸¥à¹Œ"""
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            # Default settings
            return {
                'rate_limits': {
                    'webhook': '10 per minute',
                    'api': '100 per hour',
                    'command_api': '60 per minute',
                    'last_updated': None
                },
                'email': {
                    'enabled': False,
                    'smtp_server': '',
                    'smtp_port': 587,
                    'smtp_user': '',
                    'smtp_pass': '',
                    'from_email': '',
                    'to_emails': []
                }
            }
    except Exception as e:
        logger.error(f"[SETTINGS] Error loading settings: {e}")
        return {}


def save_settings(settings_data):
    """à¸šà¸±à¸™à¸—à¸¶à¸ settings à¸¥à¸‡à¹„à¸Ÿà¸¥à¹Œ"""
    try:
        os.makedirs('data', exist_ok=True)
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings_data, f, indent=2, ensure_ascii=False)
        logger.info("[SETTINGS] Settings saved successfully")
        return True
    except Exception as e:
        logger.error(f"[SETTINGS] Error saving settings: {e}")
        return False


@app.get('/api/settings')
@session_login_required
def get_all_settings():
    """à¸”à¸¶à¸‡ settings à¸—à¸±à¹‰à¸‡à¸«à¸¡à¸”"""
    try:
        settings = load_settings()
        return jsonify(settings), 200
    except Exception as e:
        logger.error(f"[SETTINGS_API] Error getting settings: {e}")
        return jsonify({'error': str(e)}), 500


@app.post('/api/settings/rate-limits')
@session_login_required
def save_rate_limit_settings():
    """à¸šà¸±à¸™à¸—à¸¶à¸ Rate Limit Settings"""
    try:
        data = request.get_json() or {}
        webhook_limit = data.get('webhook', '').strip()
        api_limit = data.get('api', '').strip()
        command_api_limit = data.get('command_api', '').strip()

        if not webhook_limit or not api_limit or not command_api_limit:
            return jsonify({'error': 'Missing webhook, api, or command_api limit'}), 400

        # Validate format
        import re
        pattern = r'^\d+\s+per\s+(minute|hour|day)$'
        if not re.match(pattern, webhook_limit, re.IGNORECASE):
            add_system_log('error', f'âŒ [400] Rate limit update failed - Invalid webhook format: {webhook_limit}')
            return jsonify({'error': 'Invalid webhook rate limit format'}), 400
        if not re.match(pattern, api_limit, re.IGNORECASE):
            add_system_log('error', f'âŒ [400] Rate limit update failed - Invalid API format: {api_limit}')
            return jsonify({'error': 'Invalid API rate limit format'}), 400
        if not re.match(pattern, command_api_limit, re.IGNORECASE):
            add_system_log('error', f'❌ [400] Rate limit update failed - Invalid command API format: {command_api_limit}')
            return jsonify({'error': 'Invalid command API rate limit format'}), 400

        # Load current settings
        settings = load_settings()
        
        # Update rate limits
        settings['rate_limits'] = {
            'webhook': webhook_limit,
            'api': api_limit,
            'command_api': command_api_limit,
            'last_updated': datetime.now().isoformat()
        }

        # Save settings
        if save_settings(settings):
            logger.info(f"[SETTINGS] Rate limits updated: webhook={webhook_limit}, api={api_limit}, command_api={command_api_limit}")
            add_system_log('info', f'âš™ï¸ [200] Rate limits updated - Webhook: {webhook_limit}, API: {api_limit}, Command API: {command_api_limit}')
            return jsonify({
                'success': True,
                'rate_limits': settings['rate_limits']
            }), 200
        else:
            return jsonify({'error': 'Failed to save settings'}), 500

    except Exception as e:
        logger.error(f"[SETTINGS_API] Error saving rate limits: {e}")
        return jsonify({'error': str(e)}), 500


@app.get('/api/settings/email')
@session_login_required
def get_email_settings():
    """à¸”à¸¶à¸‡ Email Settings"""
    try:
        settings = load_settings()
        email_settings = settings.get('email', {})
        
        # à¹„à¸¡à¹ˆà¸ªà¹ˆà¸‡ password à¸à¸¥à¸±à¸šà¹„à¸›à¹ƒà¸«à¹‰ frontend
        email_settings_safe = email_settings.copy()
        if 'smtp_pass' in email_settings_safe:
            email_settings_safe['smtp_pass'] = '********' if email_settings.get('smtp_pass') else ''
        
        return jsonify(email_settings_safe), 200
    except Exception as e:
        logger.error(f"[SETTINGS_API] Error getting email settings: {e}")
        return jsonify({'error': str(e)}), 500


@app.post('/api/settings/email')
@session_login_required
def save_email_settings():
    """à¸šà¸±à¸™à¸—à¸¶à¸ Email Settings"""
    try:
        data = request.get_json() or {}
        
        enabled = data.get('enabled', False)
        smtp_server = data.get('smtp_server', '').strip()
        smtp_port = data.get('smtp_port', 587)
        smtp_user = data.get('smtp_user', '').strip()
        smtp_pass = data.get('smtp_pass', '').strip()
        from_email = data.get('from_email', '').strip()
        to_emails = data.get('to_emails', [])

        # Validate if enabled
        if enabled:
            if not smtp_server or not smtp_user or not from_email:
                add_system_log('error', 'âŒ [400] Email config failed - Missing required fields')
                return jsonify({'error': 'Missing required email configuration'}), 400
            
            if not to_emails or len(to_emails) == 0:
                add_system_log('error', 'âŒ [400] Email config failed - No recipients specified')
                return jsonify({'error': 'At least one recipient email is required'}), 400

        # Load current settings
        settings = load_settings()
        
        # Get existing password if new password is not provided or is masked
        existing_email = settings.get('email', {})
        if smtp_pass == '********' or not smtp_pass:
            smtp_pass = existing_email.get('smtp_pass', '')
        
        # Update email settings
        settings['email'] = {
            'enabled': enabled,
            'smtp_server': smtp_server,
            'smtp_port': smtp_port,
            'smtp_user': smtp_user,
            'smtp_pass': smtp_pass,
            'from_email': from_email,
            'to_emails': to_emails
        }

        # Save settings
        if save_settings(settings):
            # Update email_handler instance
            try:
                email_handler.enabled = enabled
                email_handler.smtp_server = smtp_server
                email_handler.smtp_port = smtp_port
                email_handler.smtp_user = smtp_user
                email_handler.smtp_pass = smtp_pass
                email_handler.from_email = from_email
                email_handler.to_emails = to_emails
            except Exception as handler_error:
                logger.warning(f"[SETTINGS] Could not update email_handler: {handler_error}")
            
            logger.info(f"[SETTINGS] Email settings updated: enabled={enabled}")
            status = "enabled" if enabled else "disabled"
            recipients = len(to_emails)
            add_system_log('info', f'ðŸ“§ [200] Email {status} - Server: {smtp_server}:{smtp_port}, Recipients: {recipients}')
            return jsonify({'success': True}), 200
        else:
            return jsonify({'error': 'Failed to save settings'}), 500

    except Exception as e:
        logger.error(f"[SETTINGS_API] Error saving email settings: {e}")
        return jsonify({'error': str(e)}), 500


@app.post('/api/settings/email/test')
@session_login_required
def test_email_settings():
    """à¸—à¸”à¸ªà¸­à¸šà¸ªà¹ˆà¸‡ Email"""
    try:
        settings = load_settings()
        email_settings = settings.get('email', {})
        
        if not email_settings.get('enabled'):
            add_system_log('warning', 'âš ï¸ [400] Test email failed - Email notifications not enabled')
            return jsonify({'error': 'Email is not enabled'}), 400
        
        # à¸­à¸±à¸›à¹€à¸”à¸• email_handler à¸”à¹‰à¸§à¸¢ settings à¸›à¸±à¸ˆà¸ˆà¸¸à¸šà¸±à¸™
        try:
            email_handler.enabled = email_settings.get('enabled', False)
            email_handler.smtp_server = email_settings.get('smtp_server', 'smtp.gmail.com')
            email_handler.smtp_port = email_settings.get('smtp_port', 587)
            email_handler.sender_email = email_settings.get('smtp_user', '')
            email_handler.sender_password = email_settings.get('smtp_pass', '')
            email_handler.to_emails = email_settings.get('to_emails', [])
        except Exception as handler_error:
            logger.warning(f"[SETTINGS] Could not update email_handler: {handler_error}")
        
        # à¸ªà¹ˆà¸‡ test email
        test_subject = "MT5 Trading Bot - Test Email"
        test_message = f"This is a test email sent at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\nIf you receive this email, your email configuration is working correctly!"
        
        # à¹€à¸£à¸µà¸¢à¸à¹ƒà¸Šà¹‰à¸Ÿà¸±à¸‡à¸à¹Œà¸Šà¸±à¸™à¸ªà¹ˆà¸‡ email
        success = _email_send_alert(test_subject, test_message)
        
        if success:
            logger.info("[SETTINGS] Test email sent successfully")
            recipients = len(email_settings.get('to_emails', []))
            add_system_log('success', f'ðŸ“§ [200] Test email sent successfully to {recipients} recipient(s)')
            return jsonify({'success': True, 'message': 'Test email sent'}), 200
        else:
            add_system_log('error', 'âŒ [500] Test email failed - Check SMTP configuration')
            return jsonify({'error': 'Failed to send test email'}), 500
            
    except Exception as e:
        logger.error(f"[SETTINGS_API] Error testing email: {e}")
        return jsonify({'error': str(e)}), 500

# =================== END SETTINGS API ===================


# ==================================================================================
# SYSTEM LOGS API (à¸ªà¸³à¸«à¸£à¸±à¸šà¹à¸ªà¸”à¸‡ logs à¹ƒà¸™à¸«à¸™à¹‰à¸² System Information)
# ==================================================================================

# System Logs Storage (In-Memory, à¸ˆà¸³à¸à¸±à¸” 300 entries)
system_logs = []
MAX_SYSTEM_LOGS = 300
system_logs_lock = threading.Lock()
sse_system_clients = []
sse_system_lock = threading.Lock()


def add_system_log(log_type, message):
    """
    à¹€à¸žà¸´à¹ˆà¸¡ system log à¹ƒà¸«à¸¡à¹ˆ
    log_type: 'info', 'success', 'warning', 'error'
    """
    with system_logs_lock:
        log_entry = {
            'id': time.time() + id(message),
            'type': log_type or 'info',
            'message': message or '',
            'timestamp': datetime.now().isoformat()
        }
        
        # à¹€à¸žà¸´à¹ˆà¸¡à¸—à¸µà¹ˆà¸«à¸™à¹‰à¸²à¸ªà¸¸à¸” (à¸¥à¹ˆà¸²à¸ªà¸¸à¸”à¸­à¸¢à¸¹à¹ˆà¸šà¸™à¸ªà¸¸à¸”)
        system_logs.insert(0, log_entry)
        
        # à¸ˆà¸³à¸à¸±à¸”à¸ˆà¸³à¸™à¸§à¸™ logs
        if len(system_logs) > MAX_SYSTEM_LOGS:
            system_logs.pop()
        
        # à¸ªà¹ˆà¸‡à¹„à¸›à¸¢à¸±à¸‡ SSE clients
        _broadcast_system_log(log_entry)
        
        return log_entry


def _broadcast_system_log(log_entry):
    """à¸ªà¹ˆà¸‡ log à¹„à¸›à¸¢à¸±à¸‡ SSE clients à¸—à¸±à¹‰à¸‡à¸«à¸¡à¸”"""
    data = f"data: {json.dumps(log_entry)}\n\n"
    
    with sse_system_lock:
        dead_clients = []
        for client_queue in sse_system_clients:
            try:
                client_queue.put(data, block=False)
            except queue.Full:
                dead_clients.append(client_queue)
            except Exception:
                dead_clients.append(client_queue)
        
        # à¸¥à¸š clients à¸—à¸µà¹ˆà¸•à¸²à¸¢
        for client in dead_clients:
            try:
                sse_system_clients.remove(client)
            except:
                pass


@app.get('/api/system/logs')
@session_login_required
def get_system_logs():
    """à¸”à¸¶à¸‡ system logs"""
    try:
        limit = int(request.args.get('limit', 300))
        limit = max(1, min(limit, MAX_SYSTEM_LOGS))
        
        with system_logs_lock:
            logs = system_logs[:limit]
        
        return jsonify({
            'success': True,
            'logs': logs,
            'total': len(logs)
        }), 200
    except Exception as e:
        logger.error(f"[SYSTEM_LOGS] Error getting logs: {e}")
        return jsonify({'error': str(e)}), 500


@app.post('/api/system/logs/clear')
@session_login_required
def clear_system_logs():
    """à¸¥à¹‰à¸²à¸‡ system logs à¸—à¸±à¹‰à¸‡à¸«à¸¡à¸”"""
    try:
        with system_logs_lock:
            system_logs.clear()
        
        add_system_log('info', 'System logs cleared')
        
        return jsonify({'success': True}), 200
    except Exception as e:
        logger.error(f"[SYSTEM_LOGS] Error clearing logs: {e}")
        return jsonify({'error': str(e)}), 500


@app.get('/events/system-logs')
def sse_system_logs():
    """Server-Sent Events stream à¸ªà¸³à¸«à¸£à¸±à¸š real-time system logs"""
    from flask import Response, stream_with_context
    
    client_queue = queue.Queue(maxsize=256)
    
    with sse_system_lock:
        sse_system_clients.append(client_queue)
    
    last_beat = time.time()
    HEARTBEAT_SECS = 20
    
    def gen():
        nonlocal last_beat
        try:
            yield "retry: 3000\n\n"
            
            # à¸ªà¹ˆà¸‡ initial message
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
            with sse_system_lock:
                try:
                    sse_system_clients.remove(client_queue)
                except:
                    pass
    
    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        "X-Accel-Buffering": "no",
    }
    
    return Response(stream_with_context(gen()), headers=headers)


# à¹€à¸žà¸´à¹ˆà¸¡ initial logs à¹€à¸¡à¸·à¹ˆà¸­ server à¹€à¸£à¸´à¹ˆà¸¡à¸—à¸³à¸‡à¸²à¸™
add_system_log('info', 'System started successfully')
add_system_log('success', 'Connected to MT5 server')
add_system_log('info', 'Webhook endpoint initialized')
add_system_log('info', 'Copy trading service active')
add_system_log('info', 'Monitoring active connections')

# =================== END SYSTEM LOGS API ===================


# =================== COMMAND QUEUE API (NEW - สำหรับ EA Poll คำสั่ง) ===================

from app.command_queue import command_queue

@app.get('/api/commands/<account>')
@limiter.limit(get_command_api_rate_limit)  # Dynamic rate limit from settings
def get_commands_for_ea(account: str):
    """
    API สำหรับ EA มา poll คำสั่งที่รออยู่

    EA จะเรียก endpoint นี้ทุกๆ 1-2 วินาทีเพื่อเช็คว่ามีคำสั่งใหม่หรือไม่

    Args:
        account: หมายเลขบัญชี MT5

    Query Parameters:
        limit: จำนวนคำสั่งสูงสุดที่จะดึง (default: 10)

    Returns:
        {
            "success": true,
            "account": "123456",
            "commands": [
                {
                    "queue_id": "...",
                    "action": "BUY",
                    "symbol": "BTCUSD",
                    "volume": 0.01,
                    ...
                }
            ],
            "count": 1
        }
    """
    try:
        account = str(account).strip()
        limit = int(request.args.get('limit', 10))

        # ตรวจสอบว่าบัญชีมีอยู่ในระบบ
        if not session_manager.account_exists(account):
            logger.warning(f"[COMMAND_API] Account {account} not found")
            return jsonify({
                'success': False,
                'error': 'Account not found'
            }), 404

        # ดึงคำสั่งที่รออยู่
        commands = command_queue.get_pending_commands(account, limit=limit)

        logger.debug(f"[COMMAND_API] Retrieved {len(commands)} command(s) for {account}")

        return jsonify({
            'success': True,
            'account': account,
            'commands': commands,
            'count': len(commands)
        })

    except Exception as e:
        logger.error(f"[COMMAND_API] Error getting commands for {account}: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.post('/api/commands/<account>/ack')
def acknowledge_command(account: str):
    """
    API สำหรับ EA แจ้งว่าประมวลผลคำสั่งเสร็จแล้ว

    Body:
        {
            "queue_id": "123456_1234567890_12345",
            "success": true,
            "error": "optional error message"
        }
    """
    try:
        account = str(account).strip()
        data = request.get_json(silent=True) or {}

        queue_id = data.get('queue_id')
        if not queue_id:
            return jsonify({
                'success': False,
                'error': 'queue_id required'
            }), 400

        # Acknowledge คำสั่ง
        success = command_queue.acknowledge_command(account, queue_id)

        if success:
            logger.info(f"[COMMAND_API] ✅ Command acknowledged: {queue_id} by {account}")

            # บันทึกประวัติ (ถ้า EA ส่ง error มา)
            if not data.get('success', True):
                error_msg = data.get('error', 'Unknown error')
                logger.warning(f"[COMMAND_API] ⚠️ Command {queue_id} failed on EA side: {error_msg}")

            return jsonify({
                'success': True,
                'message': 'Command acknowledged'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Command not found or already acknowledged'
            }), 404

    except Exception as e:
        logger.error(f"[COMMAND_API] Error acknowledging command: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.get('/api/commands/<account>/status')
@session_login_required
def get_command_queue_status(account: str):
    """
    API สำหรับดูสถานะ queue ของบัญชี (สำหรับ admin)
    """
    try:
        account = str(account).strip()

        pending_count = command_queue.get_queue_size(account)
        pending_commands = command_queue.get_pending_commands(account, limit=100)

        return jsonify({
            'success': True,
            'account': account,
            'pending_count': pending_count,
            'commands': pending_commands
        })

    except Exception as e:
        logger.error(f"[COMMAND_API] Error getting status for {account}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.post('/api/commands/<account>/clear')
@session_login_required
def clear_command_queue(account: str):
    """
    API สำหรับล้าง queue ของบัญชี (สำหรับ admin)
    """
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
        logger.error(f"[COMMAND_API] Error clearing queue for {account}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.get('/api/commands/status/all')
@session_login_required
def get_all_queues_status():
    """
    API สำหรับดูสถานะ queue ทั้งหมด (สำหรับ admin)
    """
    try:
        status = command_queue.get_all_queues_status()

        return jsonify({
            'success': True,
            'status': status
        })

    except Exception as e:
        logger.error(f"[COMMAND_API] Error getting all queues status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# =================== END COMMAND QUEUE API ===================




# ============= EA Heartbeat API =============

@app.post('/api/ea/heartbeat')
@limiter.limit("60 per minute")
def ea_heartbeat():
    """
    EA ส่ง heartbeat มาทุก 30 วินาที (ไม่บังคับ token)
    Body: {
        "account": "520310937",
        "broker": "FTMO",
        "symbol": "XAUUSD"
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data received'}), 400

        # Token เป็น optional - ถ้าส่งมาก็เช็ค ไม่ส่งมาก็ไม่เช็ค
        # (เพื่อให้ EA ใช้งานได้โดยไม่ต้องใส่ token)

        account = str(data.get('account', '')).strip()
        broker = str(data.get('broker', '')).strip()
        symbol = str(data.get('symbol', '')).strip()

        if not account:
            return jsonify({'error': 'Account number required'}), 400

        if not session_manager.account_exists(account):
            logger.warning(f"[EA_HEARTBEAT] Account {account} not found in system")
            return jsonify({
                'error': 'Account not registered',
                'message': 'Please add this account in Account Management first'
            }), 404

        # เช็คสถานะปัจจุบัน
        accounts = session_manager.get_all_accounts()
        current_account = next((a for a in accounts if a['account'] == account), None)

        if not current_account:
            return jsonify({'error': 'Account not found'}), 404

        # ⚠️ ถ้ายังไม่ได้รับ Symbol → ไม่ activate, แค่อัพเดท heartbeat
        # ต้องรอ Symbol data จาก /api/ea/symbol endpoint เท่านั้น
        if current_account['status'] == 'Wait for Activate':
            # อัพเดท heartbeat แต่ยังคงสถานะ Wait for Activate
            session_manager.update_account_heartbeat(account)
            logger.info(f"[EA_HEARTBEAT] Account {account} heartbeat received but waiting for Symbol data to activate")

            return jsonify({
                'success': True,
                'message': 'Heartbeat received - waiting for Symbol data to activate',
                'status': 'Wait for Activate',
                'activated': False
            })

        # ✅ ถ้าเคย activate แล้วและตอนนี้ Offline → กลับมา Online
        # ⚠️ แต่ถ้าเป็น PAUSE จะไม่เปลี่ยนสถานะ (ต้อง resume จาก UI เท่านั้น)
        if current_account['status'] == 'Offline':
            session_manager.set_account_online(account, broker)
            add_system_log('success', f'🟢 [EA] Account {account} back online')
            logger.info(f"[EA_HEARTBEAT] ✅ Account {account} back online")
        elif current_account['status'] == 'PAUSE':
            # Account is paused - only update heartbeat timestamp, keep PAUSE status
            session_manager.update_account_heartbeat(account)
            logger.info(f"[EA_HEARTBEAT] Account {account} is PAUSED - heartbeat received but status unchanged")
            return jsonify({
                'success': True,
                'message': 'Heartbeat received (account paused)',
                'status': 'PAUSE'
            })

        # อัพเดท heartbeat
        session_manager.update_account_heartbeat(account)

        return jsonify({
            'success': True,
            'message': 'Heartbeat received',
            'status': current_account['status'] if current_account['status'] != 'Offline' else 'Online'
        })

    except Exception as e:
        logger.error(f"[EA_HEARTBEAT_ERROR] {e}")
        return jsonify({'error': str(e)}), 500


@app.get('/api/ea/status/<account>')
def check_ea_status(account):
    """เช็คสถานะของบัญชี"""
    try:
        accounts = session_manager.get_all_accounts()
        acc = next((a for a in accounts if a['account'] == account), None)

        if not acc:
            return jsonify({'error': 'Account not found'}), 404

        return jsonify({
            'account': acc['account'],
            'status': acc['status'],
            'broker': acc['broker'],
            'last_seen': acc['last_seen']
        })

    except Exception as e:
        logger.error(f"[CHECK_STATUS_ERROR] {e}")
        return jsonify({'error': str(e)}), 500



# =================== main ===================

# =================== Secret Key Management ===================
# =================== Global Secret Key Management ===================
@app.get('/settings/secret')
@session_login_required
def get_global_secret():
    """
    ดึง Global Secret Key (สำหรับแสดงใน UI)
    """
    try:
        secret = session_manager.get_global_secret()

        return jsonify({
            'secret': secret,
            'enabled': bool(secret)
        })

    except Exception as e:
        logger.error(f"[GET_GLOBAL_SECRET_ERROR] {e}")
        return jsonify({'error': str(e)}), 500


@app.post('/settings/secret')
@session_login_required
def update_global_secret():
    """
    อัพเดท Global Secret Key

    Body: {"secret": "your_secret_key"} หรือ {"secret": ""} เพื่อลบ
    """
    try:
        data = request.get_json() or {}
        secret = data.get('secret', '').strip()

        if session_manager.update_global_secret(secret):
            action = 'updated' if secret else 'removed'
            add_system_log('success', f'🔐 Global secret key {action}')
            return jsonify({
                'success': True,
                'message': f'Secret key {action} successfully'
            })
        else:
            return jsonify({'error': 'Failed to update secret key'}), 500

    except Exception as e:
        logger.error(f"[UPDATE_GLOBAL_SECRET_ERROR] {e}")
        return jsonify({'error': str(e)}), 500


# =================== Symbol Mapping Management ===================
@app.post('/accounts/<account>/symbols')
@session_login_required
def update_symbol_mappings(account):
    """
    อัพเดท Symbol Mappings สำหรับ account

    Body options:
    1. Bulk update: {"mappings": [{"from": "XAUUSD", "to": "GOLD"}, ...]}
    2. Add single: {"from_symbol": "XAUUSD", "to_symbol": "GOLD"}
    """
    try:
        data = request.get_json() or {}

        if not session_manager.account_exists(account):
            return jsonify({'error': 'Account not found'}), 404

        # Check if this is a single mapping add request
        if 'from_symbol' in data and 'to_symbol' in data:
            from_symbol = data.get('from_symbol', '').strip()
            to_symbol = data.get('to_symbol', '').strip()

            if not from_symbol or not to_symbol:
                return jsonify({'error': 'Both symbols are required'}), 400

            # Get current mappings
            current_mappings = session_manager.get_symbol_mappings(account)

            # Check if mapping already exists
            for mapping in current_mappings:
                if mapping.get('from') == from_symbol:
                    return jsonify({'error': 'Mapping already exists'}), 400

            # Add new mapping
            new_mapping = {'from': from_symbol, 'to': to_symbol}
            current_mappings.append(new_mapping)

            # Save updated mappings
            if session_manager.update_symbol_mappings(account, current_mappings):
                logger.info(f"[SYMBOL_MAPPING] Added {from_symbol} → {to_symbol} for account {account}")
                add_system_log('success', f'✅ Symbol mapping added: {from_symbol} → {to_symbol} (account {account})')

                return jsonify({
                    'success': True,
                    'message': f'Added mapping: {from_symbol} → {to_symbol}',
                    'mapping': new_mapping
                })
            else:
                return jsonify({'error': 'Failed to add symbol mapping'}), 500

        # Otherwise, handle bulk update
        mappings = data.get('mappings', [])

        # Validate mappings format
        if not isinstance(mappings, list):
            return jsonify({'error': 'Mappings must be an array'}), 400

        for mapping in mappings:
            if not isinstance(mapping, dict) or 'from' not in mapping or 'to' not in mapping:
                return jsonify({'error': 'Invalid mapping format'}), 400

        if session_manager.update_symbol_mappings(account, mappings):
            add_system_log('success', f'🔄 Symbol mappings updated for account {account} ({len(mappings)} mappings)')
            return jsonify({
                'success': True,
                'message': 'Symbol mappings updated successfully',
                'count': len(mappings)
            })
        else:
            return jsonify({'error': 'Failed to update symbol mappings'}), 500

    except Exception as e:
        logger.error(f"[UPDATE_MAPPINGS_ERROR] {e}")
        return jsonify({'error': str(e)}), 500


@app.get('/accounts/<account>/symbols')
@session_login_required
def get_symbol_mappings(account):
    """
    ดึง Symbol Mappings ของ account
    """
    try:
        if not session_manager.account_exists(account):
            return jsonify({'error': 'Account not found'}), 404

        mappings = session_manager.get_symbol_mappings(account)

        return jsonify({
            'account': account,
            'mappings': mappings,
            'count': len(mappings)
        })

    except Exception as e:
        logger.error(f"[GET_MAPPINGS_ERROR] {e}")
        return jsonify({'error': str(e)}), 500


@app.delete('/accounts/<account>/symbols/<from_symbol>')
@session_login_required
def delete_symbol_mapping(account, from_symbol):
    """ลบ Symbol Mapping แบบ Real-time"""
    try:
        if not session_manager.account_exists(account):
            return jsonify({'error': 'Account not found'}), 404

        # โหลดข้อมูล Symbol Mappings ปัจจุบัน
        mappings = session_manager.get_symbol_mappings(account)

        # ลบ mapping ที่ตรงกับ from_symbol
        original_count = len(mappings)
        mappings = [m for m in mappings if m.get('from') != from_symbol]

        if len(mappings) == original_count:
            return jsonify({'error': 'Mapping not found'}), 404

        # บันทึกกลับเข้า database
        if session_manager.update_symbol_mappings(account, mappings):
            logger.info(f"[SYMBOL_MAPPING] Deleted {from_symbol} for account {account}")
            add_system_log('success', f'🗑️ Symbol mapping deleted: {from_symbol} (account {account})')

            return jsonify({
                'success': True,
                'message': 'Mapping deleted successfully',
                'remaining_count': len(mappings)
            })
        else:
            return jsonify({'error': 'Failed to delete mapping'}), 500

    except Exception as e:
        logger.error(f"[SYMBOL_MAPPING] Delete error: {e}")
        return jsonify({'error': str(e)}), 500


@app.get('/accounts/symbols/overview')
@session_login_required
def get_all_mappings_overview():
    """
    ดึงภาพรวม Symbol Mappings ของทุก Account
    """
    try:
        all_mappings = session_manager.get_all_symbol_mappings()

        return jsonify({
            'success': True,
            'data': all_mappings,
            'total_accounts': len(all_mappings)
        })

    except Exception as e:
        logger.error(f"[GET_ALL_MAPPINGS_ERROR] {e}")
        return jsonify({'error': str(e)}), 500


# ============= Background Status Checker =============

def background_status_checker():
    """
    เช็คสถานะบัญชีทุก 1 นาที
    ถ้าไม่มี heartbeat มานานเกิน 5 นาที ให้เปลี่ยนเป็น Offline
    """
    while True:
        try:
            session_manager.check_account_online_status()
            time.sleep(60)  # เช็คทุก 1 นาที
        except Exception as e:
            logger.error(f"[BACKGROUND_CHECKER_ERROR] {e}")
            time.sleep(60)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )
    app.logger.setLevel(logging.INFO)
    
    # เริ่ม background thread
    checker_thread = threading.Thread(target=background_status_checker, daemon=True)
    checker_thread.start()
    logger.info("[BACKGROUND] Status checker thread started")
    
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', '5000')), debug=False)
