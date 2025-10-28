"""
Copy Trading Handler
รับและประมวลผลสัญญาณจาก Master EA
Version: 3.0 - Tick Value Auto-Detection (Multiply Mode Only)

🔥 การทำงาน:
- Auto Mapping Volume = ON + Volume Mode = Multiply
  → ตรวจสอบ Tick Value อัตโนมัติ
  → ถ้า Tick Value ต่างกัน = ปรับ Volume ให้มูลค่าเท่ากัน
  → ถ้า Tick Value เท่ากัน = ใช้ Multiply ปกติ (Master × Multiplier)

- Volume Mode = Fixed/Percent
  → ไม่ได้รับผลจาก Auto Mapping Volume
  → คำนวณตามโหมดที่เลือก
  
- Auto Mapping Volume = OFF
  → ไม่ตรวจสอบ Tick Value
  → ใช้ Volume Mode ที่เลือกตามปกติ
"""

import logging
from typing import Dict, Optional
from datetime import datetime  # ⭐ เพิ่มสำหรับ timestamp ในอีเมล์

logger = logging.getLogger(__name__)

class CopyHandler:
    """จัดการการรับและประมวลผลสัญญาณจาก Master"""
    
    def __init__(self, copy_manager, symbol_mapper, copy_executor, session_manager, email_handler=None):
        self.copy_manager = copy_manager
        self.symbol_mapper = symbol_mapper
        self.copy_executor = copy_executor
        self.email_handler = email_handler  # ⭐ เพิ่ม email_handler

        # ✅ เพิ่ม BalanceHelper สำหรับ Percent Mode
        from .balance_helper import BalanceHelper
        self.balance_helper = BalanceHelper(session_manager)

        logger.info("[COPY_HANDLER] Initialized (v3.0 - Tick Value Auto-Detection Enabled by Default)")
    
    def process_master_signal(self, api_key: str, signal_data: Dict) -> Dict:
        """
        ประมวลผลสัญญาณจาก Master EA
        
        Args:
            api_key: API Key ของ Copy Pair
            signal_data: ข้อมูล Signal จาก Master {
                'event': 'deal_add' | 'deal_close' | 'position_modify',
                'order_id': 'order_12345',
                'account': '111111',
                'symbol': 'XAUUSD',
                'type': 'BUY' | 'SELL',
                'volume': 1.0,
                'tp': 2450.0,
                'sl': 2400.0
            }
            
        Returns:
            Dict: {'success': bool, 'message': str, 'error': str}
        """
        pair: Optional[Dict] = None
        try:
            # 1) ตรวจสอบ API Key และหา Pair
            pair = self.copy_manager.validate_api_key(api_key)
            if not pair:
                logger.warning(f"[COPY_HANDLER] Invalid API key: {api_key[:8]}...")
                return {'success': False, 'error': 'Invalid API key'}
            
            # 2) ตรวจสอบสถานะ Pair
            if pair.get('status') != 'active':
                logger.info(f"[COPY_HANDLER] Pair {pair.get('id')} is inactive")
                return {'success': False, 'error': 'Copy pair is inactive'}
            
            # 3) ตรวจสอบว่าเป็น Master account จริงหรือไม่
            master_account = str(signal_data.get('account', ''))
            if master_account != pair.get('master_account'):
                logger.warning(
                    f"[COPY_HANDLER] Account mismatch: "
                    f"received {master_account}, expected {pair.get('master_account')}"
                )
                return {'success': False, 'error': 'Master account mismatch'}
            
            # 4) ตรวจสอบว่า Slave account มีอยู่และเชื่อมต่อแล้ว
            slave_account = pair.get('slave_account')
            if not self.balance_helper.session_manager.account_exists(slave_account):
                logger.warning(f"[COPY_HANDLER] Slave account {slave_account} not found")
                return {'success': False, 'error': 'Slave account not connected'}
            
            if not self.balance_helper.session_manager.is_instance_alive(slave_account):
                logger.warning(f"[COPY_HANDLER] Slave account {slave_account} instance not alive")
                return {'success': False, 'error': 'Slave account instance not running'}
            
            # 5) แปลง Signal เป็น Command
            slave_command = self._convert_signal_to_command(signal_data, pair)
            if not slave_command:
                logger.warning("[COPY_HANDLER] Failed to convert signal to command")
                return {'success': False, 'error': 'Signal conversion failed'}
            
            # 6) ส่งคำสั่งไปยัง Slave
            logger.info(f"[COPY_HANDLER] Executing command on slave: {slave_account}")
            result = self.copy_executor.execute_on_slave(
                slave_account=pair['slave_account'],
                command=slave_command,
                pair=pair
            )
            return result
        
        except Exception as e:
            logger.error(f"[COPY_HANDLER] Error processing signal: {e}", exc_info=True)
            try:
                self.copy_executor.copy_history.record_copy_event({
                    'status': 'error',
                    'master': str(signal_data.get('account', '-')),
                    'slave': (pair.get('slave_account', '-') if isinstance(pair, dict) else '-'),
                    'action': str(signal_data.get('event', 'UNKNOWN')).upper(),
                    'symbol': signal_data.get('symbol', '-'),
                    'volume': signal_data.get('volume', ''),
                    'message': f'❌ Exception: {str(e)}'
                })
            except Exception:
                pass
            return {'success': False, 'error': str(e)}
    
    # ======================
    #  Volume Calculation
    # ======================
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
        
        🔥 TICK VALUE AUTO-DETECTION (เฉพาะ Multiply Mode):
        - เมื่อ Auto Mapping Volume = ON + Volume Mode = Multiply
          → ตรวจสอบ Tick Value อัตโนมัติ
          → ถ้า Tick Value ต่างกัน = ปรับ Volume ให้มูลค่าเท่ากัน
          → ถ้า Tick Value เท่ากัน = ใช้ Multiply ปกติ
        
        - Volume Mode = Fixed/Percent → ไม่ได้รับผลจาก Auto Mapping Volume
        
        Volume Modes:
        - multiply: Master Volume × Multiplier (รองรับ Tick Value Auto)
        - fixed: ใช้ค่าคงที่ (ไม่เกี่ยวกับ Auto Mapping Volume)
        - percent: คำนวณจาก % ของ Balance (ไม่เกี่ยวกับ Auto Mapping Volume)
        
        Args:
            master_volume: Volume จาก Master
            settings: การตั้งค่า Pair
            slave_account: หมายเลขบัญชี Slave
            symbol: Symbol ที่จะเทรดบน Slave
            master_account: หมายเลขบัญชี Master
            master_symbol: Symbol ต้นฉบับจาก Master
            
        Returns:
            float: Volume ที่คำนวณแล้ว
        """
        try:
            volume_mode = settings.get('volume_mode') or settings.get('volumeMode', 'multiply')
            multiplier = float(settings.get('multiplier', 2))
            auto_map_volume = settings.get('auto_map_volume', True)
            
            # ตรวจสอบข้อมูล Symbol ของ Slave
            symbol_info = self.balance_helper.session_manager.get_symbol_info(slave_account, symbol)
            if not symbol_info:
                logger.warning(f"[COPY_HANDLER] Cannot get symbol info for {symbol}, using master volume")
                return max(master_volume, 0.01)
            
            min_lot = float(symbol_info.get('volume_min', 0.01))
            max_lot = float(symbol_info.get('volume_max', 100.0))
            lot_step = float(symbol_info.get('volume_step', 0.01))
            
            # 🔥 TICK VALUE AUTO-DETECTION
            # เงื่อนไข: Auto Mapping Volume = ON + Volume Mode = Multiply + มีข้อมูล Master/Slave
            if (auto_map_volume and 
                volume_mode == 'multiply' and 
                master_account and 
                master_symbol):
                
                logger.info("[COPY_HANDLER] 🔥 Tick Value Auto-Detection enabled (Auto Mapping Volume = ON + Multiply Mode)")
                
                # ดึงข้อมูล Symbol ของ Master และ Slave
                master_symbol_info = self.balance_helper.session_manager.get_symbol_info(
                    master_account, 
                    master_symbol
                )
                
                if master_symbol_info and symbol_info:
                    # ดึง Tick Value (contract size)
                    master_tick_value = float(master_symbol_info.get('trade_contract_size', 0))
                    slave_tick_value = float(symbol_info.get('trade_contract_size', 0))
                    
                    # ตรวจสอบว่า Tick Value ต่างกันหรือไม่
                    if master_tick_value > 0 and slave_tick_value > 0 and master_tick_value != slave_tick_value:
                        # ✅ Tick Value ต่างกัน → ปรับ Volume ให้มูลค่าเท่ากัน
                        tick_ratio = master_tick_value / slave_tick_value
                        calculated_volume = master_volume * tick_ratio
                        
                        logger.info(
                            f"[COPY_HANDLER] ✅ TICK VALUE DETECTED (Different):\n"
                            f"  Master: {master_symbol} | Tick Value = {master_tick_value} | Volume = {master_volume}\n"
                            f"  Slave: {symbol} | Tick Value = {slave_tick_value}\n"
                            f"  Ratio = {tick_ratio:.4f} | Calculated Volume = {calculated_volume:.2f}\n"
                            f"  Trade Value: Master = ${master_volume * master_tick_value:.2f} | "
                            f"Slave = ${calculated_volume * slave_tick_value:.2f}"
                        )
                        
                        # ตรวจสอบขอบเขตและปัดเศษ
                        calculated_volume = self._adjust_volume(calculated_volume, min_lot, max_lot, lot_step)
                        
                        logger.info(
                            f"[COPY_HANDLER] 🎯 TICK VALUE AUTO-ADJUSTED: "
                            f"{master_volume} → {calculated_volume} "
                            f"(Equal Value: ${calculated_volume * slave_tick_value:.2f})"
                        )
                        
                        return calculated_volume
                    
                    elif master_tick_value == slave_tick_value and master_tick_value > 0:
                        # ℹ️ Tick Value เท่ากัน → ใช้ Multiply ปกติ
                        logger.info(
                            f"[COPY_HANDLER] ℹ️ Tick Values are EQUAL ({master_tick_value}), "
                            f"using standard Multiply: {master_volume} × {multiplier}"
                        )
                    else:
                        # ⚠️ ไม่มีข้อมูล Tick Value → ใช้ Multiply ปกติ
                        logger.info(
                            f"[COPY_HANDLER] ⚠️ Tick Value data incomplete, "
                            f"using standard Multiply: {master_volume} × {multiplier}"
                        )
            
            # 📌 STANDARD VOLUME MODES
            # ใช้เมื่อ:
            # 1. Auto Mapping Volume = OFF หรือ
            # 2. Volume Mode = Fixed/Percent (ไม่เกี่ยวกับ Auto Mapping Volume) หรือ
            # 3. Volume Mode = Multiply + Tick Values เท่ากัน หรือ
            # 4. ไม่มีข้อมูล Master/Slave Symbol
            
            logger.info(f"[COPY_HANDLER] 📌 Using Volume Mode: {volume_mode}")
            
            if volume_mode == 'multiply':
                # โหมด Multiply: Volume × Multiplier
                calculated_volume = master_volume * multiplier
                logger.info(f"[COPY_HANDLER] Multiply mode: {master_volume} × {multiplier} = {calculated_volume}")
            
            elif volume_mode == 'fixed':
                # โหมด Fixed: ใช้ค่า Multiplier เป็น Volume คงที่
                calculated_volume = multiplier
                logger.info(f"[COPY_HANDLER] Fixed mode: Volume = {calculated_volume}")
            
            elif volume_mode == 'percent':
                # โหมด Percent: คำนวณจาก % ของ Balance
                balance = self.balance_helper.get_account_balance(slave_account)
                if balance <= 0:
                    logger.warning(f"[COPY_HANDLER] Cannot get balance for {slave_account}, using min lot")
                    return min_lot
                
                risk_amount = balance * (multiplier / 100)
                point_value = 10  # ค่าประมาณ
                calculated_volume = risk_amount / (point_value * 100)
                
                logger.info(
                    f"[COPY_HANDLER] Percent mode: "
                    f"Balance={balance} | Risk={multiplier}% | Volume={calculated_volume}"
                )
            
            else:
                # โหมดที่ไม่รู้จัก → ใช้ multiply mode
                logger.warning(f"[COPY_HANDLER] Unknown volume mode: {volume_mode}, using multiply mode")
                calculated_volume = master_volume * multiplier
            
            # ตรวจสอบขอบเขตและปัดเศษ
            # ⭐ ดึง strategy (Default = 'warn' - แจ้งเตือนแต่ยังเทรด)
            min_volume_strategy = settings.get('min_volume_strategy', 'warn')
            
            # เฉพาะ 'skip' เท่านั้นที่จะข้ามการเทรด
            skip_if_too_small = (min_volume_strategy == 'skip')
            
            calculated_volume = self._adjust_volume(
                calculated_volume, 
                min_lot, 
                max_lot, 
                lot_step,
                skip_if_too_small=skip_if_too_small
            )
            
            # ⭐ ถ้าได้ 0 = strategy เป็น 'skip' และ volume น้อยเกินไป
            if calculated_volume == 0:
                logger.warning(
                    f"[COPY_HANDLER] ❌ Trade SKIPPED (strategy='skip'): Volume too small\n"
                    f"  Master volume: {master_volume}\n"
                    f"  Calculated volume: {master_volume * tick_ratio if master_account and master_symbol else master_volume * multiplier:.5f}\n"
                    f"  Min lot: {min_lot}\n"
                    f"  💡 Change strategy to 'warn' to trade with min_lot instead"
                )
                return 0
            
            return calculated_volume

        except Exception as e:
            logger.error(f"[COPY_HANDLER] Error calculating volume: {e}")
            return max(master_volume, 0.01)
    
    def _adjust_volume(
        self, 
        volume: float, 
        min_lot: float, 
        max_lot: float, 
        lot_step: float,
        skip_if_too_small: bool = False  # ⭐ NEW: Option to skip trade
    ) -> float:
        """
        ปรับ volume ให้อยู่ในขอบเขตที่ถูกต้อง
        
        ⭐ NEW: รองรับ 3 Strategies เมื่อ Volume น้อยเกินไป:
        1. Round Up to Min Lot (Default)
        2. Skip Trade (ถ้า skip_if_too_small = True)
        3. Warning + Use Min Lot
        
        Args:
            volume: Volume ที่คำนวณได้
            min_lot: Volume ต่ำสุด
            max_lot: Volume สูงสุด
            lot_step: ขั้นของ Volume
            skip_if_too_small: ถ้า True จะคืน 0 เมื่อ volume น้อยเกินไป
            
        Returns:
            float: Volume ที่ปรับแล้ว (หรือ 0 ถ้าต้องการ skip)
        """
        original_volume = volume
        
        # ตรวจสอบว่า Volume น้อยกว่า Min Lot มากหรือไม่
        if volume < min_lot:
            # คำนวณ % ที่ต่างจาก Min Lot
            percentage_diff = ((min_lot - volume) / min_lot) * 100
            
            # ⭐ แจ้งเตือนตามระดับความแตกต่าง + ส่งอีเมล์
            if percentage_diff > 80:  # ⭐ เปลี่ยนจาก 90% เป็น 80%
                # 🚨 CRITICAL: ต่างกันมากกว่า 80%
                log_message = (
                    f"⚠️ CRITICAL WARNING: Volume {volume:.5f} is {percentage_diff:.1f}% less than min_lot {min_lot}!\n"
                    f"  Calculated volume is EXTREMELY small.\n"
                    f"  Trade value will be {(min_lot/volume):.1f}x HIGHER than Master!\n"
                    f"  Master will risk: ${volume * 10000:.2f} (example)\n"
                    f"  Slave will risk: ${min_lot * 10000:.2f} (example)"
                )
                logger.error(f"[COPY_HANDLER] {log_message}")
                
                # ⭐ ส่งอีเมล์แจ้งเตือน CRITICAL
                if self.email_handler:
                    email_subject = "⚠️ CRITICAL: Min Volume Warning"
                    email_message = f"""
🚨 CRITICAL Min Volume Alert

Volume Calculated: {volume:.5f} lot
Min Lot Required: {min_lot} lot
Difference: {percentage_diff:.1f}% less than minimum

Risk Multiplier: {(min_lot/volume):.1f}x HIGHER than Master

Example Risk:
- Master Risk: ${volume * 10000:.2f}
- Slave Risk: ${min_lot * 10000:.2f}

{'⚠️ Trade will proceed with min_lot ' + str(min_lot) if not skip_if_too_small else '❌ Trade SKIPPED (strategy=skip)'}

Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""
                    try:
                        self.email_handler.send_alert(email_subject, email_message.strip(), "high")
                        logger.info("[COPY_HANDLER] ✅ CRITICAL email alert sent successfully")
                    except Exception as e:
                        logger.error(f"[COPY_HANDLER] ❌ Failed to send CRITICAL email: {e}")
                
                # ✅ ถ้าเป็น skip mode และต่างกันมากกว่า 80% → Skip
                if skip_if_too_small:
                    logger.warning(
                        f"[COPY_HANDLER] ❌ SKIPPING TRADE: Volume too small (>80% difference, strategy='skip')"
                    )
                    
                    # ⭐ ส่งอีเมล์แจ้งเตือนการ Skip
                    if self.email_handler:
                        skip_email_subject = "❌ Trade SKIPPED - Min Volume"
                        skip_email_message = f"""
❌ Trade Skipped Alert

Reason: Volume difference exceeds 80% threshold

Volume Calculated: {volume:.5f} lot
Min Lot Required: {min_lot} lot
Difference: {percentage_diff:.1f}%

Strategy: skip
Action: Trade NOT executed

This trade was skipped to maintain accurate risk management.
Consider increasing Master volume or changing strategy to 'warn'.

Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""
                        try:
                            self.email_handler.send_alert(skip_email_subject, skip_email_message.strip(), "high")
                            logger.info("[COPY_HANDLER] ✅ SKIP email alert sent successfully")
                        except Exception as e:
                            logger.error(f"[COPY_HANDLER] ❌ Failed to send SKIP email: {e}")
                    
                    return 0  # ⭐ คืน 0 = ไม่เทรด (เฉพาะเมื่อเลือก skip)
                else:
                    logger.warning(
                        f"[COPY_HANDLER] ⚠️ Proceeding with min_lot {min_lot} anyway (strategy='warn')..."
                    )
                
            elif percentage_diff > 50:
                # ⚠️ WARNING: ต่างกัน 50-80%
                log_message = (
                    f"⚠️ WARNING: Volume {volume:.5f} is {percentage_diff:.1f}% less than min_lot {min_lot}\n"
                    f"  Trade value will be {(min_lot/volume):.1f}x HIGHER than Master.\n"
                    f"  Adjusted to min_lot {min_lot} and proceeding..."
                )
                logger.warning(f"[COPY_HANDLER] {log_message}")
                
                # ⭐ ส่งอีเมล์แจ้งเตือน WARNING
                if self.email_handler:
                    email_subject = "⚠️ Min Volume Warning"
                    email_message = f"""
⚠️ Min Volume Alert

Volume Calculated: {volume:.5f} lot
Min Lot Required: {min_lot} lot
Difference: {percentage_diff:.1f}% less than minimum

Risk Multiplier: {(min_lot/volume):.1f}x HIGHER than Master

Action: Trade will proceed with min_lot {min_lot}

Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""
                    try:
                        self.email_handler.send_alert(email_subject, email_message.strip(), "normal")
                        logger.info("[COPY_HANDLER] ✅ WARNING email alert sent successfully")
                    except Exception as e:
                        logger.error(f"[COPY_HANDLER] ❌ Failed to send WARNING email: {e}")
            
            else:
                # ℹ️ INFO: ต่างกันน้อยกว่า 50%
                logger.info(
                    f"[COPY_HANDLER] Volume {volume:.5f} < min_lot {min_lot}, adjusted to {min_lot}"
                )
            
            volume = min_lot

        # ตรวจสอบ Max Lot
        if volume > max_lot:
            logger.warning(
                f"[COPY_HANDLER] Volume {volume} > max_lot {max_lot}, adjusted to {max_lot}"
            )
            volume = max_lot

        # ปัดเศษตาม lot_step
        steps = round(volume / lot_step)
        adjusted_volume = steps * lot_step

        # ตรวจสอบอีกครั้งหลังปัดเศษ
        if adjusted_volume < min_lot:
            adjusted_volume = min_lot
            
        # ⭐ Log สรุป
        if abs(adjusted_volume - original_volume) > 0.001:
            ratio_change = (adjusted_volume / original_volume) if original_volume > 0 else 0
            logger.info(
                f"[COPY_HANDLER] Volume adjustment: {original_volume:.5f} → {adjusted_volume:.5f} "
                f"(×{ratio_change:.2f} = {ratio_change*100:.0f}% of original)"
            )

        return round(adjusted_volume, 2)

    # ======================
    #  Signal Conversion
    # ======================
    def _convert_signal_to_command(self, signal_data: Dict, pair: Dict) -> Optional[Dict]:
        """
        แปลงสัญญาณจาก Master เป็นคำสั่งสำหรับ Slave
        
        ✅ รองรับ Order Tracking และ Tick Value Auto-Detection
        
        Args:
            signal_data: ข้อมูล Signal จาก Master
            pair: ข้อมูล Copy Pair
            
        Returns:
            Dict: Command สำหรับ Slave EA หรือ None ถ้าแปลงไม่สำเร็จ
        """
        try:
            settings = pair.get('settings', {})
            
            # ✅ Normalize keys (รองรับทั้ง camelCase และ snake_case)
            auto_map_symbol = settings.get('auto_map_symbol') or settings.get('autoMapSymbol', True)
            auto_map_volume = settings.get('auto_map_volume') or settings.get('autoMapVolume', True)
            copy_psl = settings.get('copy_psl') or settings.get('copyPSL', True)
            
            # ดึงข้อมูลพื้นฐาน
            event = str(signal_data.get('event', '')).lower()
            master_symbol = str(signal_data.get('symbol', ''))  # ⭐ เก็บ symbol ต้นฉบับ
            trade_type = str(signal_data.get('type', '')).upper()
            volume = float(signal_data.get('volume', 0))
            
            # ✅ ดึง order_id จาก Master Signal
            order_id = signal_data.get('order_id', '')
            
            logger.info(
                f"[COPY_HANDLER] Converting signal: "
                f"event={event} | symbol={master_symbol} | type={trade_type} | "
                f"volume={volume} | order_id={order_id}"
            )
            
            # ==================
            # 1. Map Symbol
            # ==================
            slave_symbol = master_symbol  # Default
            if auto_map_symbol:
                mapped_symbol = self.symbol_mapper.map_symbol(master_symbol)
                if not mapped_symbol:
                    logger.warning(
                        f"[COPY_HANDLER] Cannot map symbol: {master_symbol}, using original"
                    )
                    slave_symbol = master_symbol
                else:
                    logger.info(
                        f"[COPY_HANDLER] Symbol mapped: {master_symbol} → {mapped_symbol}"
                    )
                    slave_symbol = mapped_symbol
            
            # ==================
            # 2. Map Volume (⭐ รองรับ Tick Value อัตโนมัติ)
            # ==================
            if auto_map_volume:
                original_volume = volume
                volume = self._calculate_slave_volume(
                    master_volume=volume,
                    settings=settings,
                    slave_account=pair['slave_account'],
                    symbol=slave_symbol,  # ใช้ symbol ที่แปลงแล้ว
                    master_account=pair['master_account'],  # ⭐ ส่ง master account
                    master_symbol=master_symbol  # ⭐ ส่ง master symbol ต้นฉบับ
                )
                logger.info(
                    f"[COPY_HANDLER] Volume adjusted: {original_volume} → {volume}"
                )
            
            # ==================
            # 3. สร้าง Comment
            # ==================
            copy_comment = f"COPY_{order_id}" if order_id else f"Copy from Master {pair['master_account']}"
            logger.info(f"[COPY_HANDLER] Generated comment: {copy_comment}")
            
            # ==================
            # 4. สร้างคำสั่งตาม Event Type
            # ==================
            
            # --- EVENT: OPEN ORDER ---
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
                        logger.info(f"[COPY_HANDLER] ✅ TP copied: {command['take_profit']}")
                    if signal_data.get('sl') is not None:
                        command['stop_loss'] = float(signal_data['sl'])
                        logger.info(f"[COPY_HANDLER] ✅ SL copied: {command['stop_loss']}")
                    logger.info(f"[COPY_HANDLER] Copy TP/SL is ENABLED")
                else:
                    logger.info(f"[COPY_HANDLER] ⚠️ Copy TP/SL is DISABLED")
                
                logger.info(
                    f"[COPY_HANDLER] ✅ OPEN Command created: "
                    f"{trade_type} {slave_symbol} {volume} lots | Comment: {copy_comment}"
                )
                return command
            
            # --- EVENT: CLOSE ORDER ---
            elif event in ['deal_close', 'position_close']:
                logger.info(f"[COPY_HANDLER] Processing CLOSE ORDER event")
                
                if order_id:
                    # ⭐ ปิดด้วย Comment
                    command = {
                        'action': 'close_by_comment',
                        'comment': copy_comment,
                        'symbol': slave_symbol
                    }
                    logger.info(f"[COPY_HANDLER] ✅ CLOSE Command created (by Comment): {copy_comment}")
                    return command
                else:
                    # Fallback: ปิดทั้งหมดของ Symbol
                    command = {
                        'action': 'close',
                        'symbol': slave_symbol,
                        'order_type': 'close'
                    }
                    logger.warning(
                        f"[COPY_HANDLER] ⚠️ No order_id, using fallback CLOSE for symbol: {slave_symbol}"
                    )
                    return command
            
            # --- EVENT: MODIFY ORDER ---
            elif event in ['position_modify', 'modify']:
                logger.info(f"[COPY_HANDLER] Processing MODIFY ORDER event")
                
                if copy_psl and order_id:
                    command = {
                        'action': 'modify_position',
                        'comment': copy_comment,
                        'symbol': slave_symbol,
                        'take_profit': (
                            float(signal_data.get('tp', 0)) 
                            if signal_data.get('tp') is not None 
                            else None
                        ),
                        'stop_loss': (
                            float(signal_data.get('sl', 0)) 
                            if signal_data.get('sl') is not None 
                            else None
                        )
                    }
                    logger.info(
                        f"[COPY_HANDLER] ✅ MODIFY Command created: "
                        f"Comment: {copy_comment} | TP: {command.get('take_profit')} | "
                        f"SL: {command.get('stop_loss')}"
                    )
                    return command
                else:
                    if not copy_psl:
                        logger.info(f"[COPY_HANDLER] copyPSL is disabled, ignoring MODIFY event")
                    if not order_id:
                        logger.warning(f"[COPY_HANDLER] No order_id provided, cannot modify")
                    return None
            
            # --- UNKNOWN EVENT ---
            logger.warning(f"[COPY_HANDLER] ⚠️ Unknown event type: {event}")
            return None
            
        except Exception as e:
            logger.error(f"[COPY_HANDLER] ❌ Error converting signal: {e}", exc_info=True)
            return None


# =================== Testing & Debugging ===================

def test_copy_handler():
    """ฟังก์ชันทดสอบ CopyHandler พร้อม Tick Value Support"""
    print("\n" + "="*80)
    print("🧪 Testing CopyHandler - Tick Value Auto-Detection")
    print("="*80)
    
    # Mock objects
    class MockCopyManager:
        def validate_api_key(self, key):
            return {
                'id': 'pair_001',
                'status': 'active',
                'master_account': '111111',
                'slave_account': '222222',
                'settings': {
                    'auto_map_symbol': True,
                    'auto_map_volume': True,
                    'copy_psl': True,
                    'volume_mode': 'multiply',
                    'multiplier': 2.0
                }
            }
    
    class MockSymbolMapper:
        def map_symbol(self, symbol):
            # Map USOIL → USOIL.cash
            if symbol == 'USOIL':
                return 'USOIL.cash'
            return symbol
    
    class MockCopyExecutor:
        class MockCopyHistory:
            def record_copy_event(self, event):
                print(f"  📝 Event Recorded: {event}")
        
        def __init__(self):
            self.copy_history = self.MockCopyHistory()
        
        def execute_on_slave(self, slave_account, command, pair):
            print(f"  ✅ Command sent to Slave: {command}")
            return {'success': True}
    
    class MockSessionManager:
        def account_exists(self, account):
            return True
        def is_instance_alive(self, account):
            return True
        def get_symbol_info(self, account, symbol):
            # Mock symbol info ตามภาพที่คุณส่งมา
            if symbol == 'USOIL':
                return {
                    'volume_min': 0.01,
                    'volume_max': 100.0,
                    'volume_step': 0.01,
                    'trade_contract_size': 1000.0  # ⭐ Crude Oil = 1000
                }
            elif symbol == 'USOIL.cash':
                return {
                    'volume_min': 0.01,
                    'volume_max': 100.0,
                    'volume_step': 0.01,
                    'trade_contract_size': 100.0  # ⭐ WTI CFD = 100
                }
            return None
    
    # Initialize handler
    handler = CopyHandler(
        MockCopyManager(),
        MockSymbolMapper(),
        MockCopyExecutor(),
        MockSessionManager()
    )
    
    # Test: Open Order with Tick Value Auto-Detection
    print("\n📌 Test: OPEN ORDER - Tick Value Auto-Detection")
    print("-" * 80)
    signal_open = {
        'event': 'deal_add',
        'order_id': 'order_12345',
        'account': '111111',
        'symbol': 'USOIL',
        'type': 'BUY',
        'volume': 0.01,  # ⭐ Master ซื้อ 0.01 lot
        'tp': 75.50,
        'sl': 73.00
    }
    
    print("Master Signal:")
    print(f"  Symbol: {signal_open['symbol']}")
    print(f"  Volume: {signal_open['volume']} lot")
    print(f"  Tick Value: 1000")
    print(f"  Trade Value: ${signal_open['volume'] * 1000}")
    print()
    
    result = handler.process_master_signal('test_key', signal_open)
    print(f"\nResult: {result}")
    
    print("\n" + "="*80)
    print("✅ Tick Value Test Completed!")
    print("="*80 + "\n")


if __name__ == '__main__':
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )
    
    # Run tests
    test_copy_handler()
