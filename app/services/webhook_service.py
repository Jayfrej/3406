"""
Webhook Service
Handles webhook request processing, validation, and command execution
"""
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any

logger = logging.getLogger(__name__)


class WebhookService:
    """Service for handling webhook operations and trading commands"""

    def __init__(self, session_manager, command_queue, record_and_broadcast_fn, logger_instance=None):
        """
        Initialize Webhook Service

        Args:
            session_manager: SessionManager instance for account management
            command_queue: CommandQueue instance for EA communication
            record_and_broadcast_fn: Function to record trade events to history
            logger_instance: Optional logger instance (uses module logger if None)
        """
        self.session_manager = session_manager
        self.command_queue = command_queue
        self.record_and_broadcast = record_and_broadcast_fn
        self.logger = logger_instance or logger

    def normalize_action(self, action: str) -> str:
        """
        Normalize action aliases to standard actions
        - CALL -> BUY
        - PUT -> SELL

        Args:
            action: Action string to normalize

        Returns:
            str: Normalized action
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

    def validate_webhook_payload(self, data: Dict) -> Dict[str, Any]:
        """
        Validate webhook payload structure and data

        Args:
            data: Webhook payload dictionary

        Returns:
            dict: {'valid': bool, 'error': str (if invalid)}
        """
        required_fields = ['action']
        if 'account_number' not in data and 'accounts' not in data:
            return {'valid': False, 'error': 'Missing field: account_number or accounts'}
        for field in required_fields:
            if field not in data:
                return {'valid': False, 'error': f'Missing field: {field}'}

        # Normalize action aliases (call->buy, put->sell)
        action = self.normalize_action(data['action'])
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

    def process_webhook(self, data: Dict) -> Dict[str, Any]:
        """
        Process webhook data and send trading commands to EAs

        Args:
            data: Validated webhook payload

        Returns:
            dict: {'success': bool, 'message': str, 'error': str (if failed)}
        """
        try:
            target_accounts = data['accounts'] if 'accounts' in data else [data['account_number']]
            action = str(data['action']).upper()

            # Use symbol that was already translated from webhook handler
            mapped_symbol = data.get('symbol')

            results = []

            for account in target_accounts:
                account_str = str(account).strip()

                # 1. Check if account exists in system
                if not self.session_manager.account_exists(account_str):
                    error_msg = f'Account {account_str} not found in system'
                    self.logger.error(f"[WEBHOOK_ERROR] {error_msg}")

                    self.record_and_broadcast({
                        'status': 'error',
                        'action': action,
                        'symbol': data.get('symbol', '-'),
                        'account': account_str,
                        'volume': data.get('volume', ''),
                        'price': data.get('price', ''),
                        'message': f'❌ {error_msg}'
                    })

                    results.append({'account': account_str, 'success': False, 'error': error_msg})
                    continue

                # Check status column first (more reliable than heartbeat)
                account_info = self.session_manager.get_account_info(account_str)
                account_status = account_info.get('status', '') if account_info else ''

                if account_status == 'Offline':
                    error_msg = f'Account {account_str} Offline'
                    self.logger.warning(f"[WEBHOOK_ERROR] {error_msg}")

                    self.record_and_broadcast({
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
                if not self.session_manager.is_instance_alive(account_str):
                    error_msg = f'Account {account_str} Offline'
                    self.logger.warning(f"[WEBHOOK_ERROR] {error_msg}")

                    self.record_and_broadcast({
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

                # Account passed checks - send command
                cmd = self.prepare_trading_command(data, mapped_symbol, account_str)
                ok = self.write_command_for_ea(account_str, cmd)

                if ok:
                    self.record_and_broadcast({
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

                    self.record_and_broadcast({
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

            # Summarize results
            success_count = sum(1 for r in results if r['success'])
            total_count = len(results)

            if success_count == total_count:
                return {'success': True, 'message': f'{action} sent to {success_count}/{total_count} accounts'}
            elif success_count > 0:
                return {'success': True, 'message': f'{action} partial success: {success_count}/{total_count} accounts'}
            else:
                return {'success': False, 'error': f'Failed to send {action} to any account'}

        except Exception as e:
            self.logger.error(f"[WEBHOOK_ERROR] {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def prepare_trading_command(self, data: Dict, mapped_symbol: Optional[str], account: str) -> Dict:
        """
        Prepare trading command structure for EA

        Args:
            data: Webhook data
            mapped_symbol: Mapped/translated symbol (if available)
            account: Account number

        Returns:
            dict: Trading command structure
        """
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

    def write_command_for_ea(self, account: str, command: Dict) -> bool:
        """
        Send command to EA via API Command Queue

        EA polls commands from GET /api/commands/<account> instead of file reading

        Args:
            account: Account number
            command: Trading command dictionary

        Returns:
            bool: True if sent successfully
        """
        try:
            account = str(account)

            # Send command to Command Queue (API Mode only)
            success = self.command_queue.add_command(account, command)

            if success:
                self.logger.info(
                    f"[WRITE_CMD] ✅ Added to queue: {command.get('action')} "
                    f"{command.get('symbol')} for {account}"
                )
            else:
                self.logger.error(f"[WRITE_CMD] ❌ Failed to add to queue for {account}")

            return success

        except Exception as e:
            self.logger.error(f"[WRITE_CMD_ERROR] {e}")
            return False

