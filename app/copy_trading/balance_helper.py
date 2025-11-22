"""
Balance Helper for Copy Trading
คำนวณ Risk Management สำหรับ Copy Trading
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

class BalanceHelper:
    """Helper สำหรับดึงข้อมูล Balance และคำนวณ Risk Management"""

    def __init__(self, session_manager, balance_manager=None):
        self.session_manager = session_manager
        self.balance_manager = balance_manager

    def get_account_balance(self, account: str) -> Optional[float]:
        """
        ดึง Balance ของ Account จาก Balance Manager (EA ส่งมาผ่าน API)

        Args:
            account: หมายเลขบัญชี

        Returns:
            float: Balance หรือ None ถ้าไม่มีข้อมูล
        """
        try:
            if not self.balance_manager:
                logger.warning(f"[BALANCE_HELPER] Balance manager not initialized")
                return None

            # ตรวจสอบว่า Account มีอยู่
            if not self.session_manager.account_exists(account):
                logger.warning(f"[BALANCE_HELPER] Account {account} not found in system")
                return None

            # ดึง balance จาก balance_manager
            balance = self.balance_manager.get_balance(account)

            if balance is not None:
                logger.debug(f"[BALANCE_HELPER] Account {account} balance: {balance:.2f}")
                return balance
            else:
                logger.warning(
                    f"[BALANCE_HELPER] No balance data for account {account}. "
                    f"Make sure EA is running and sending balance updates."
                )
                return None

        except Exception as e:
            logger.error(f"[BALANCE_HELPER] Failed to get balance for {account}: {e}")
            return None

    def calculate_volume_by_risk(self, balance: float, risk_percent: float, 
                                 symbol: str, stop_loss_pips: float = 50) -> float:
        """
        คำนวณ Volume จาก Risk Percentage
        
        Args:
            balance: Balance ของ Account
            risk_percent: เปอร์เซ็นต์ Risk (เช่น 2.0 = 2%)
            symbol: Symbol ที่จะเทรด
            stop_loss_pips: ระยะ Stop Loss (pips)
            
        Returns:
            float: Volume (lots)
        """
        try:
            # คำนวณ Risk Amount
            risk_amount = balance * (risk_percent / 100)
            
            # ดึง Point Value (simplified - ควรดึงจาก MT5)
            point_values = {
                'XAUUSD': 1.0,      # Gold: $1 per 0.01 lot per $1 move
                'EURUSD': 10.0,     # Forex: $10 per 0.01 lot per pip
                'GBPUSD': 10.0,
                'USDJPY': 10.0,
            }
            
            symbol_upper = symbol.upper()
            point_value = point_values.get(symbol_upper, 10.0)  # Default: 10
            
            # คำนวณ Volume
            volume = risk_amount / (stop_loss_pips * point_value)
            
            # ปัดเศษและจำกัด Min/Max
            volume = round(volume, 2)
            volume = max(0.01, min(volume, 100.0))  # Min: 0.01, Max: 100
            
            logger.debug(
                f"[BALANCE] Calculated volume: {volume} "
                f"(Balance: {balance}, Risk: {risk_percent}%, SL: {stop_loss_pips} pips)"
            )
            
            return volume
            
        except Exception as e:
            logger.error(f"[BALANCE] Volume calculation error: {e}")
            return 0.01  # Fallback: minimum volume