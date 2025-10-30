"""
Copy Trading Handler - FIXED VERSION
แก้ไขให้ส่งคำสั่งไปทุก Slave ที่เชื่อมกับ Master เดียวกัน
Version: 3.2 - Enhanced Logging for Volume Calculation
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

        logger.info("[COPY_HANDLER] Initialized (v3.2 - Enhanced Volume Logging)")
    
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
            skipped_count = 0
            results = []
            
            for pair in valid_pairs:
                slave_account = pair.get('slave_account')
                
                try:
                    # แปลง Signal เป็น Command สำหรับ Slave นี้
                    slave_command = self._convert_signal_to_command(signal_data, pair)
                    if not slave_command:
                        # ⭐ ถ้า None แสดงว่า skip โดยตั้งใจ (เช่น copy_psl = False ใน MODIFY event)
                        logger.info(f"[COPY_HANDLER] ⚠️ Skipped slave {slave_account} (command not applicable)")
                        skipped_count += 1
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
                f"{success_count}/{total_slaves} successful, "
                f"{failed_count}/{total_slaves} failed, "
                f"{skipped_count}/{total_slaves} skipped"
            )
            
            return {
                'success': success_count > 0,
                'slaves_processed': success_count,
                'slaves_failed': failed_count,
                'slaves_skipped': skipped_count,
                'total_slaves': total_slaves,
                'results': results,
                'message': f'Sent to {success_count}/{total_slaves} slaves ({skipped_count} skipped)'
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
        
        try:
            # ค้นหาทุก pairs จาก CopyManager
            all_pairs = self.copy_manager.get_all_pairs()
            
            # กรองเฉพาะ pairs ที่ใช้ API key นี้
            for pair in all_pairs:
                if pair.get('api_token') == api_key or pair.get('apiToken') == api_key:
                    matching_pairs.append(pair)
                    logger.debug(f"[COPY_HANDLER] Found pair {pair.get('id')} with matching API key")
            
            if matching_pairs:
                logger.info(f"[COPY_HANDLER] Found {len(matching_pairs)} pair(s) with API key {api_key[:8]}...")
            else:
                logger.warning(f"[COPY_HANDLER] No pairs found with API key {api_key[:8]}...")
                
        except Exception as e:
            logger.error(f"[COPY_HANDLER] Error finding pairs by API key: {e}", exc_info=True)
        
        return matching_pairs
    
    def _convert_signal_to_command(self, signal_data: Dict, pair: Dict) -> Optional[Dict]:
        """
        แปลง Signal จาก Master เป็น Command สำหรับ Slave
        
        🔥 ENHANCED: เพิ่ม Logging ที่ละเอียดขึ้นสำหรับการคำนวณ Volume
        
        Args:
            signal_data: ข้อมูล Signal จาก Master
            pair: ข้อมูล Copy Pair
            
        Returns:
            Dict หรือ None: Command สำหรับ Slave หรือ None ถ้าไม่ควร copy
        """
        try:
            # Extract data
            master_account = str(signal_data.get('account', ''))
            slave_account = pair.get('slave_account')
            event = signal_data.get('event', '').lower()
            master_symbol = signal_data.get('symbol', '')
            trade_type = str(signal_data.get('type', 'BUY')).upper()
            order_id = signal_data.get('order_id')
            
            settings = pair.get('settings', {})
            auto_map_volume = settings.get('auto_map_volume', True)
            copy_psl = settings.get('copy_psl', True)
            
            # 🔥 ENHANCED: Log การตั้งค่าที่สำคัญ
            logger.info(
                f"[COPY_HANDLER] 🔧 Settings for Pair {pair.get('id')}:\n"
                f"  auto_map_volume: {auto_map_volume}\n"
                f"  volume_mode: {settings.get('volume_mode', 'multiply')}\n"
                f"  multiplier: {settings.get('multiplier', 1.0)}\n"
                f"  copy_psl: {copy_psl}"
            )
            
            # 1. Auto Mapping Symbol
            slave_symbol = master_symbol
            if settings.get('auto_map_symbol', True):
                mapped = self.symbol_mapper.map_symbol(
                    master_symbol,
                    from_account=master_account,
                    to_account=slave_account
                )
                if mapped and mapped != master_symbol:
                    slave_symbol = mapped
                    logger.info(f"[COPY_HANDLER] Symbol mapped: {master_symbol} → {slave_symbol}")
            
            # 2. Calculate Volume
            volume = float(signal_data.get('volume', 0.01))
            original_volume = volume
            
            # 🔥 ENHANCED: Log ก่อนคำนวณ Volume
            logger.info(
                f"[COPY_HANDLER] 📊 Volume Calculation Started:\n"
                f"  Master Volume: {volume}\n"
                f"  Master Symbol: {master_symbol}\n"
                f"  Slave Symbol: {slave_symbol}\n"
                f"  Master Account: {master_account}\n"
                f"  Slave Account: {slave_account}"
            )
            
            # คำนวณ Volume
            volume = self._calculate_slave_volume(
                master_volume=volume,
                settings=settings,
                slave_account=slave_account,
                symbol=slave_symbol,
                master_account=master_account,
                master_symbol=master_symbol
            )
            
            # 🔥 ENHANCED: Log หลังคำนวณ Volume
            if original_volume > 0:
                adjustment_pct = ((volume/original_volume - 1) * 100)
            else:
                adjustment_pct = 0
                
            logger.info(
                f"[COPY_HANDLER] 📊 Volume Calculation Result:\n"
                f"  Original Volume: {original_volume}\n"
                f"  Calculated Volume: {volume}\n"
                f"  Adjustment: {adjustment_pct:+.2f}%"
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
                    'volume': volume,  # ✅ Volume ที่คำนวณแล้ว
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
                
                # ⭐ เช็ค copy_psl ก่อนว่าจะคัดลอก TP/SL หรือไม่
                if not copy_psl:
                    logger.info(f"[COPY_HANDLER] ⚠️ Copy TP/SL is DISABLED, skipping MODIFY event")
                    return None
                
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
        
        🔥 ENHANCED: เพิ่ม Logging ที่ชัดเจนขึ้นในทุกขั้นตอน
        
        Modes:
        - fixed: ใช้ค่า multiplier เป็น volume คงที่
        - percent: คำนวณจาก balance ratio × multiplier
        - multiply: master_volume × multiplier (รองรับ Tick Value Auto-Detection)
        
        Tick Value Auto-Detection:
        - ทำงานเฉพาะใน multiply mode + auto_map_volume = True
        - ปรับ volume ให้มูลค่าเท่ากันเมื่อ tick value ต่างกัน
        """
        try:
            volume_mode = settings.get('volume_mode', 'multiply').lower()
            multiplier = float(settings.get('multiplier', 1.0))
            auto_map_volume = settings.get('auto_map_volume', True)
            
            logger.info(
                f"[COPY_HANDLER] 🔧 Volume Calculation Mode:\n"
                f"  Mode: {volume_mode}\n"
                f"  Multiplier: {multiplier}\n"
                f"  Auto Map Volume: {auto_map_volume}\n"
                f"  Master Volume: {master_volume}"
            )
            
            # ============================================================
            # MODE 1: FIXED VOLUME
            # ============================================================
            if volume_mode == 'fixed':
                volume = multiplier
                logger.info(f"[COPY_HANDLER] ✅ FIXED mode: Volume = {volume}")
                return volume
            
            # ============================================================
            # MODE 2: PERCENT (Balance-Based)
            # ============================================================
            elif volume_mode == 'percent':
                if not master_account or not slave_account:
                    logger.warning("[COPY_HANDLER] ⚠️ Missing account info for percent mode, using multiply fallback")
                    return master_volume * multiplier
                
                master_balance = self.balance_helper.get_account_balance(master_account)
                slave_balance = self.balance_helper.get_account_balance(slave_account)
                
                if master_balance and slave_balance and master_balance > 0:
                    ratio = slave_balance / master_balance
                    volume = master_volume * ratio * multiplier
                    logger.info(
                        f"[COPY_HANDLER] ✅ PERCENT mode:\n"
                        f"  Master Balance: ${master_balance:.2f}\n"
                        f"  Slave Balance: ${slave_balance:.2f}\n"
                        f"  Balance Ratio: {ratio:.4f}\n"
                        f"  Calculation: {master_volume} × {ratio:.4f} × {multiplier} = {volume:.4f}"
                    )
                    return volume
                else:
                    logger.warning("[COPY_HANDLER] ⚠️ Cannot get balances, using multiply fallback")
                    return master_volume * multiplier
            
            # ============================================================
            # MODE 3: MULTIPLY (with Tick Value Auto-Detection)
            # ============================================================
            else:
                logger.info(f"[COPY_HANDLER] 📊 MULTIPLY mode activated")
                
                # 🔥 Tick Value Auto-Detection
                # เงื่อนไข: auto_map_volume = True + master_symbol ≠ slave_symbol
                if auto_map_volume and master_symbol and master_symbol != symbol:
                    logger.info(
                        f"[COPY_HANDLER] 🔥 Tick Value Auto-Detection:\n"
                        f"  Checking symbols: {master_symbol} vs {symbol}"
                    )
                    
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
                        
                        logger.info(
                            f"[COPY_HANDLER] 📊 Tick Value Info:\n"
                            f"  Master ({master_symbol}): {master_tick}\n"
                            f"  Slave ({symbol}): {slave_tick}"
                        )
                        
                        if master_tick != slave_tick and master_tick > 0 and slave_tick > 0:
                            # ✅ Tick Value ต่างกัน → ปรับ Volume
                            tick_ratio = master_tick / slave_tick
                            volume = master_volume * tick_ratio * multiplier
                            
                            logger.info(
                                f"[COPY_HANDLER] ✅ TICK VALUE ADJUSTED:\n"
                                f"  Tick Ratio: {tick_ratio:.4f}\n"
                                f"  Calculation: {master_volume} × {tick_ratio:.4f} × {multiplier} = {volume:.4f}\n"
                                f"  Trade Value (Master): ${master_volume * master_tick:.2f}\n"
                                f"  Trade Value (Slave): ${volume * slave_tick:.2f}"
                            )
                            return volume
                        else:
                            logger.info(
                                f"[COPY_HANDLER] ℹ️ Tick Values are equal or invalid, "
                                f"using standard multiply"
                            )
                    else:
                        logger.warning(
                            f"[COPY_HANDLER] ⚠️ Cannot get symbol info for tick value detection:\n"
                            f"  Master info: {bool(master_info)}\n"
                            f"  Slave info: {bool(slave_info)}"
                        )
                elif not auto_map_volume:
                    logger.info(f"[COPY_HANDLER] ℹ️ Auto Map Volume is OFF, using standard multiply")
                elif master_symbol == symbol:
                    logger.info(f"[COPY_HANDLER] ℹ️ Same symbols ({symbol}), using standard multiply")
                
                # Standard Multiply (fallback)
                volume = master_volume * multiplier
                logger.info(
                    f"[COPY_HANDLER] ✅ Standard MULTIPLY:\n"
                    f"  Calculation: {master_volume} × {multiplier} = {volume}"
                )
                return volume
                
        except Exception as e:
            logger.error(f"[COPY_HANDLER] ❌ Error calculating volume: {e}", exc_info=True)
            logger.info(f"[COPY_HANDLER] Using fallback: master_volume = {master_volume}")
            return master_volume
