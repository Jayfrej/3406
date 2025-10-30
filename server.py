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

# ==== components ====
session_manager = SessionManager()
symbol_mapper = SymbolMapper()
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
copy_manager = CopyManager()
copy_history = CopyHistory()
copy_executor = CopyExecutor(session_manager, copy_history)
copy_handler = CopyHandler(copy_manager, symbol_mapper, copy_executor, session_manager, email_handler)

try:
    logger
except NameError:
    import logging
    logger = logging.getLogger(__name__)
logger.info("[COPY_TRADING] Components initialized successfully")


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
                
                # à¹€à¸Šà¹‡à¸„ Status à¸›à¸±à¸ˆà¸ˆà¸¸à¸šà¸±à¸™
                is_alive = session_manager.is_instance_alive(account)
                new_status = "Online" if is_alive else "Offline"
                
                # à¸”à¸¶à¸‡ Status à¹€à¸à¹ˆà¸²
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
        if session_manager.create_instance(account, nickname):
            logger.info(f"[ACCOUNT_ADDED] {account} ({nickname})")
            add_system_log('success', f'Account {account} added successfully')
            email_handler.send_alert("New Account Added", f"Account {account} ({nickname}) created and started")
            return jsonify({'success': True})
        return jsonify({'error': 'Failed to create account instance'}), 500
    except Exception as e:
        logger.error(f"[ADD_ACCOUNT_ERROR] {e}")
        return jsonify({'error': str(e)}), 500


@app.post('/accounts/<account>/restart')
@session_login_required
def restart_account(account):
    ok = session_manager.restart_instance(account)
    if ok:
        add_system_log('info', f'ðŸ”„ [200] Account restarted: {account}')
        return jsonify({'success': True})
    else:
        add_system_log('error', f'âŒ [500] Restart failed: {account}')
        return jsonify({'error': 'Failed to restart account'}), 500


@app.post('/accounts/<account>/stop')
@session_login_required
def stop_account(account):
    ok = session_manager.stop_instance(account)
    if ok:
        add_system_log('warning', f'â¸ï¸ [200] Account stopped: {account}')
        return jsonify({'success': True})
    else:
        add_system_log('error', f'âŒ [500] Stop failed: {account}')
        return jsonify({'error': 'Failed to stop account'}), 500


@app.post('/accounts/<account>/open')
@session_login_required
def open_account(account):
    try:
        if session_manager.is_instance_alive(account):
            session_manager.focus_instance(account)
            add_system_log('info', f'ðŸ‘ï¸ [200] Account focused: {account} (already online)')
            return jsonify({'success': True, 'message': 'Account is already online'})
        if session_manager.start_instance(account):
            add_system_log('success', f'âœ… [200] Account opened: {account}')
            return jsonify({'success': True})
        return jsonify({'error': 'Failed to open account'}), 500
    except Exception as e:
        logger.error(f"[OPEN_ACCOUNT_ERROR] {e}")
        return jsonify({'error': str(e)}), 500


@app.delete('/accounts/<account>')
@session_login_required
def delete_account(account):
    """à¸¥à¸šà¸šà¸±à¸à¸Šà¸µ Master/Slave à¸ˆà¸£à¸´à¸‡ à¹à¸¥à¸°à¸¥à¹‰à¸²à¸‡ history/allowlist (à¸–à¹‰à¸²à¸¡à¸µ)"""
    try:
        ok = session_manager.delete_instance(str(account))
        app.logger.info(f'[DELETE_ACCOUNT] account={account} ok={ok}')
        if ok:
            # à¹€à¸à¹‡à¸š logic à¹€à¸”à¸´à¸¡à¹„à¸§à¹‰ (history/allowlist) à¹à¸•à¹ˆà¹„à¸¡à¹ˆà¹ƒà¸«à¹‰ error à¸—à¸³à¹ƒà¸«à¹‰à¸¥à¹‰à¸¡
            try:
                deleted = delete_account_history(account)
                app.logger.info(f'[HISTORY_DELETED] {deleted} events for {account}')
                add_system_log('warning', f'ðŸ—‘ï¸ [200] Account deleted: {account} ({deleted} history records removed)')
            except Exception as e:
                app.logger.warning(f'[HISTORY_DELETE_ERROR] {e}')
                add_system_log('warning', f'ðŸ—‘ï¸ [200] Account deleted: {account}')
            return jsonify({'ok': True}), 200
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
        add_system_log('error', 'âŒ [400] Webhook account creation failed - Account number required')
        return jsonify({"error": "account required"}), 400
    nickname = str(data.get("nickname") or "").strip()
    enabled = bool(data.get("enabled", True))

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
    add_system_log('success', f'âœ… [200] Webhook account {status_text}: {account} ({nickname})')
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
        'supported_actions': ['BUY', 'SELL', 'LONG', 'SHORT', 'CLOSE', 'CLOSE_ALL', 'CLOSE_SYMBOL'],
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

    # target accounts
    target_accounts = data.get('accounts') or [data.get('account_number')]

    allowed, blocked = [], []

    # âœ… à¸•à¸£à¸§à¸ˆà¸ªà¸­à¸šà¹à¸•à¹ˆà¸¥à¸° account à¸§à¹ˆà¸²à¸­à¸¢à¸¹à¹ˆà¹ƒà¸™ Webhook Management à¸«à¸£à¸·à¸­à¹„à¸¡à¹ˆ
    for acc in target_accounts:
        acc_str = str(acc).strip()

        if is_account_allowed_for_webhook(acc_str):
            allowed.append(acc_str)
        else:
            blocked.append(acc_str)

            # ðŸ”´ à¸šà¸±à¸™à¸—à¸¶à¸ Error à¸¥à¸‡ Trade History
            record_and_broadcast({
                'status': 'error',
                'action': str(data.get('action', 'UNKNOWN')).upper(),
                'symbol': data.get('symbol', '-'),
                'account': acc_str,
                'volume': data.get('volume', ''),
                'price': data.get('price', ''),
                'message': 'âŒ Account not in Webhook Management'
            })

            logger.error(f"[WEBHOOK_ERROR] Account {acc_str} not in Webhook Management")
            add_system_log('warning', f'âš ï¸ [403] Webhook blocked - Account {acc_str} not in whitelist')

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


# =================== webhook utils ===================
def validate_webhook_payload(data):
    required_fields = ['action']
    if 'account_number' not in data and 'accounts' not in data:
        return {'valid': False, 'error': 'Missing field: account_number or accounts'}
    for field in required_fields:
        if field not in data:
            return {'valid': False, 'error': f'Missing field: {field}'}

    action = str(data['action']).upper()
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
        return {'valid': False, 'error': 'Invalid action. Must be one of: BUY, SELL, LONG, SHORT, CLOSE, CLOSE_ALL, CLOSE_SYMBOL'}

    return {'valid': True}


# =================== webhook core ===================
def process_webhook(data):
    """
    à¸ªà¹ˆà¸‡à¸„à¸³à¸ªà¸±à¹ˆà¸‡à¹„à¸›à¸¢à¸±à¸‡ EA à¸•à¸²à¸¡ accounts à¸—à¸µà¹ˆà¸à¸³à¸«à¸™à¸” à¸žà¸£à¹‰à¸­à¸¡à¸šà¸±à¸™à¸—à¸¶à¸à¸¥à¸‡ history
    """
    try:
        target_accounts = data['accounts'] if 'accounts' in data else [data['account_number']]
        action = str(data['action']).upper()

        # map symbol à¸–à¹‰à¸²à¸¡à¸µà¸à¸²à¸£à¹ƒà¸Šà¹‰à¸ªà¸±à¸à¸¥à¸±à¸à¸©à¸“à¹Œ
        mapped_symbol = None
        if action in ['BUY', 'SELL', 'LONG', 'SHORT', 'CLOSE_SYMBOL'] or (action == 'CLOSE' and 'symbol' in data):
            original_symbol = data['symbol']
            mapped_symbol = symbol_mapper.map_symbol(original_symbol)
            if not mapped_symbol:
                error_msg = f'Cannot map symbol: {original_symbol}'
                logger.error(f"[WEBHOOK_ERROR] {error_msg}")

                # à¸šà¸±à¸™à¸—à¸¶à¸ error à¸ªà¸³à¸«à¸£à¸±à¸šà¸—à¸¸à¸ account
                for account in target_accounts:
                    record_and_broadcast({
                        'status': 'error',
                        'action': action,
                        'symbol': original_symbol,
                        'account': account,
                        'volume': data.get('volume', ''),
                        'price': data.get('price', ''),
                        'message': f'âŒ {error_msg}'
                    })

                return {'success': False, 'error': error_msg}

            logger.info(f"[SYMBOL_MAPPING] {original_symbol} â†’ {mapped_symbol}")

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

            # ðŸ”´ 2. à¸•à¸£à¸§à¸ˆà¸ªà¸­à¸šà¸§à¹ˆà¸²à¸šà¸±à¸à¸Šà¸µ Online à¸«à¸£à¸·à¸­à¹„à¸¡à¹ˆ
            if not session_manager.is_instance_alive(account_str):
                error_msg = f'Account {account_str} is offline'
                logger.warning(f"[WEBHOOK_ERROR] {error_msg}")

                record_and_broadcast({
                    'status': 'error',
                    'action': action,
                    'symbol': data.get('symbol', '-'),
                    'account': account_str,
                    'volume': data.get('volume', ''),
                    'price': data.get('price', ''),
                    'message': f'âš ï¸ {error_msg}'
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
                    'symbol': mapped_symbol or data.get('symbol', '-'),
                    'account': account_str,
                    'volume': data.get('volume', ''),
                    'price': data.get('price', ''),
                    'message': f'{action} command sent to EA'
                })

                results.append({'account': account_str, 'success': True, 'command': cmd, 'action': action})
            else:
                error_msg = 'Failed to write command file'

                record_and_broadcast({
                    'status': 'error',
                    'action': action,
                    'symbol': mapped_symbol or data.get('symbol', '-'),
                    'account': account_str,
                    'volume': data.get('volume', ''),
                    'price': data.get('price', ''),
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

        # map symbol à¸–à¹‰à¸²à¸¡à¸µà¸à¸²à¸£à¹ƒà¸Šà¹‰à¸ªà¸±à¸à¸¥à¸±à¸à¸©à¸“à¹Œ
        mapped_symbol = None
        if action in ['BUY', 'SELL', 'LONG', 'SHORT', 'CLOSE_SYMBOL'] or (action == 'CLOSE' and 'symbol' in data):
            original_symbol = data['symbol']
            mapped_symbol = symbol_mapper.map_symbol(original_symbol)
            if not mapped_symbol:
                return {'success': False, 'error': f'Cannot map symbol: {original_symbol}'}
            logger.info(f"[SYMBOL_MAPPING] {original_symbol} â†’ {mapped_symbol}")

        results = []
        for account in target_accounts:
            # à¸•à¸£à¸§à¸ˆà¸§à¹ˆà¸²à¸¡à¸µà¸šà¸±à¸à¸Šà¸µà¹ƒà¸™ server à¹à¸¥à¸° online
            if not session_manager.account_exists(account):
                record_and_broadcast({
                    'status': 'error', 'action': action,
                    'symbol': data.get('symbol', '-'), 'account': account,
                    'volume': data.get('volume', ''), 'price': data.get('price', ''),
                    'message': 'Account not found'
                })
                results.append({'account': account, 'success': False, 'error': 'Account not found'})
                continue

            if not session_manager.is_instance_alive(account):
                record_and_broadcast({
                    'status': 'error', 'action': action,
                    'symbol': data.get('symbol', '-'), 'account': account,
                    'volume': data.get('volume', ''), 'price': data.get('price', ''),
                    'message': 'Account is offline'
                })
                results.append({'account': account, 'success': False, 'error': 'Account is offline'})
                continue

            cmd = prepare_trading_command(data, mapped_symbol, account)
            ok = write_command_for_ea(account, cmd)

            if ok:
                record_and_broadcast({
                    'status': 'success', 'action': action,
                    'symbol': mapped_symbol or data.get('symbol', '-'), 'account': account,
                    'volume': data.get('volume', ''), 'price': data.get('price', ''),
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
    à¹€à¸‚à¸µà¸¢à¸™à¸„à¸³à¸ªà¸±à¹ˆà¸‡à¸¥à¸‡à¹„à¸Ÿà¸¥à¹Œà¹ƒà¸«à¹‰ EA à¸­à¹ˆà¸²à¸™ (MT5 à¸ˆà¸°à¸­à¹ˆà¸²à¸™à¸ˆà¸²à¸ MQL5/Files à¸‚à¸­à¸‡ instance)
    - primary: <instance>\\Data\\MQL5\\Files\\webhook_command_<ts>.json  (portable mode)
    - fallback: <instance>\\MQL5\\Files\\webhook_command_<ts>.json
    """
    try:
        account = str(account)
        instance_path = session_manager.get_instance_path(account)

        ts = int(time.time() * 1000)
        filename = f"webhook_command_{ts}.json"

        targets = [
            os.path.join(instance_path, "Data", "MQL5", "Files", filename),  # portable datapath
            os.path.join(instance_path, "MQL5", "Files", filename),          # fallback
        ]

        wrote_any = False
        for out_path in targets:
            try:
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(command, f, ensure_ascii=False, indent=2)
                logger.info(f"[WRITE_CMD] wrote {out_path}")
                wrote_any = True
            except Exception as e:
                logger.warning(f"[WRITE_CMD] Failed to write {out_path}: {e}")

        return wrote_any
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

        if not webhook_limit or not api_limit:
            return jsonify({'error': 'Missing webhook or api limit'}), 400

        # Validate format
        import re
        pattern = r'^\d+\s+per\s+(minute|hour|day)$'
        if not re.match(pattern, webhook_limit, re.IGNORECASE):
            add_system_log('error', f'âŒ [400] Rate limit update failed - Invalid webhook format: {webhook_limit}')
            return jsonify({'error': 'Invalid webhook rate limit format'}), 400
        if not re.match(pattern, api_limit, re.IGNORECASE):
            add_system_log('error', f'âŒ [400] Rate limit update failed - Invalid API format: {api_limit}')
            return jsonify({'error': 'Invalid API rate limit format'}), 400

        # Load current settings
        settings = load_settings()
        
        # Update rate limits
        settings['rate_limits'] = {
            'webhook': webhook_limit,
            'api': api_limit,
            'last_updated': datetime.now().isoformat()
        }

        # Save settings
        if save_settings(settings):
            logger.info(f"[SETTINGS] Rate limits updated: webhook={webhook_limit}, api={api_limit}")
            add_system_log('info', f'âš™ï¸ [200] Rate limits updated - Webhook: {webhook_limit}, API: {api_limit}')
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


# =================== main ===================
if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )
    app.logger.setLevel(logging.INFO)
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', '5000')))
