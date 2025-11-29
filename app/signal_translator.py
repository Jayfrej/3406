"""
Signal Translator
แปลสัญญาณจาก TradingView/Master ให้เป็นคำสั่งที่ EA เข้าใจ
รวมถึงแปล Symbol และตรวจสอบว่า Slave มี Symbol นั้นหรือไม่
Version: 1.3 - Fixed: ส่ง available_symbols เข้า map_symbol()
"""

import logging
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)


class SignalTranslator:
    """แปลสัญญาณให้เป็นคำสั่งสำหรับ EA"""

    def __init__(self, broker_data_manager, symbol_mapper, session_manager=None):
        """
        Args:
            broker_data_manager: BrokerDataManager instance
            symbol_mapper: SymbolMapper instance
            session_manager: SessionManager instance (optional) - สำหรับเช็ค per-account mappings
        """
        self.broker_data_manager = broker_data_manager
        self.symbol_mapper = symbol_mapper
        self.session_manager = session_manager
    
    # =========================
    # Public Methods
    # =========================
    def translate_for_account(
        self, 
        signal: Dict, 
        target_account: str,
        auto_map_symbol: bool = True
    ) -> Optional[Dict]:
        """
        แปลสัญญาณ 1 ชุด สำหรับ 1 บัญชี
        
        Args:
            signal: ข้อมูลสัญญาณจาก TradingView/Master
            target_account: บัญชีปลายทาง (slave)
            auto_map_symbol: ถ้า True จะพยายาม map symbol อัตโนมัติ
        
        Returns:
            คำสั่งพร้อมส่งให้ EA หรือ None ถ้าใช้ไม่ได้
        """
        if not signal or not isinstance(signal, dict):
            logger.error("[SIGNAL_TRANSLATOR] Invalid signal payload")
            return None
        
        original_symbol = str(signal.get('symbol', '')).strip()
        if not original_symbol:
            logger.error("[SIGNAL_TRANSLATOR] Missing symbol in signal")
            return None

        # 1) ดึงรายชื่อ Symbol ที่บัญชีนี้มี
        available_symbols = self.broker_data_manager.get_available_symbols(target_account) or []
        if not available_symbols:
            logger.warning(
                f"[SIGNAL_TRANSLATOR] No available symbols for account {target_account} "
                f"(broker data may not be sent yet)"
            )
        else:
            logger.debug(
                f"[SIGNAL_TRANSLATOR] Account {target_account} has {len(available_symbols)} symbols: "
                f"{available_symbols[:5]}..." if len(available_symbols) > 5 else f"{available_symbols}"
            )

        # 2) เตรียม symbol ที่จะใช้
        mapped_symbol = None

        # ⭐ NEW: เช็ค per-account symbol mapping ที่ User ตั้งไว้ก่อน
        if self.session_manager:
            user_mappings = self.session_manager.get_symbol_mappings(target_account)
            if user_mappings:
                # หา mapping ที่ตรงกัน (case-insensitive)
                symbol_upper = original_symbol.upper()
                for mapping in user_mappings:
                    if mapping.get('from', '').upper() == symbol_upper:
                        user_mapped = mapping.get('to', '')
                        if user_mapped:
                            # ตรวจสอบว่า symbol ที่ map อยู่ใน available_symbols หรือไม่
                            if not available_symbols or user_mapped in available_symbols:
                                mapped_symbol = user_mapped
                                logger.info(
                                    f"[SIGNAL_TRANSLATOR] ✅ User mapping found: "
                                    f"{original_symbol} → {mapped_symbol} for {target_account}"
                                )
                            else:
                                # ลอง case-insensitive match
                                user_mapped_lower = user_mapped.lower()
                                for avail in available_symbols:
                                    if avail.lower() == user_mapped_lower:
                                        mapped_symbol = avail
                                        logger.info(
                                            f"[SIGNAL_TRANSLATOR] ✅ User mapping found (case-adjusted): "
                                            f"{original_symbol} → {mapped_symbol} for {target_account}"
                                        )
                                        break

                                if not mapped_symbol:
                                    logger.warning(
                                        f"[SIGNAL_TRANSLATOR] ⚠️ User mapped symbol '{user_mapped}' "
                                        f"not in available symbols for {target_account}"
                                    )
                        break

        # ถ้าไม่มี user mapping หรือ user mapping ไม่สำเร็จ → ใช้ auto mapping
        if not mapped_symbol:
            if auto_map_symbol:
                # ใช้ whitelist ของโบรกเกอร์ช่วย map
                mapped_symbol = self._map_symbol_with_whitelist(
                    original_symbol,
                    available_symbols
                )
            else:
                # ไม่ auto map → พยายาม map ด้วย mapper ปกติ
                mapped_symbol = self.symbol_mapper.map_symbol(
                    original_symbol,
                    available_symbols  # ✅ ส่ง available_symbols เข้าไป
                )
        
        if not mapped_symbol:
            logger.warning(
                f"[SIGNAL_TRANSLATOR] ❌ Mapping failed for {original_symbol} on {target_account}"
            )
            return None
        
        # 3) สร้าง payload ส่งให้ EA
        translated = {
            'original_symbol': original_symbol,
            'symbol': mapped_symbol,
            'action': signal.get('action'),  # อาจเป็น None (ไม่เป็นไร)
            'event': signal.get('event'),    # เก็บ event ไว้ด้วย
            'order_type': signal.get('order_type', 'market'),
            'type': signal.get('type'),      # เก็บ type ไว้ด้วย
            'volume': signal.get('volume'),
            'price': signal.get('price'),
            'take_profit': signal.get('take_profit'),
            'stop_loss': signal.get('stop_loss'),
            'comment': signal.get('comment'),
            'timeframe': signal.get('timeframe'),
            'ticket': signal.get('ticket'),
            'order_id': signal.get('order_id'),
        }
        
        # ⭐ ลบการตรวจสอบ action ออก
        # เพราะ Master ส่ง 'event' ไม่ใช่ 'action'
        # การแปล event → action เป็นหน้าที่ของ copy_handler
        
        logger.info(
            f"[SIGNAL_TRANSLATOR] ✅ {original_symbol} → {mapped_symbol} for {target_account}"
        )
        return translated
    
    def translate_batch_for_account_list(
        self,
        signal: Dict,
        target_accounts: List[str],
        auto_map_symbol: bool = True
    ) -> Dict[str, Optional[Dict]]:
        """
        แปลสัญญาณชุดเดียวให้หลายบัญชี
        
        Returns:
            dict: {account: translated_or_none}
        """
        if not target_accounts:
            logger.warning("[SIGNAL_TRANSLATOR] Empty target account list")
            return {}
        
        results: Dict[str, Optional[Dict]] = {}
        
        for account in target_accounts:
            results[account] = self.translate_for_account(
                signal,
                account,
                auto_map_symbol
            )
        
        success_count = sum(1 for v in results.values() if v is not None)
        logger.info(
            f"[SIGNAL_TRANSLATOR] Batch translation: {success_count}/{len(target_accounts)} "
            f"successful"
        )
        
        return results

    # =========================
    # Internal Helpers
    # =========================
    def _map_symbol_with_whitelist(
        self, 
        original_symbol: str, 
        available_symbols: List[str]
    ) -> Optional[str]:
        """
        แปล Symbol โดยใช้ whitelist จากโบรกเกอร์
        
        Args:
            original_symbol: Symbol ต้นฉบับ
            available_symbols: Symbol ที่มีในโบรกเกอร์
        
        Returns:
            str หรือ None
        """
        # 1. ลองหาตรงๆ ก่อน
        if original_symbol in available_symbols:
            logger.debug(f"[SIGNAL_TRANSLATOR] Exact match: {original_symbol}")
            return original_symbol
        
        # 2. ลองใช้ symbol mapper
        # ✅ แก้ไข: ส่ง available_symbols เข้าไปด้วย
        mapped = self.symbol_mapper.map_symbol(original_symbol, available_symbols)
        
        if mapped and mapped in available_symbols:
            logger.debug(
                f"[SIGNAL_TRANSLATOR] Mapped with whitelist: "
                f"{original_symbol} → {mapped}"
            )
            return mapped
        
        # 3. ลอง case-insensitive match
        original_lower = original_symbol.lower()
        for symbol in available_symbols:
            if symbol.lower() == original_lower:
                logger.debug(f"[SIGNAL_TRANSLATOR] Case-insensitive match: {original_symbol} → {symbol}")
                return symbol
        
        # 4. ลองหา partial match ด้วย normalization
        try:
            normalized_original = self._normalize_symbol_simple(original_symbol)
            if normalized_original:
                for symbol in available_symbols:
                    normalized_candidate = self._normalize_symbol_simple(symbol)
                    if normalized_candidate == normalized_original:
                        logger.debug(f"[SIGNAL_TRANSLATOR] Normalized match: {original_symbol} → {symbol}")
                        return symbol
        except Exception as e:
            logger.debug(f"[SIGNAL_TRANSLATOR] Normalization error: {e}")
        
        # 5. Debug: แสดงข้อมูลสำหรับการแก้ไข
        logger.warning(
            f"[SIGNAL_TRANSLATOR] ❌ No mapping found for {original_symbol} "
            f"in available symbols: {available_symbols[:10]}..."  # แสดงแค่ 10 ตัวแรก
        )
        return None
    
    def _normalize_symbol_simple(self, symbol: str) -> str:
        """Simple normalization สำหรับการเปรียบเทียบเบื้องต้น"""
        if not symbol:
            return ""
        
        # Convert to uppercase
        normalized = symbol.upper().strip()
        
        # Remove common suffixes
        suffixes = ['.CASH', '_CASH', '.SPOT', '_SPOT', '.MINI', '_MINI', 
                   '.PRO', '_PRO', '.ECN', '_ECN', 'M', 'S', 'C']
        
        for suffix in suffixes:
            if normalized.endswith(suffix):
                normalized = normalized[:-len(suffix)]
                break
        
        # Remove common prefixes
        prefixes = ['M_', 'MINI_', 'SPOT_', 'CASH_']
        for prefix in prefixes:
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix):]
                break
        
        return normalized