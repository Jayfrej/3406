"""
Account Balance Manager
จัดเก็บและจัดการข้อมูล Account Balance ที่ EA ส่งมาผ่าน API
"""

import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class AccountBalanceManager:
    """
    จัดการข้อมูล Account Balance
    - เก็บข้อมูล balance ของแต่ละ account ใน memory
    - EA จะส่งข้อมูล balance มาทุกๆ 30 วินาที
    - ข้อมูลจะหมดอายุหลัง 2 นาที (ถ้า EA ไม่ส่งมา)
    """

    def __init__(self, cache_expiry_seconds: int = 120):
        """
        Args:
            cache_expiry_seconds: เวลาที่ข้อมูล balance จะหมดอายุ (default: 120 วินาที)
        """
        self._balances: Dict[str, Dict] = {}
        self._locks: Dict[str, threading.Lock] = {}
        self._cache_expiry = cache_expiry_seconds

        logger.info(f"[BALANCE_MANAGER] Initialized with cache expiry: {cache_expiry_seconds}s")

    def update_balance(
        self,
        account: str,
        balance: float,
        equity: float = None,
        margin: float = None,
        free_margin: float = None,
        currency: str = None
    ) -> bool:
        """
        อัพเดทข้อมูล balance ของ account

        Args:
            account: หมายเลขบัญชี
            balance: Balance
            equity: Equity (optional)
            margin: Margin (optional)
            free_margin: Free Margin (optional)
            currency: สกุลเงิน (optional)

        Returns:
            bool: True ถ้าอัพเดทสำเร็จ
        """
        try:
            account = str(account).strip()

            if account not in self._locks:
                self._locks[account] = threading.Lock()

            with self._locks[account]:
                self._balances[account] = {
                    'balance': float(balance),
                    'equity': float(equity) if equity is not None else None,
                    'margin': float(margin) if margin is not None else None,
                    'free_margin': float(free_margin) if free_margin is not None else None,
                    'currency': currency,
                    'updated_at': datetime.now(),
                    'timestamp': datetime.now().isoformat()
                }

            logger.info(
                f"[BALANCE_MANAGER] Updated: Account {account} "
                f"Balance={balance:.2f} Equity={equity} Currency={currency}"
            )

            return True

        except Exception as e:
            logger.error(f"[BALANCE_MANAGER] Update error: {e}", exc_info=True)
            return False

    def get_balance(self, account: str) -> Optional[float]:
        """
        ดึง balance ของ account

        Args:
            account: หมายเลขบัญชี

        Returns:
            float: Balance หรือ None ถ้าไม่มีข้อมูล/หมดอายุ
        """
        try:
            account = str(account).strip()

            if account not in self._balances:
                logger.warning(f"[BALANCE_MANAGER] No data for account {account}")
                return None

            data = self._balances[account]
            updated_at = data.get('updated_at')

            # ตรวจสอบว่าข้อมูลหมดอายุหรือไม่
            if updated_at:
                age = (datetime.now() - updated_at).total_seconds()
                if age > self._cache_expiry:
                    logger.warning(
                        f"[BALANCE_MANAGER] Data expired for account {account} "
                        f"(age: {age:.0f}s > {self._cache_expiry}s)"
                    )
                    return None

            balance = data.get('balance')
            logger.debug(f"[BALANCE_MANAGER] Retrieved balance for {account}: {balance}")

            return balance

        except Exception as e:
            logger.error(f"[BALANCE_MANAGER] Get balance error: {e}", exc_info=True)
            return None

    def get_balance_info(self, account: str) -> Optional[Dict]:
        """
        ดึงข้อมูล balance ทั้งหมดของ account

        Args:
            account: หมายเลขบัญชี

        Returns:
            dict: ข้อมูล balance ทั้งหมด หรือ None ถ้าไม่มีข้อมูล/หมดอายุ
        """
        try:
            account = str(account).strip()

            if account not in self._balances:
                return None

            data = self._balances[account].copy()
            updated_at = data.get('updated_at')

            # ตรวจสอบว่าข้อมูลหมดอายุหรือไม่
            if updated_at:
                age = (datetime.now() - updated_at).total_seconds()
                if age > self._cache_expiry:
                    logger.warning(
                        f"[BALANCE_MANAGER] Data expired for account {account} "
                        f"(age: {age:.0f}s)"
                    )
                    return None

                data['age_seconds'] = age

            # แปลง datetime เป็น string สำหรับ JSON
            if 'updated_at' in data:
                data['updated_at'] = data['updated_at'].isoformat()

            return data

        except Exception as e:
            logger.error(f"[BALANCE_MANAGER] Get balance info error: {e}", exc_info=True)
            return None

    def get_all_balances(self) -> Dict[str, Dict]:
        """
        ดึงข้อมูล balance ของทุก account

        Returns:
            dict: {account: balance_info}
        """
        try:
            result = {}

            for account in list(self._balances.keys()):
                info = self.get_balance_info(account)
                if info:  # เฉพาะข้อมูลที่ยังไม่หมดอายุ
                    result[account] = info

            return result

        except Exception as e:
            logger.error(f"[BALANCE_MANAGER] Get all balances error: {e}", exc_info=True)
            return {}

    def cleanup_expired(self) -> int:
        """
        ลบข้อมูลที่หมดอายุ

        Returns:
            int: จำนวน account ที่ถูกลบ
        """
        try:
            now = datetime.now()
            expired_accounts = []

            for account, data in self._balances.items():
                updated_at = data.get('updated_at')
                if updated_at:
                    age = (now - updated_at).total_seconds()
                    if age > self._cache_expiry:
                        expired_accounts.append(account)

            for account in expired_accounts:
                del self._balances[account]
                if account in self._locks:
                    del self._locks[account]

            if expired_accounts:
                logger.info(
                    f"[BALANCE_MANAGER] Cleaned up {len(expired_accounts)} expired accounts"
                )

            return len(expired_accounts)

        except Exception as e:
            logger.error(f"[BALANCE_MANAGER] Cleanup error: {e}", exc_info=True)
            return 0

    def get_status(self) -> Dict:
        """
        ดึงสถานะของ Balance Manager

        Returns:
            dict: สถานะทั้งหมด
        """
        try:
            active_accounts = []
            expired_accounts = []
            now = datetime.now()

            for account, data in self._balances.items():
                updated_at = data.get('updated_at')
                if updated_at:
                    age = (now - updated_at).total_seconds()
                    if age <= self._cache_expiry:
                        active_accounts.append({
                            'account': account,
                            'balance': data.get('balance'),
                            'age_seconds': age
                        })
                    else:
                        expired_accounts.append(account)

            return {
                'total_accounts': len(self._balances),
                'active_accounts': len(active_accounts),
                'expired_accounts': len(expired_accounts),
                'cache_expiry_seconds': self._cache_expiry,
                'accounts': active_accounts
            }

        except Exception as e:
            logger.error(f"[BALANCE_MANAGER] Get status error: {e}", exc_info=True)
            return {'error': str(e)}

    def check_balance_health(self, account: str) -> Dict:
        """
        ตรวจสอบสุขภาพของ balance data

        Args:
            account: หมายเลขบัญชี

        Returns:
            dict: {
                'healthy': bool,
                'warnings': List[str],
                'last_update_seconds': float,
                'balance': float
            }
        """
        try:
            account = str(account).strip()
            info = self.get_balance_info(account)

            if not info:
                return {
                    'healthy': False,
                    'warnings': ['No balance data available - EA may not be sending balance updates'],
                    'last_update_seconds': None,
                    'balance': None
                }

            warnings = []
            age = info.get('age_seconds', 0)
            balance = info.get('balance', 0)

            # Check 1: Balance data too old (EA might be offline or not sending)
            if age > self._cache_expiry:
                warnings.append(
                    f'Balance data is {age:.0f}s old (expired - EA stopped sending updates)'
                )
            elif age > 90:  # Warning at 90 seconds (before expiry at 120s)
                warnings.append(
                    f'Balance data is {age:.0f}s old (approaching expiry - EA may have issues)'
                )

            # Check 2: Balance = 0 or negative (unusual but not necessarily an error)
            if balance <= 0:
                warnings.append(f'Balance is {balance:.2f} (unusual - check account status)')

            return {
                'healthy': len(warnings) == 0,
                'warnings': warnings,
                'last_update_seconds': age,
                'balance': balance
            }

        except Exception as e:
            logger.error(f"[BALANCE_MANAGER] Check health error: {e}", exc_info=True)
            return {
                'healthy': False,
                'warnings': [f'Error checking health: {str(e)}'],
                'last_update_seconds': None,
                'balance': None
            }


# Global instance
balance_manager = AccountBalanceManager(cache_expiry_seconds=120)
