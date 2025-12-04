"""
Broker Data Manager
จัดการข้อมูลโบรกเกอร์ที่ EA ส่งมา (Contract Size, Symbols, Volume Limits)
Version: 1.0
"""

import os
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class BrokerDataManager:
    """จัดการข้อมูลโบรกเกอร์แต่ละบัญชี"""
    
    def __init__(self, data_dir: str = 'data'):
        self.data_dir = data_dir
        self.data_file = os.path.join(data_dir, 'broker_info.json')
        self.broker_data = {}
        
        # สร้างโฟลเดอร์ถ้ายังไม่มี
        os.makedirs(data_dir, exist_ok=True)
        
        # โหลดข้อมูลเดิม
        self._load_from_file()
        
        logger.info(f"[BROKER_MANAGER] Initialized with {len(self.broker_data)} accounts")
    
    def _load_from_file(self):
        """โหลดข้อมูลจากไฟล์"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    self.broker_data = json.load(f)
                logger.info(f"[BROKER_MANAGER] Loaded {len(self.broker_data)} broker data from file")
            else:
                logger.info("[BROKER_MANAGER] No existing broker data file, starting fresh")
        except Exception as e:
            logger.error(f"[BROKER_MANAGER] Failed to load broker data: {e}")
            self.broker_data = {}
    
    def _save_to_file(self):
        """บันทึกข้อมูลลงไฟล์"""
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.broker_data, f, indent=2, ensure_ascii=False)
            logger.debug(f"[BROKER_MANAGER] Saved {len(self.broker_data)} broker data to file")
        except Exception as e:
            logger.error(f"[BROKER_MANAGER] Failed to save broker data: {e}")
    
    def save_broker_info(self, account: str, broker_data: dict) -> bool:
        """
        เก็บข้อมูลโบรกเกอร์ที่ EA ส่งมา
        
        Args:
            account: หมายเลขบัญชี
            broker_data: {
                "broker": "XM Global",
                "symbols": [
                    {
                        "name": "EURUSD",
                        "contract_size": 100000,
                        "volume_min": 0.01,
                        "volume_max": 100.0
                    }
                ]
            }
        
        Returns:
            bool: สำเร็จหรือไม่
        """
        try:
            account = str(account).strip()
            
            if not account:
                logger.error("[BROKER_MANAGER] Account number is empty")
                return False
            
            # บันทึกข้อมูล
            self.broker_data[account] = {
                'account': account,
                'broker': broker_data.get('broker', 'Unknown'),
                'symbols': broker_data.get('symbols', []),
                'updated_at': datetime.now().isoformat(),
                'symbol_count': len(broker_data.get('symbols', []))
            }
            
            # บันทึกลงไฟล์
            self._save_to_file()
            
            logger.info(
                f"[BROKER_MANAGER] ✅ Saved broker info for account {account}: "
                f"{self.broker_data[account]['symbol_count']} symbols from "
                f"{self.broker_data[account]['broker']}"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"[BROKER_MANAGER] Failed to save broker info: {e}")
            return False
    
    def get_broker_info(self, account: str) -> Optional[Dict]:
        """
        ดึงข้อมูลโบรกเกอร์ของบัญชี
        
        Args:
            account: หมายเลขบัญชี
        
        Returns:
            dict หรือ None
        """
        account = str(account).strip()
        return self.broker_data.get(account)
    
    def get_available_symbols(self, account: str) -> List[str]:
        """
        ดึงรายชื่อ Symbol ทั้งหมดที่บัญชีนี้มี
        
        Args:
            account: หมายเลขบัญชี
        
        Returns:
            List[str]: รายชื่อ Symbol
        """
        broker_info = self.get_broker_info(account)
        
        if not broker_info:
            logger.warning(f"[BROKER_MANAGER] No broker info for account {account}")
            return []
        
        symbols = [s['name'] for s in broker_info.get('symbols', [])]
        logger.debug(f"[BROKER_MANAGER] Account {account} has {len(symbols)} symbols")
        
        return symbols
    
    def get_symbol_info(self, account: str, symbol: str) -> Optional[Dict]:
        """
        ดึงข้อมูล Symbol เฉพาะตัว
        
        Args:
            account: หมายเลขบัญชี
            symbol: ชื่อ Symbol
        
        Returns:
            dict หรือ None: {
                "name": "EURUSD",
                "contract_size": 100000,
                "volume_min": 0.01,
                "volume_max": 100.0
            }
        """
        broker_info = self.get_broker_info(account)
        
        if not broker_info:
            return None
        
        for sym in broker_info.get('symbols', []):
            if sym['name'] == symbol:
                return sym
        
        logger.debug(f"[BROKER_MANAGER] Symbol {symbol} not found in account {account}")
        return None
    
    def get_contract_size(self, account: str, symbol: str) -> float:
        """
        ดึง Contract Size ของ Symbol
        
        Args:
            account: หมายเลขบัญชี
            symbol: ชื่อ Symbol
        
        Returns:
            float: Contract Size (default: 100000 ถ้าไม่พบ)
        """
        symbol_info = self.get_symbol_info(account, symbol)
        
        if symbol_info and symbol_info.get('contract_size'):
            return float(symbol_info['contract_size'])
        
        # Default fallback
        logger.warning(
            f"[BROKER_MANAGER] Contract size not found for {symbol} in account {account}, "
            f"using default 100000"
        )
        return 100000.0
    
    def has_symbol(self, account: str, symbol: str) -> bool:
        """
        ตรวจสอบว่าบัญชีมี Symbol นี้หรือไม่
        
        Args:
            account: หมายเลขบัญชี
            symbol: ชื่อ Symbol
        
        Returns:
            bool
        """
        available_symbols = self.get_available_symbols(account)
        return symbol in available_symbols
    
    def get_stats(self) -> Dict:
        """ดึงสถิติการใช้งาน"""
        total_symbols = sum(
            info.get('symbol_count', 0) 
            for info in self.broker_data.values()
        )
        
        return {
            'total_accounts': len(self.broker_data),
            'total_symbols': total_symbols,
            'accounts': list(self.broker_data.keys())
        }
    
    def clear_account(self, account: str) -> bool:
        """ลบข้อมูลบัญชี"""
        try:
            account = str(account).strip()
            
            if account in self.broker_data:
                del self.broker_data[account]
                self._save_to_file()
                logger.info(f"[BROKER_MANAGER] Cleared broker data for account {account}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"[BROKER_MANAGER] Failed to clear account {account}: {e}")
            return False