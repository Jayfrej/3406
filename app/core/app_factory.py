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
from dotenv import load_dotenv

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
    app = Flask(__name__, static_folder='../static', static_url_path='/static')

    # Load configuration
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['JSON_AS_ASCII'] = False  # Support Thai characters

    # Initialize rate limiter
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=["200 per day", "50 per hour"],
        storage_uri="memory://"
    )

    logger.info("[APP_FACTORY] Initializing application...")

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
    email_handler = EmailHandler()
    command_queue = CommandQueue()
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
        copy_history=copy_history
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

    # Initialize services
    system_logs_service = SystemLogsService()
    account_allowlist_service = AccountAllowlistService()

    # Helper function for recording trades (used by webhook)
    from app.trades import record_and_broadcast

    webhook_service = WebhookService(
        session_manager=session_manager,
        command_queue=command_queue,
        record_and_broadcast_fn=record_and_broadcast,
        logger_instance=logger
    )

    settings_service = SettingsService()

    logger.info("[APP_FACTORY] Services initialized")

    # =================== Initialize Routes ===================
    from app.routes.webhook_routes import webhook_bp, init_webhook_routes
    from app.routes.account_routes import account_bp, init_account_routes
    from app.routes.copy_trading_routes import copy_trading_bp, init_copy_trading_routes
    from app.routes.settings_routes import settings_bp, init_settings_routes
    from app.routes.system_routes import system_bp, init_system_routes, register_error_handlers
    from app.routes.broker_balance_routes import broker_balance_bp, init_broker_balance_routes

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

    logger.info("[APP_FACTORY] Routes initialized")

    # =================== Register Blueprints ===================
    app.register_blueprint(webhook_bp)
    app.register_blueprint(account_bp)
    app.register_blueprint(copy_trading_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(system_bp)
    app.register_blueprint(broker_balance_bp)

    logger.info("[APP_FACTORY] Blueprints registered")

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


