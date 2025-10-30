"""
Copy Trading Handler - FIXED VERSION
แก้ไขให้ส่งคำสั่งไปทุก Slave ที่เชื่อมกับ Master เดียวกัน
Version: 3.1 - Multiple Slaves Support
"""

import logging
from typing import Dict, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

class CopyHandler:
    """จัดการการรับและประมวลผลสัญญาณจาก Master"""
    
    def __init__(self, copy_manager, symbol_mapper, copy_executor, session_manager, email_handler=None):
        self.copy_manager = copy_manager
        self.symbol_mapper = symbol_mapper
        self.copy_executor = copy_executor
        self.email_handler = email_handler

        from .balance_helper import BalanceHelper
        self.balance_helper = BalanceHelper(session_manager)

        logger.info("[COPY_HANDLER] Initialized (v3.1 - Multiple Slaves Support)")
    
    def process_master_signal(self, api_key: str, signal_data: Dict) -> Dict:
        """
        ประมวลผลสัญญาณจาก Master EA และส่งไปทุก Slave ที่ใช้ API key เดียวกัน
        
        🔥 FIXED: วนลูปส่งคำสั่งไปทุก Slave แทนที่จะส่งแค่ตัวเดียว
        
        Args:
            api_key: API Key ของ Copy Pair
            signal_data: ข้อมูล Signal จาก Master
            
        Returns:
            Dict: {'success': bool, 'message': str, 'slaves_processed': int}
        """
        try:
            # ============================================================
            # FIXED: หาทุก pairs ที่ใช้ API key นี้แทนที่จะหาแค่ตัวเดียว
            # ============================================================
            matching_pairs = self._get_all_pairs_by_api_key(api_key)
            
            if not matching_pairs:
                logger.warning(f"[COPY_HANDLER] Invalid API key: {api_key[:8]}...")
                return {'success': False, 'error': 'Invalid API key'}
            
            logger.info(f"[COPY_HANDLER] Found {len(matching_pairs)} pair(s) using this API key")
            
            # ตรวจสอบ Master account จาก signal
            master_account = str(signal_data.get('account', ''))
            
            # กรองเฉพาะ pairs ที่ match กับ master account และ status = active
            valid_pairs = []
            for pair in matching_pairs:
                # ตรวจสอบ Master account
                if master_account != pair.get('master_account'):
                    continue
                
                # ตรวจสอบสถานะ Pair
                if pair.get('status') != 'active':
                    logger.info(f"[COPY_HANDLER] Pair {pair.get('id')} is inactive, skipping")
                    continue
                
                # ตรวจสอบว่า Slave account เชื่อมต่ออยู่หรือไม่
                slave_account = pair.get('slave_account')
                if not self.balance_helper.session_manager.account_exists(slave_account):
                    logger.warning(f"[COPY_HANDLER] Slave account {slave_account} not found, skipping")
                    continue
                
                if not self.balance_helper.session_manager.is_instance_alive(slave_account):
                    logger.warning(f"[COPY_HANDLER] Slave account {slave_account} instance not alive, skipping")
                    continue
                
                valid_pairs.append(pair)
            
            if not valid_pairs:
                logger.warning(
                    f"[COPY_HANDLER] No valid pairs found for master {master_account}"
                )
                return {'success': False, 'error': 'No valid slave accounts available'}
            
            logger.info(f"[COPY_HANDLER] Processing signal for {len(valid_pairs)} slave(s)")
            
            # ============================================================
            # FIXED: วนลูปส่งคำสั่งไปทุก Slave
            # ============================================================
            success_count = 0
            failed_count = 0
            results = []
            
            for pair in valid_pairs:
                slave_account = pair.get('slave_account')
                
                try:
                    # แปลง Signal เป็น Command สำหรับ Slave นี้
                    slave_command = self._convert_signal_to_command(signal_data, pair)
                    if not slave_command:
                        logger.warning(f"[COPY_HANDLER] Failed to convert signal for slave {slave_account}")
                        failed_count += 1
                        continue
                    
                    # ส่งคำสั่งไปยัง Slave นี้
                    logger.info(f"[COPY_HANDLER] Executing command on slave: {slave_account}")
                    result = self.copy_executor.execute_on_slave(
                        slave_account=slave_account,
                        command=slave_command,
                        pair=pair
                    )
                    
                    if result.get('success'):
                        success_count += 1
                        logger.info(f"[COPY_HANDLER] ✅ Successfully sent to slave {slave_account}")
                    else:
                        failed_count += 1
                        logger.error(f"[COPY_HANDLER] ❌ Failed to send to slave {slave_account}: {result.get('error')}")
                    
                    results.append({
                        'slave_account': slave_account,
                        'success': result.get('success'),
                        'error': result.get('error')
                    })
                
                except Exception as e:
                    logger.error(f"[COPY_HANDLER] Error processing slave {slave_account}: {e}", exc_info=True)
                    failed_count += 1
                    results.append({
                        'slave_account': slave_account,
                        'success': False,
                        'error': str(e)
                    })
            
            # สรุปผลลัพธ์
            total_slaves = len(valid_pairs)
            logger.info(
                f"[COPY_HANDLER] ✅ Signal processed: "
                f"{success_count}/{total_slaves} successful, {failed_count}/{total_slaves} failed"
            )
            
            return {
                'success': success_count > 0,
                'slaves_processed': success_count,
                'slaves_failed': failed_count,
                'total_slaves': total_slaves,
                'results': results,
                'message': f'Sent to {success_count}/{total_slaves} slaves'
            }
        
        except Exception as e:
            logger.error(f"[COPY_HANDLER] Error processing signal: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    # ============================================================
    # FIXED: เพิ่มฟังก์ชันหาทุก pairs ที่ใช้ API key เดียวกัน
    # ============================================================
    def _get_all_pairs_by_api_key(self, api_key: str) -> List[Dict]:
        """
        หาทุก pairs ที่ใช้ API key นี้
        
        Args:
            api_key: API Key ที่ต้องการหา
            
        Returns:
            List[Dict]: รายการ pairs ที่ใช้ API key นี้
        """
        matching_pairs = []
        
        # วิธีที่ 1: ใช้ api_keys mapping (ถ้ามี)
        if hasattr(self.copy_manager, 'api_keys'):
            pair_ids = self.copy_manager.api_keys.get(api_key)
            
            # ถ้า pair_ids เป็น list (กรณีมีหลาย pairs)
            if isinstance(pair_ids, list):
                for pair_id in pair_ids:
                    pair = self.copy_manager.get_pair_by_id(pair_id)
                    if pair:
                        matching_pairs.append(pair)
            # ถ้า pair_ids เป็น string (กรณีมี pair เดียว)
            elif isinstance(pair_ids, str):
                pair = self.copy_manager.get_pair_by_id(pair_ids)
                if pair:
                    matching_pairs.append(pair)
        
        # วิธีที่ 2: Fallback - สแกนทุก pairs โดยตรง
        if not matching_pairs:
            for pair in self.copy_manager.pairs:
                pair_api_key = pair.get('api_key') or pair.get('apiKey')
                if pair_api_key == api_key:
                    matching_pairs.append(pair)
        
        return matching_pairs
    
    # ============================================================
    # ฟังก์ชันเดิมที่ไม่ต้องแก้ (เก็บไว้ทั้งหมด)
    # ============================================================
    
    def _convert_signal_to_command(self, signal_data: Dict, pair: Dict) -> Optional[Dict]:
        """
        แปลงสัญญาณจาก Master เป็นคำสั่งสำหรับ Slave
        [เก็บโค้ดเดิมทั้งหมด - ไม่ต้องแก้]
        """
        try:
            settings = pair.get('settings', {})
            
            # ✅ Normalize keys - รองรับทั้ง True และ False
            # ใช้ if-else แทน or เพื่อให้ False ทำงานได้ถูกต้อง
            auto_map_symbol = (settings.get('auto_map_symbol') 
                             if 'auto_map_symbol' in settings 
                             else settings.get('autoMapSymbol', True))
            auto_map_volume = (settings.get('auto_map_volume') 
                             if 'auto_map_volume' in settings 
                             else settings.get('autoMapVolume', True))
            copy_psl = (settings.get('copy_psl') 
                       if 'copy_psl' in settings 
                       else settings.get('copyPSL', True))
            
            # ดึงข้อมูลพื้นฐาน
            event = str(signal_data.get('event', '')).lower()
            master_symbol = str(signal_data.get('symbol', ''))
            trade_type = str(signal_data.get('type', '')).upper()
            volume = float(signal_data.get('volume', 0))
            order_id = signal_data.get('order_id', '')
            
            logger.info(
                f"[COPY_HANDLER] Converting signal: "
                f"event={event} | symbol={master_symbol} | type={trade_type} | "
                f"volume={volume} | order_id={order_id}"
            )
            
            # 1. Map Symbol
            slave_symbol = master_symbol
            if auto_map_symbol:
                mapped_symbol = self.symbol_mapper.map_symbol(master_symbol)
                if mapped_symbol:
                    logger.info(f"[COPY_HANDLER] Symbol mapped: {master_symbol} → {mapped_symbol}")
                    slave_symbol = mapped_symbol
            
            # 2. Calculate Volume
            slave_account = pair.get('slave_account')
            master_account = pair.get('master_account')
            
            volume = self._calculate_slave_volume(
                master_volume=volume,
                settings=settings,
                slave_account=slave_account,
                symbol=slave_symbol,
                master_account=master_account,
                master_symbol=master_symbol
            )
            
            # 3. Generate Comment
            copy_comment = f"COPY_{order_id}" if order_id else f"Copy from Master {master_account}"
            logger.info(f"[COPY_HANDLER] Generated comment: {copy_comment}")
            
            # 4. Create Command based on Event Type
            
            # EVENT: OPEN ORDER
            if event in ['deal_add', 'order_add']:
                logger.info(f"[COPY_HANDLER] Processing OPEN ORDER event")
                
                command = {
                    'action': trade_type,
                    'symbol': slave_symbol,
                    'volume': volume,
                    'order_type': 'market',
                    'comment': copy_comment
                }
                
                if copy_psl:
                    if signal_data.get('tp') is not None:
                        command['take_profit'] = float(signal_data['tp'])
                    if signal_data.get('sl') is not None:
                        command['stop_loss'] = float(signal_data['sl'])
                    logger.info(f"[COPY_HANDLER] Copy TP/SL is ENABLED")
                
                logger.info(
                    f"[COPY_HANDLER] ✅ OPEN Command created: "
                    f"{trade_type} {slave_symbol} {volume} lots | Comment: {copy_comment}"
                )
                return command
            
            # EVENT: CLOSE ORDER
            elif event in ['deal_close', 'position_close']:
                logger.info(f"[COPY_HANDLER] Processing CLOSE ORDER event")
                
                if order_id:
                    # ⭐ ใช้ action: "close" แทน "close_by_comment" เพื่อให้ EA รู้จัก
                    command = {
                        'action': 'close',
                        'comment': copy_comment,
                        'symbol': slave_symbol
                    }
                    logger.info(f"[COPY_HANDLER] ✅ CLOSE Command created (by Comment): {copy_comment}")
                    return command
                else:
                    command = {
                        'action': 'close_symbol',
                        'symbol': slave_symbol
                    }
                    logger.info(f"[COPY_HANDLER] ✅ CLOSE Command created (by Symbol): {slave_symbol}")
                    return command
            
            # EVENT: MODIFY ORDER
            elif event in ['position_modify', 'order_modify']:
                logger.info(f"[COPY_HANDLER] Processing MODIFY ORDER event")
                
                new_tp = signal_data.get('tp')
                new_sl = signal_data.get('sl')
                
                if order_id:
                    command = {
                        'action': 'modify',
                        'comment': copy_comment,
                        'symbol': slave_symbol
                    }
                    if new_tp is not None:
                        command['take_profit'] = float(new_tp)
                    if new_sl is not None:
                        command['stop_loss'] = float(new_sl)
                    
                    logger.info(
                        f"[COPY_HANDLER] ✅ MODIFY Command created (by Comment): "
                        f"Comment: {copy_comment} | TP: {new_tp} | SL: {new_sl}"
                    )
                    return command
            
            logger.warning(f"[COPY_HANDLER] Unknown event type: {event}")
            return None
            
        except Exception as e:
            logger.error(f"[COPY_HANDLER] Error converting signal: {e}", exc_info=True)
            return None
    
    def _calculate_slave_volume(
        self,
        master_volume: float,
        settings: Dict,
        slave_account: str,
        symbol: str,
        master_account: str = None,
        master_symbol: str = None
    ) -> float:
        """
        คำนวณ Volume สำหรับ Slave ตาม settings
        [เก็บโค้ดเดิมทั้งหมด - ไม่ต้องแก้]
        """
        try:
            volume_mode = settings.get('volume_mode', 'multiply').lower()
            multiplier = float(settings.get('multiplier', 1.0))
            auto_map_volume = settings.get('auto_map_volume', True)
            
            logger.info(f"[COPY_HANDLER] Volume Mode: {volume_mode} | Multiplier: {multiplier}")
            
            # FIXED MODE
            if volume_mode == 'fixed':
                volume = multiplier
                logger.info(f"[COPY_HANDLER] Using fixed volume: {volume}")
                return volume
            
            # PERCENT MODE
            elif volume_mode == 'percent':
                if not master_account or not slave_account:
                    logger.warning("[COPY_HANDLER] Missing account info for percent mode")
                    return master_volume * multiplier
                
                master_balance = self.balance_helper.get_account_balance(master_account)
                slave_balance = self.balance_helper.get_account_balance(slave_account)
                
                if master_balance and slave_balance and master_balance > 0:
                    ratio = slave_balance / master_balance
                    volume = master_volume * ratio * multiplier
                    logger.info(
                        f"[COPY_HANDLER] Percent mode: "
                        f"Master: ${master_balance:.2f} | Slave: ${slave_balance:.2f} | "
                        f"Ratio: {ratio:.4f} | Volume: {volume:.2f}"
                    )
                    return volume
                else:
                    logger.warning("[COPY_HANDLER] Cannot get balances, using multiplier")
                    return master_volume * multiplier
            
            # MULTIPLY MODE (with Tick Value Auto-Detection)
            else:
                # Tick Value Auto-Detection
                if auto_map_volume and master_symbol and master_symbol != symbol:
                    logger.info("[COPY_HANDLER] 🔥 Tick Value Auto-Detection enabled")
                    
                    master_info = self.balance_helper.session_manager.get_symbol_info(
                        master_account, master_symbol
                    )
                    slave_info = self.balance_helper.session_manager.get_symbol_info(
                        slave_account, symbol
                    )
                    
                    if (master_info and slave_info and 
                        master_info.get('trade_contract_size') and 
                        slave_info.get('trade_contract_size')):
                        
                        master_tick = float(master_info['trade_contract_size'])
                        slave_tick = float(slave_info['trade_contract_size'])
                        
                        if master_tick != slave_tick:
                            ratio = master_tick / slave_tick
                            volume = master_volume * ratio * multiplier
                            logger.info(
                                f"[COPY_HANDLER] ✅ Tick Value adjusted: "
                                f"Master: {master_tick} | Slave: {slave_tick} | "
                                f"Ratio: {ratio:.4f} | Volume: {volume:.4f}"
                            )
                            return volume
                
                # Standard multiply
                volume = master_volume * multiplier
                logger.info(f"[COPY_HANDLER] Multiply mode: {master_volume} × {multiplier} = {volume}")
                return volume
                
        except Exception as e:
            logger.error(f"[COPY_HANDLER] Error calculating volume: {e}", exc_info=True)
            return master_volume
