"""
Copy Trading Manager
จัดการ Copy Pairs, API Keys, และการตั้งค่า

Version: 2.0 - Multiple Pairs per API Key Support
"""

import os
import json
import secrets
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class CopyManager:
    """จัดการ Copy Trading Pairs และ API Keys"""
    
    def __init__(self):
        self.data_dir = os.path.join("data")
        os.makedirs(self.data_dir, exist_ok=True)
        
        self.pairs_file = os.path.join(self.data_dir, "copy_pairs.json")
        self.api_keys_file = os.path.join(self.data_dir, "api_keys.json")
        
        self.pairs = self._load_pairs()
        self.api_keys = self._load_api_keys()
        
        logger.info("[COPY_MANAGER] Initialized successfully")
    
    # =================== Data Loading ===================
    
    def _load_pairs(self) -> List[Dict]:
        """โหลด Copy Pairs จากไฟล์"""
        try:
            if os.path.exists(self.pairs_file):
                with open(self.pairs_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return []
        except Exception as e:
            logger.error(f"[COPY_MANAGER] Failed to load pairs: {e}")
            return []
    
    def _save_pairs(self):
        """บันทึก Copy Pairs ลงไฟล์"""
        try:
            with open(self.pairs_file, 'w', encoding='utf-8') as f:
                json.dump(self.pairs, f, ensure_ascii=False, indent=2)
            logger.info("[COPY_MANAGER] Pairs saved successfully")
        except Exception as e:
            logger.error(f"[COPY_MANAGER] Failed to save pairs: {e}")
    
    def _load_api_keys(self) -> Dict:
        """โหลด API Keys mapping"""
        try:
            if os.path.exists(self.api_keys_file):
                with open(self.api_keys_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"[COPY_MANAGER] Failed to load API keys: {e}")
            return {}
    
    def _save_api_keys(self):
        """บันทึก API Keys mapping"""
        try:
            with open(self.api_keys_file, 'w', encoding='utf-8') as f:
                json.dump(self.api_keys, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[COPY_MANAGER] Failed to save API keys: {e}")
    
    # =================== API Key Management ===================
    
    def generate_api_key(self) -> str:
        """สร้าง API Key ใหม่ที่ไม่ซ้ำกัน"""
        while True:
            api_key = f"ctk_{secrets.token_urlsafe(24)}"
            if api_key not in self.api_keys:
                return api_key
    
    def validate_api_key(self, api_key: str) -> Optional[List[Dict]]:
        """
        ตรวจสอบ API Key และคืนค่าข้อมูล Pairs ทั้งหมดที่ใช้ API Key นี้
        
        🔥 แก้ไขจากเดิม: คืนค่าเป็น List[Dict] แทน Dict เพื่อรองรับหลาย Pairs
        
        Returns:
            List[Dict]: รายการ Pairs ทั้งหมดที่ตรงกับ API Key
            None: ถ้าไม่พบ API Key
        """
        # ตรวจสอบจาก api_keys.json ก่อน (รองรับทั้ง string และ list)
        pair_ids = self.api_keys.get(api_key)
        
        if pair_ids:
            # ถ้าเป็น list ของ pair_ids
            if isinstance(pair_ids, list):
                found_pairs = []
                for pair_id in pair_ids:
                    for pair in self.pairs:
                        if pair.get('id') == pair_id:
                            found_pairs.append(pair)
                return found_pairs if found_pairs else None
            
            # ถ้าเป็น string เดียว (backward compatibility)
            else:
                for pair in self.pairs:
                    if pair.get('id') == pair_ids:
                        return [pair]  # คืนเป็น list เพื่อความสอดคล้อง
        
        # Fallback: ค้นหาจาก pairs โดยตรง
        found_pairs = []
        for pair in self.pairs:
            if pair.get('api_key') == api_key:
                found_pairs.append(pair)
        
        return found_pairs if found_pairs else None
    
    def get_pair_by_api_key(self, api_key: str) -> Optional[List[Dict]]:
        """
        ดึงข้อมูล Pairs จาก API Key
        
        🔥 แก้ไขจากเดิม: คืนค่าเป็น List[Dict]
        """
        return self.validate_api_key(api_key)
    
    def get_pair_for_master(self, api_key: str, master_account: str) -> Optional[Dict]:
        """
        ดึง Pair ที่ตรงกับ API Key และ Master Account
        
        🆕 ฟังก์ชันใหม่: ใช้สำหรับการ copy trade ที่ต้องการเลือก pair เฉพาะ master
        
        Args:
            api_key: API Key
            master_account: หมายเลขบัญชี Master
            
        Returns:
            Dict: Pair ที่ตรงกับ master_account
            None: ถ้าไม่พบ
        """
        pairs = self.validate_api_key(api_key)
        if not pairs:
            return None
        
        # หา pair ที่ master_account ตรงกัน
        for pair in pairs:
            if str(pair.get('master_account')) == str(master_account):
                return pair
        
        return None
    
    # =================== Pair Management ===================
    
    def create_pair(self, master_account: str, slave_account: str, 
                   settings: Dict, master_nickname: str = "", 
                   slave_nickname: str = "") -> Dict:
        """สร้าง Copy Pair ใหม่"""
        try:
            # สร้าง API Key
            api_key = self.generate_api_key()
            
            # สร้าง Pair object
            pair = {
                'id': f"pair_{int(datetime.now().timestamp() * 1000)}",
                'master_account': str(master_account),
                'slave_account': str(slave_account),
                'master_nickname': master_nickname,
                'slave_nickname': slave_nickname,
                'api_key': api_key,
                'status': 'active',
                'settings': {
                    'auto_map_symbol': settings.get('auto_map_symbol', True),
                    'auto_map_volume': settings.get('auto_map_volume', True),
                    'copy_psl': settings.get('copy_psl', True),
                    'volume_mode': settings.get('volume_mode', 'multiply'),
                    'multiplier': float(settings.get('multiplier', 2.0))
                },
                'created': datetime.now().isoformat(),
                'updated': datetime.now().isoformat()
            }
            
            # เพิ่ม Pair
            self.pairs.append(pair)
            
            # เพิ่ม API Key mapping
            self.api_keys[api_key] = pair['id']
            
            # บันทึก
            self._save_pairs()
            self._save_api_keys()
            
            logger.info(f"[COPY_MANAGER] Created pair: {master_account} -> {slave_account}")
            return pair
            
        except Exception as e:
            logger.error(f"[COPY_MANAGER] Failed to create pair: {e}")
            raise
    
    def get_all_pairs(self) -> List[Dict]:
        """ดึงรายการ Pairs ทั้งหมด"""
        return self.pairs
    
    def get_pair_by_id(self, pair_id: str) -> Optional[Dict]:
        """ดึงข้อมูล Pair จาก ID"""
        for pair in self.pairs:
            if pair.get('id') == pair_id:
                return pair
        return None
    
    def update_pair(self, pair_id: str, updates: Dict) -> bool:
        """อัปเดตข้อมูล Pair"""
        try:
            for pair in self.pairs:
                if pair.get('id') == pair_id:
                    # อัปเดต settings
                    if 'settings' in updates:
                        pair['settings'].update(updates['settings'])
                    
                    # อัปเดต master/slave accounts
                    if 'master_account' in updates:
                        pair['master_account'] = str(updates['master_account'])
                    if 'slave_account' in updates:
                        pair['slave_account'] = str(updates['slave_account'])
                    if 'master_nickname' in updates:
                        pair['master_nickname'] = updates['master_nickname']
                    if 'slave_nickname' in updates:
                        pair['slave_nickname'] = updates['slave_nickname']
                    
                    pair['updated'] = datetime.now().isoformat()
                    
                    self._save_pairs()
                    logger.info(f"[COPY_MANAGER] Updated pair: {pair_id}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"[COPY_MANAGER] Failed to update pair: {e}")
            return False
    
    def delete_pair(self, pair_id: str) -> bool:
        """ลบ Copy Pair"""
        try:
            pair_id = str(pair_id)
            pair = self.get_pair_by_id(pair_id)
            if not pair:
                return False

            api_key = pair.get('api_key') or pair.get('apiKey')
            
            # อัพเดท api_keys mapping
            if api_key and api_key in self.api_keys:
                # ถ้าเป็น list
                if isinstance(self.api_keys[api_key], list):
                    self.api_keys[api_key] = [
                        pid for pid in self.api_keys[api_key] if pid != pair_id
                    ]
                    # ถ้าไม่เหลือ pair แล้ว ลบ key ออก
                    if not self.api_keys[api_key]:
                        del self.api_keys[api_key]
                # ถ้าเป็น string
                else:
                    if self.api_keys[api_key] == pair_id:
                        del self.api_keys[api_key]
                
                self._save_api_keys()

            # ลบ pair
            self.pairs = [p for p in self.pairs if str(p.get('id')) != pair_id]
            self._save_pairs()
            
            logger.info(f"[COPY_MANAGER] Deleted pair: {pair_id}")
            return True
            
        except Exception as e:
            logger.exception(f"[COPY_MANAGER] delete_pair error: {e}")
            return False
    
    def toggle_pair_status(self, pair_id: str) -> Optional[str]:
        """เปิด/ปิด Copy Pair"""
        try:
            pair = self.get_pair_by_id(pair_id)
            if not pair:
                return None
            
            new_status = 'inactive' if pair.get('status') == 'active' else 'active'
            pair['status'] = new_status
            pair['updated'] = datetime.now().isoformat()
            
            self._save_pairs()
            logger.info(f"[COPY_MANAGER] Toggled pair {pair_id} to {new_status}")
            return new_status
            
        except Exception as e:
            logger.error(f"[COPY_MANAGER] Failed to toggle pair: {e}")
            return None
    
    # =================== Query Functions ===================
    
    def get_pairs_by_master(self, master_account: str) -> List[Dict]:
        """ดึง Pairs ทั้งหมดที่ใช้ Master account นี้"""
        return [p for p in self.pairs if p.get('master_account') == str(master_account)]
    
    def get_pairs_by_slave(self, slave_account: str) -> List[Dict]:
        """ดึง Pairs ทั้งหมดที่ใช้ Slave account นี้"""
        return [p for p in self.pairs if p.get('slave_account') == str(slave_account)]
    
    def get_active_pairs(self) -> List[Dict]:
        """ดึง Pairs ที่เปิดใช้งานอยู่"""
        return [p for p in self.pairs if p.get('status') == 'active']
