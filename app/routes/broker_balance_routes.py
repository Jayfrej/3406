"""
Broker and Balance API Routes
Handles broker data registration, account balance updates, and related queries
"""
import logging
from flask import Blueprint, request, jsonify
from app.middleware.auth import session_login_required

logger = logging.getLogger(__name__)

# Create blueprint
broker_balance_bp = Blueprint('broker_balance', __name__)

# These will be injected by the app factory
broker_manager = None
balance_manager = None
session_manager = None
system_logs_service = None
email_handler = None
limiter = None


def init_broker_balance_routes(bm, blm, sm, sls, eh, lim):
    """
    Initialize broker and balance routes with dependencies

    Args:
        bm: BrokerDataManager instance
        blm: AccountBalance instance (balance manager)
        sm: SessionManager instance
        sls: SystemLogsService instance
        eh: EmailHandler instance
        lim: Limiter instance
    """
    global broker_manager, balance_manager, session_manager
    global system_logs_service, email_handler, limiter

    broker_manager = bm
    balance_manager = blm
    session_manager = sm
    system_logs_service = sls
    email_handler = eh
    limiter = lim


# =================== Broker Data API ===================

@broker_balance_bp.route('/api/broker/register', methods=['POST'])
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
    # Apply rate limit
    limiter.limit("10 per minute")(lambda: None)()

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
                    system_logs_service.add_log('success', f'🟢 [EA] Account {account} activated by Symbol data (Broker: {broker_name}, {symbol_count} symbols)')
                    logger.info(f"[BROKER_REGISTER] ✅ Account {account} ACTIVATED by Symbol data")

                    # ส่ง email แจ้งเตือน
                    email_handler.send_alert(
                        "Account Activated by Symbol",
                        f"Account {account} activated by Symbol data\nBroker: {broker_name}\nSymbols: {symbol_count}"
                    )

            system_logs_service.add_log(
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
        system_logs_service.add_log('error', f'❌ [500] Broker data registration failed: {str(e)}')
        return jsonify({'error': str(e)}), 500


@broker_balance_bp.route('/api/broker/<account>', methods=['GET'])
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


@broker_balance_bp.route('/api/broker/stats', methods=['GET'])
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

@broker_balance_bp.route('/api/account/balance', methods=['POST'])
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
    # Apply rate limit
    limiter.limit("60 per minute")(lambda: None)()

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


@broker_balance_bp.route('/api/account/<account>/balance', methods=['GET'])
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


@broker_balance_bp.route('/api/account/balance/all', methods=['GET'])
@session_login_required
def get_all_account_balances():
    """ดึงข้อมูล balance ของทุก account"""
    try:
        balances = balance_manager.get_all_balances()
        return jsonify({'success': True, 'data': balances}), 200
    except Exception as e:
        logger.error(f"[BALANCE_GET_ALL] Error: {e}")
        return jsonify({'error': str(e)}), 500


@broker_balance_bp.route('/api/account/balance/status', methods=['GET'])
@session_login_required
def get_balance_manager_status():
    """ดึงสถานะของ Balance Manager"""
    try:
        status = balance_manager.get_status()
        return jsonify({'success': True, 'status': status}), 200
    except Exception as e:
        logger.error(f"[BALANCE_STATUS] Error: {e}")
        return jsonify({'error': str(e)}), 500

