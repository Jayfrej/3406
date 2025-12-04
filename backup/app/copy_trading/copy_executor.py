
import os
import json
import time
import logging
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class CopyExecutor:
    """ส่งคำสั่งการเทรดไปยัง Slave account"""

    def __init__(self, session_manager, copy_history, command_queue):
        """
        Initialize Copy Executor

        Args:
            session_manager: SessionManager instance
            copy_history: CopyHistory instance
            command_queue: CommandQueue instance for EA communication
        """
        self.session_manager = session_manager
        self.copy_history = copy_history
        self.command_queue = command_queue

    # ========================= Public API =========================

    def execute_on_slave(self, slave_account: str, command: Dict[str, Any], pair: Dict[str, Any]) -> Dict[str, Any]:
        """
        ส่งคำสั่งไปยัง Slave account พร้อมตรวจสอบสถานะ
        """
        try:
            # 🔴 1) ตรวจสอบว่าบัญชี Slave มีอยู่จริง
            if not self.session_manager.account_exists(slave_account):
                error_msg = f"Slave account {slave_account} not found in system"
                logger.error(f"[COPY_EXECUTOR] {error_msg}")
                return {'success': False, 'error': error_msg}

            # 🔴 2) ตรวจสอบว่า Slave ออนไลน์
            if not self.session_manager.is_instance_alive(slave_account):
                error_msg = f"Slave account {slave_account} is offline"
                logger.warning(f"[COPY_EXECUTOR] {error_msg}")
                return {'success': False, 'error': error_msg}

            # 🔴 3) ตรวจสอบว่า Slave ไม่ถูก PAUSE และได้ activate แล้ว
            slave_info = self.session_manager.get_account_info(slave_account)
            if slave_info:
                if slave_info.get('status') == 'PAUSE':
                    error_msg = f"Slave account {slave_account} is paused"
                    logger.warning(f"[COPY_EXECUTOR] {error_msg}")
                    return {'success': False, 'error': error_msg}

                if slave_info.get('status') == 'Wait for Activate' or not slave_info.get('symbol_received', False):
                    error_msg = f"Slave account {slave_account} not activated"
                    logger.warning(f"[COPY_EXECUTOR] {error_msg}")
                    return {'success': False, 'error': error_msg}

            # ✅ บัญชีผ่านการตรวจสอบ — เตรียมคำสั่งสำหรับ Slave
            full_command: Dict[str, Any] = {
                **command,
                'account': slave_account,
                'timestamp': datetime.now().isoformat(),
                'copy_from': pair.get('master_account', '-')
            }

            # เขียนคำสั่งลงไฟล์สำหรับ EA
            success = self._write_command_file(slave_account, full_command)

            if success:
                logger.info(
                    f"[COPY_EXECUTOR] Command sent to {slave_account}: "
                    f"{command.get('action')} {command.get('symbol')}"
                )
                return {'success': True, 'message': 'Command sent to slave account'}

            # ❌ เขียนไฟล์ไม่สำเร็จ
            error_msg = "Failed to write command file"
            return {'success': False, 'error': error_msg}

        except Exception as e:
            error_msg = f"Execution error: {str(e)}"
            logger.error(f"[COPY_EXECUTOR] {error_msg}", exc_info=True)
            return {'success': False, 'error': error_msg}

    # ========================= Internal Helpers =========================

    def _write_command_file(self, account: str, command: Dict[str, Any]) -> bool:
        """
        ส่งคำสั่งไปยัง EA ฝั่ง Slave ผ่าน API Command Queue

        EA จะ poll คำสั่งจาก GET /api/commands/<account> แทนการอ่านไฟล์

        Args:
            account: หมายเลขบัญชี Slave
            command: คำสั่งที่จะส่ง

        Returns:
            bool: True ถ้าสำเร็จ
        """
        try:
            # ส่งคำสั่งเข้า Command Queue (API Mode เท่านั้น)
            success = self.command_queue.add_command(account, command)

            if success:
                logger.info(
                    f"[COPY_EXECUTOR] ✅ Added to queue: "
                    f"{command.get('action')} {command.get('symbol')} for {account}"
                )
            else:
                logger.error(f"[COPY_EXECUTOR] ❌ Failed to add to queue for {account}")

            return success

        except Exception as e:
            logger.error(f"[COPY_EXECUTOR] ❌ Failed to send command: {e}", exc_info=True)
            return False
