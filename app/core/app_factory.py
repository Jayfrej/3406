"""
Application Factory
Creates and configures the Flask application with all services and routes
"""
import os
import logging
import threading
from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
from dotenv import load_dotenv
from app.middleware.rate_limit_helpers import get_rate_limit_key, is_localhost

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


def create_app():
    """
    Create and configure the Flask application

    Returns:
        Flask: Configured Flask application instance
    """
    app = Flask(__name__, static_folder='../../static', static_url_path='/static')

    # Load configuration
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['JSON_AS_ASCII'] = False  # Support Thai characters

    # CRITICAL: Session cookie configuration (จำเป็นมากสำหรับ auth)
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,       # ป้องกัน JavaScript เข้าถึง cookie
        SESSION_COOKIE_SAMESITE='Lax',      # อนุญาตให้ส่ง cookie ใน same-site requests
        SESSION_COOKIE_SECURE=False,        # ใช้ True ถ้าเป็น HTTPS
        PERMANENT_SESSION_LIFETIME=3600     # session หมดอายุใน 1 ชั่วโมง
    )

    # Enable CORS for cross-origin API requests
    CORS(app, resources={
        r"/api/*": {
            "origins": ["http://localhost:*", "http://127.0.0.1:*", "http://192.168.*.*:*"],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })

    # Initialize rate limiter with custom key function
    # Higher limits for EA polling (polls every 1 second = 3600/hour)
    limiter = Limiter(
        app=app,
        key_func=get_rate_limit_key,
        default_limits=["50000 per day", "10000 per hour"],  # ← เพิ่มจาก 1000 → 10000 per hour
        storage_uri="memory://"
    )

    logger.info("[APP_FACTORY] Initializing application...")

    # =================== Database Initialization (Safety Net) ===================
    # This ensures database tables exist even if setup.py wasn't run
    # Uses CREATE TABLE IF NOT EXISTS - safe to run every startup
    try:
        from app.core.database_init import ensure_database_schema, verify_database_health

        logger.info("[APP_FACTORY] Checking database schema...")
        if ensure_database_schema():
            health = verify_database_health()
            if health['healthy']:
                logger.info(f"[APP_FACTORY] ✓ Database healthy - {health['user_count']} users, {health['account_count']} accounts")
            else:
                logger.warning(f"[APP_FACTORY] ⚠ Database issue: {health.get('error', 'Unknown')}")
        else:
            logger.error("[APP_FACTORY] ✗ Failed to initialize database schema!")
    except Exception as e:
        logger.error(f"[APP_FACTORY] ✗ Database init error: {e}")

    # =================== Initialize Core Modules ===================
    from app.session_manager import SessionManager
    from app.email_handler import EmailHandler
    from app.command_queue import CommandQueue
    from app.broker_data_manager import BrokerDataManager
    from app.account_balance import AccountBalanceManager
    from app.symbol_mapper import SymbolMapper
    from app.signal_translator import SignalTranslator
    from app.trades import init_trades

    # Initialize managers
    session_manager = SessionManager()
    logger.info("[APP_FACTORY] SessionManager initialized")

    email_handler = EmailHandler()
    logger.info("[APP_FACTORY] EmailHandler initialized")

    command_queue = CommandQueue()
    logger.info(f"[APP_FACTORY] ✅ CommandQueue initialized: {type(command_queue)}")

    broker_manager = BrokerDataManager()
    balance_manager = AccountBalanceManager()
    symbol_mapper = SymbolMapper()
    signal_translator = SignalTranslator(
        broker_data_manager=broker_manager,
        symbol_mapper=symbol_mapper,
        session_manager=session_manager
    )

    logger.info("[APP_FACTORY] Core modules initialized")

    # =================== Initialize Copy Trading ===================
    from app.copy_trading import (
        CopyManager,
        CopyHandler,
        CopyExecutor,
        CopyHistory,
        BalanceHelper
    )

    copy_manager = CopyManager()
    copy_history = CopyHistory()
    balance_helper = BalanceHelper(
        session_manager=session_manager,
        balance_manager=balance_manager
    )
    copy_executor = CopyExecutor(
        session_manager=session_manager,
        copy_history=copy_history,
        command_queue=command_queue
    )
    copy_handler = CopyHandler(
        copy_manager=copy_manager,
        symbol_mapper=symbol_mapper,
        copy_executor=copy_executor,
        session_manager=session_manager,
        broker_data_manager=broker_manager,
        balance_manager=balance_manager,
        email_handler=email_handler
    )

    logger.info("[APP_FACTORY] Copy trading modules initialized")

    # =================== Initialize Services ===================
    from app.services.system_logs_service import SystemLogsService
    from app.services.account_allowlist_service import AccountAllowlistService
    from app.services.webhook_service import WebhookService
    from app.services.settings_service import SettingsService
    from app.services.user_service import UserService  # Domain + License Key system

    # Initialize services
    system_logs_service = SystemLogsService()
    account_allowlist_service = AccountAllowlistService()
    user_service = UserService()  # License key management
    logger.info("[APP_FACTORY] UserService initialized (License Key support)")

    # Helper function for recording trades (used by webhook)
    from app.trades import record_and_broadcast

    logger.info(f"[APP_FACTORY] Creating WebhookService with command_queue: {type(command_queue)}")
    webhook_service = WebhookService(
        session_manager=session_manager,
        command_queue=command_queue,
        record_and_broadcast_fn=record_and_broadcast,
        logger_instance=logger
    )
    logger.info("[APP_FACTORY] ✅ WebhookService initialized with command_queue")

    settings_service = SettingsService()

    logger.info("[APP_FACTORY] Services initialized")

    # =================== Initialize Routes ===================
    from app.routes.webhook_routes import webhook_bp, init_webhook_routes
    from app.routes.account_routes import account_bp, init_account_routes
    from app.routes.copy_trading_routes import copy_trading_bp, init_copy_trading_routes
    from app.routes.settings_routes import settings_bp, init_settings_routes
    from app.routes.system_routes import system_bp, init_system_routes, register_error_handlers
    from app.routes.broker_balance_routes import broker_balance_bp, init_broker_balance_routes
    from app.routes.command_routes import command_bp, init_command_routes
    from app.routes.user_routes import user_bp, init_user_routes  # License key API
    from app.routes.unified_routes import unified_bp, init_unified_routes  # Domain + License Key

    # Import EA API routes
    from app.routes.ea_api_routes import ea_api_bp, init_ea_api_routes

    # Import auth routes (Multi-User SaaS)
    from app.routes.auth_routes import auth_bp

    # Import trades blueprint
    from app.trades import trades_bp

    # Helper for email sending (used by settings)
    def _email_send_alert(subject, message):
        return email_handler.send_alert(subject, message)

    # Helper for deleting account history (used by account routes)
    from app.trades import delete_account_history

    # Initialize route dependencies
    init_webhook_routes(
        ws=webhook_service,
        sm=session_manager,
        st=signal_translator,
        eh=email_handler,
        sls=system_logs_service,
        lim=limiter,
        aas=account_allowlist_service
    )

    init_account_routes(
        sm=session_manager,
        sls=system_logs_service,
        aas=account_allowlist_service,
        cm=copy_manager,
        ch=copy_history,
        dah_fn=delete_account_history
    )

    init_copy_trading_routes(
        cm=copy_manager,
        ch=copy_history,
        ce=copy_executor,
        chand=copy_handler,
        sm=session_manager,
        sls=system_logs_service,
        lim=limiter
    )

    init_settings_routes(
        ss=settings_service,
        sls=system_logs_service,
        eh=email_handler,
        esa_fn=_email_send_alert
    )

    init_system_routes(
        sls=system_logs_service,
        sm=session_manager
    )

    init_broker_balance_routes(
        bm=broker_manager,
        blm=balance_manager,
        sm=session_manager,
        sls=system_logs_service,
        eh=email_handler,
        lim=limiter
    )

    # Initialize command routes
    init_command_routes(
        cq=command_queue,
        sm=session_manager,
        lim=limiter,
        ss=settings_service
    )

    # Initialize EA API routes (heartbeat and balance only)
    init_ea_api_routes(
        bm=balance_manager,
        sm=session_manager,
        lim=limiter
    )

    # Initialize User routes (License Key management)
    init_user_routes(
        us=user_service,
        sls=system_logs_service
    )

    # Initialize Unified routes (Domain + License Key webhook)
    init_unified_routes(
        us=user_service,
        sm=session_manager,
        ws=webhook_service,
        sls=system_logs_service,
        lim=limiter
    )

    logger.info("[APP_FACTORY] Routes initialized (including unified endpoint)")

    # =================== Register Blueprints ===================
    app.register_blueprint(auth_bp)  # Auth routes first (Google OAuth)
    app.register_blueprint(webhook_bp)
    app.register_blueprint(account_bp)
    app.register_blueprint(copy_trading_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(system_bp)
    app.register_blueprint(broker_balance_bp)
    app.register_blueprint(command_bp)
    app.register_blueprint(ea_api_bp)
    app.register_blueprint(trades_bp)
    app.register_blueprint(user_bp)  # License Key API routes

    # Register UI routes (so API routes take precedence)
    from app.routes.ui_routes import ui_bp
    app.register_blueprint(ui_bp)

    # Register unified endpoint LAST (catch-all route /<license_key>)
    # This must be last to avoid conflicts with other routes
    app.register_blueprint(unified_bp)

    logger.info("[APP_FACTORY] Blueprints registered (unified endpoint last)")

    # Debug: Log all registered routes
    logger.info("[APP_FACTORY] Registered routes:")
    for rule in app.url_map.iter_rules():
        methods = ','.join(sorted(rule.methods - {'HEAD', 'OPTIONS'}))
        logger.info(f"  {rule.endpoint:40s} {rule.rule:50s} [{methods}]")

    # Initialize trades (requires app context)
    with app.app_context():
        init_trades()

    # =================== Register Error Handlers ===================
    register_error_handlers(app)

    logger.info("[APP_FACTORY] Error handlers registered")

    # =================== Start Background Threads ===================
    def monitor_instances():
        """Monitor account status and send email alerts on status changes"""
        import time
        from datetime import datetime

        last_status = {}

        while True:
            try:
                accounts = session_manager.get_all_accounts()

                for info in accounts:
                    account = info["account"]
                    nickname = info.get("nickname", "")
                    current_db_status = info.get("status", "")

                    # Skip PAUSE status
                    if current_db_status == "PAUSE":
                        last_status[account] = "PAUSE"
                        continue

                    # Skip Wait for Activate
                    if current_db_status == "Wait for Activate":
                        last_status[account] = "Wait for Activate"
                        continue

                    # Check current status
                    is_alive = session_manager.is_instance_alive(account)
                    new_status = "Online" if is_alive else "Offline"

                    old_status = last_status.get(account, None)

                    # Status changed - send email
                    if old_status and new_status != old_status:
                        display_name = f"{account} ({nickname})" if nickname else account

                        if new_status == "Offline":
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
                            system_logs_service.add_log('warning', f'⚠️ Account {account} went offline')
                            logger.warning(f"[STATUS_CHANGE] {account}: {old_status} -> {new_status}")

                        elif new_status == "Online":
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
                            system_logs_service.add_log('success', f'✅ Account {account} is now online')
                            logger.info(f"[STATUS_CHANGE] {account}: {old_status} -> {new_status}")

                    # Update status in DB
                    session_manager.update_account_status(account, new_status)
                    last_status[account] = new_status

                time.sleep(30)

            except Exception as e:
                logger.error(f"[MONITOR_ERROR] {e}", exc_info=True)
                time.sleep(60)

    # Start monitoring thread
    threading.Thread(target=monitor_instances, daemon=True).start()
    logger.info("[APP_FACTORY] Monitoring thread started")

    # Add initial system logs
    system_logs_service.add_log('info', 'System started successfully')
    system_logs_service.add_log('success', 'Connected to MT5 server')
    system_logs_service.add_log('info', 'Webhook endpoint initialized')
    system_logs_service.add_log('info', 'Copy trading service active')
    system_logs_service.add_log('info', 'Monitoring active connections')

    logger.info("[APP_FACTORY] Application initialization complete")

    return app


