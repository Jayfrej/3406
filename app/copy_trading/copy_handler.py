"""
Copy Trading Handler - VERSION v3.4 WITH PARTIAL CLOSE
แก้ไข:
1. แปล Symbol ทุกครั้งสำหรับทุก Slave Account (v3.3)
2. แปลง trade_type เป็น lowercase สำหรับ action (v3.3)
3. 🔥 รองรับ Partial Close Volume (v3.4) - NEW!

Version: 3.4 - Partial Close Support
"""

import logging
from typing import Dict, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

class CopyHandler:
    """จัดการการรับและประมวลผลสัญญาณจาก Master"""

    def __init__(self, copy_manager, symbol_mapper, copy_executor, session_manager, broker_data_manager=None, balance_manager=None, email_handler=None):
        self.copy_manager = copy_manager
        self.symbol_mapper = symbol_mapper
        self.copy_executor = copy_executor
        self.email_handler = email_handler

        # ⭐ เพิ่ม broker_data_manager และ balance_manager
        self.broker_manager = broker_data_manager
        self.balance_manager = balance_manager

        from .balance_helper import BalanceHelper
        self.balance_helper = BalanceHelper(session_manager, balance_manager)

        logger.info("[COPY_HANDLER] Initialized (v3.4 - Partial Close Support)")

    def _get_action_type(self, signal_data: Dict) -> str:
        """
        แปลง event type เป็น action type ที่ถูกต้อง
        - DEAL_ADD/POSITION_OPEN → BUY/SELL (จาก type field)
        - DEAL_CLOSE/POSITION_CLOSE → CLOSE
        - POSITION_MODIFY/ORDER_MODIFY → MODIFY
        """
        event = str(signal_data.get('event', '')).lower()
        trade_type = str(signal_data.get('type', '')).upper()

        # OPEN orders - use trade type
        if event in ['deal_add', 'order_add', 'deal_open', 'position_add', 'position_open']:
            if trade_type in ['BUY', 'LONG', 'CALL', '0']:
                return 'BUY'
            elif trade_type in ['SELL', 'SHORT', 'PUT', '1']:
                return 'SELL'
            else:
                return 'OPEN'

        # CLOSE orders
        elif event in ['deal_close', 'position_close']:
            return 'CLOSE'

        # MODIFY orders
        elif event in ['position_modify', 'order_modify', 'modify']:
            return 'MODIFY'

        # Fallback - use type or event
        return trade_type if trade_type else event.upper() if event else 'UNKNOWN'

    def _convert_signal_to_command(self, signal_data: Dict, pair: Dict) -> Optional[Dict]:
        """
        แปลงสัญญาณจาก Master เป็นคำสั่งสำหรับ Slave
        🔥 v3.4: รองรับ partial close volume
        """
        try:
            settings = pair.get('settings', {})

            # Helper function
            def get_setting(key_snake, key_camel, default):
                return settings.get(key_snake, settings.get(key_camel, default))
            
            auto_map_symbol = get_setting('auto_map_symbol', 'autoMapSymbol', True)
            auto_map_volume = get_setting('auto_map_volume', 'autoMapVolume', True)
            copy_psl = get_setting('copy_psl', 'copyPSL', True)
            
            # ดึงข้อมูลพื้นฐาน
            event = str(signal_data.get('event', '')).lower()
            master_symbol = str(signal_data.get('symbol', ''))
            trade_type = str(signal_data.get('type', '')).upper()
            volume = float(signal_data.get('volume', 0))
            order_id = signal_data.get('order_id', '')
            
            logger.info(
                f"[COPY_HANDLER] Signal Conversion: "
                f"event={event.upper()} | symbol={master_symbol} | volume={volume} | "
                f"AutoMapSymbol={auto_map_symbol} | CopyPSL={copy_psl}"
            )
            
            # Generate Comment
            slave_account = pair.get('slave_account')
            master_account = pair.get('master_account')
            copy_comment = f"COPY_{order_id}" if order_id else f"Copy_{master_account}"
            
            # EVENT: OPEN ORDER
            if event in ['deal_add', 'order_add', 'deal_open', 'position_add', 'position_open']:
                logger.info(f"[COPY_HANDLER] Processing OPEN ORDER event")

                # ⭐ แปลง trade_type เป็น lowercase (รองรับ CALL/PUT aliases)
                if trade_type in ['BUY', 'LONG', 'CALL', '0']:
                    action = 'buy'
                elif trade_type in ['SELL', 'SHORT', 'PUT', '1']:
                    action = 'sell'
                else:
                    logger.error(f"[COPY_HANDLER] Unknown trade type: {trade_type}")
                    return None

                # 🔥 รับ order_type และ price จาก Master signal
                order_type = str(signal_data.get('order_type', 'market')).lower()
                price = float(signal_data.get('price', 0))

                command = {
                    'action': action,  # ✅ lowercase
                    'symbol': master_symbol,
                    'volume': volume,
                    'order_type': order_type,  # 🔥 ใช้ order_type จาก Master
                    'comment': copy_comment
                }

                # เพิ่ม price สำหรับ pending orders
                if order_type in ['limit', 'stop'] and price > 0:
                    command['price'] = price
                    logger.info(f"[COPY_HANDLER] Pending order: {order_type} @ {price}")

                if copy_psl:
                    if signal_data.get('tp') is not None:
                        command['take_profit'] = float(signal_data['tp'])
                    if signal_data.get('sl') is not None:
                        command['stop_loss'] = float(signal_data['sl'])

                logger.info(
                    f"[COPY_HANDLER] ✅ OPEN Command created: "
                    f"{action} {master_symbol} {volume} lots"
                    f"{' ' + order_type if order_type != 'market' else ''}"
                    f"{' @ ' + str(price) if price > 0 else ''}"
                )
                return command
            
            # 🔥 EVENT: CLOSE ORDER - รองรับ Partial Close
            elif event in ['deal_close', 'position_close']:
                logger.info(f"[COPY_HANDLER] Processing CLOSE ORDER event - volume={volume}")
                
                # 🔥 รองรับ Partial Close - ตรวจสอบ volume ที่ส่งมา
                if volume > 0:
                    # Partial Close - ส่ง volume ที่คำนวณแล้วไปให้ slave
                    command = {
                        'action': 'close',
                        'symbol': master_symbol,
                        'volume': volume,  # 🔥 ส่ง volume ที่จะปิด (คำนวณแล้วใน _calculate_slave_volume)
                        'comment': copy_comment
                    }
                    
                    logger.info(f"[COPY_HANDLER] ✅ PARTIAL CLOSE Command: {master_symbol} volume={volume}")
                    return command
                
                # Full Close หรือ close by comment
                elif order_id:
                    command = {
                        'action': 'close',
                        'comment': copy_comment,
                        'symbol': master_symbol
                    }
                    logger.info(f"[COPY_HANDLER] ✅ CLOSE by comment: {copy_comment}")
                    return command
                
                # Close all symbol
                else:
                    command = {
                        'action': 'close_symbol',
                        'symbol': master_symbol
                    }
                    logger.info(f"[COPY_HANDLER] ✅ CLOSE all: {master_symbol}")
                    return command
            
            # EVENT: MODIFY ORDER
            elif event in ['position_modify', 'order_modify', 'modify']:
                logger.info(f"[COPY_HANDLER] Processing MODIFY ORDER event")
                
                if not copy_psl:
                    logger.info(f"[COPY_HANDLER] ⚠️ Copy TP/SL disabled, skipping MODIFY")
                    return None
                
                new_tp = signal_data.get('tp')
                new_sl = signal_data.get('sl')
                
                if order_id:
                    command = {
                        'action': 'modify',
                        'comment': copy_comment,
                        'symbol': master_symbol
                    }
                    if new_tp is not None:
                        command['take_profit'] = float(new_tp)
                    if new_sl is not None:
                        command['stop_loss'] = float(new_sl)
                    
                    logger.info(f"[COPY_HANDLER] ✅ MODIFY Command created: {copy_comment}")
                    return command
            
            logger.warning(f"[COPY_HANDLER] Unknown event type: {event.upper()}")
            return None

        except Exception as e:
            logger.error(f"[COPY_HANDLER] Error converting signal: {str(e)}", exc_info=True)

            # แจ้งเตือน conversion error
            if self.email_handler:
                try:
                    master_account = pair.get('master_account', 'Unknown')
                    slave_account = pair.get('slave_account', 'Unknown')
                    self.email_handler.send_copy_trading_error_alert(
                        error_type='Signal Conversion Failed',
                        master_account=master_account,
                        slave_account=slave_account,
                        error_message=f"Failed to convert signal: {str(e)}",
                        signal_data=signal_data
                    )
                except Exception as email_err:
                    logger.error(f"[COPY_HANDLER] Failed to send error email: {email_err}")

            return None

    def process_master_signal(self, api_key: str, signal_data: Dict) -> Dict:
        """
        ประมวลผลสัญญาณจาก Master EA และส่งไปทุก Slave ที่ใช้ API key เดียวกัน

        🔥 v3.4: รองรับ partial close volume validation
        """
        try:
            matching_pairs = self._get_all_pairs_by_api_key(api_key)

            if not matching_pairs:
                logger.warning(f"[COPY_HANDLER] Invalid API key: {api_key[:8]}...")
                return {'success': False, 'error': 'Invalid API key'}

            # ⚠️ ตรวจสอบว่า Master account ถูก PAUSE หรือยังไม่ได้ activate หรือไม่
            master_account = str(signal_data.get('account', ''))
            if master_account:
                master_info = self.balance_helper.session_manager.get_account_info(master_account)
                if master_info:
                    # ตรวจสอบ PAUSE
                    if master_info.get('status') == 'PAUSE':
                        logger.warning(f"[COPY_HANDLER] Master {master_account} is PAUSED - rejecting signal")

                        # บันทึก error ลง history สำหรับทุก slave ที่เกี่ยวข้อง
                        for pair in matching_pairs:
                            if master_account == pair.get('master_account'):
                                slave_account = pair.get('slave_account', '-')
                                try:
                                    self.copy_executor.copy_history.record_copy_event({
                                        'master': master_account,
                                        'slave': slave_account,
                                        'action': self._get_action_type(signal_data),
                                        'order_type': signal_data.get('order_type', 'market'),
                                        'symbol': signal_data.get('symbol', '-'),
                                        'price': signal_data.get('price', ''),
                                        'tp': signal_data.get('tp', ''),
                                        'sl': signal_data.get('sl', ''),
                                        'volume': signal_data.get('volume', ''),
                                        'status': 'error',
                                        'message': 'Master account is paused'
                                    })
                                except Exception as log_err:
                                    logger.error(f"[COPY_HANDLER] Failed to log master paused error: {log_err}")

                        return {
                            'success': False,
                            'error': 'Master account is paused',
                            'master_account': master_account
                        }

                    # ตรวจสอบว่ายังไม่ได้ activate (Wait for Activate)
                    if master_info.get('status') == 'Wait for Activate' or not master_info.get('symbol_received', False):
                        logger.warning(f"[COPY_HANDLER] Master {master_account} not activated - rejecting signal")

                        # บันทึก error ลง history สำหรับทุก slave ที่เกี่ยวข้อง
                        for pair in matching_pairs:
                            if master_account == pair.get('master_account'):
                                slave_account = pair.get('slave_account', '-')
                                try:
                                    self.copy_executor.copy_history.record_copy_event({
                                        'master': master_account,
                                        'slave': slave_account,
                                        'action': self._get_action_type(signal_data),
                                        'order_type': signal_data.get('order_type', 'market'),
                                        'symbol': signal_data.get('symbol', '-'),
                                        'price': signal_data.get('price', ''),
                                        'tp': signal_data.get('tp', ''),
                                        'sl': signal_data.get('sl', ''),
                                        'volume': signal_data.get('volume', ''),
                                        'status': 'error',
                                        'message': 'Master account not activated - waiting for Symbol data'
                                    })
                                except Exception as log_err:
                                    logger.error(f"[COPY_HANDLER] Failed to log master not activated error: {log_err}")

                        return {
                            'success': False,
                            'error': 'Master account not activated - waiting for Symbol data',
                            'master_account': master_account
                        }

            # 🔥 ตรวจสอบ volume และ event type
            master_volume = float(signal_data.get('volume', 0))
            event = str(signal_data.get('event', '')).lower()
            
            if event in ['deal_close', 'position_close']:
                if master_volume > 0:
                    logger.info(f"[COPY_HANDLER] 🔥 PARTIAL CLOSE detected: volume={master_volume}")
                else:
                    logger.info(f"[COPY_HANDLER] FULL CLOSE detected")
            
            logger.info(f"[COPY_HANDLER] Found {len(matching_pairs)} pair(s) using this API key")
            
            # ⭐ เก็บ Symbol ต้นฉบับจาก Master
            original_master_symbol = str(signal_data.get('symbol', ''))
            master_account = str(signal_data.get('account', ''))
            
            logger.info(
                f"[COPY_HANDLER] Master signal: account={master_account}, "
                f"symbol={original_master_symbol}, event={signal_data.get('event')}, volume={master_volume}"
            )
            
            # กรองเฉพาะ pairs ที่ active
            valid_pairs = []
            for pair in matching_pairs:
                if master_account != pair.get('master_account'):
                    continue
                
                if pair.get('status') != 'active':
                    logger.info(f"[COPY_HANDLER] Pair {pair.get('id')} inactive (status)")
                    continue
                
                if pair.get('active') is False:
                    logger.info(f"[COPY_HANDLER] Pair {pair.get('id')} inactive (flag)")
                    continue
                
                slave_account = pair.get('slave_account')
                if not self.balance_helper.session_manager.account_exists(slave_account):
                    logger.warning(f"[COPY_HANDLER] Slave {slave_account} not found")
                    continue
                
                if not self.balance_helper.session_manager.is_instance_alive(slave_account):
                    logger.warning(f"[COPY_HANDLER] Slave {slave_account} not alive")
                    continue

                # Check if slave account is PAUSED
                slave_info = self.balance_helper.session_manager.get_account_info(slave_account)
                if slave_info and slave_info.get('status') == 'PAUSE':
                    logger.warning(f"[COPY_HANDLER] Slave {slave_account} is PAUSED - skipping")
                    # Record error in copy history
                    try:
                        self.copy_executor.copy_history.record_copy_event({
                            'master': master_account,
                            'slave': slave_account,
                            'action': self._get_action_type(signal_data),
                            'order_type': signal_data.get('order_type', 'market'),
                            'symbol': original_master_symbol,
                            'price': signal_data.get('price', ''),
                            'tp': signal_data.get('tp', ''),
                            'sl': signal_data.get('sl', ''),
                            'volume': master_volume,
                            'status': 'error',
                            'message': 'Slave account is paused'
                        })
                    except Exception as log_err:
                        logger.error(f"[COPY_HANDLER] Failed to log paused account error: {log_err}")
                    continue

                valid_pairs.append(pair)
            
            if not valid_pairs:
                logger.warning(f"[COPY_HANDLER] No valid pairs for master {master_account}")
                return {'success': False, 'error': 'No valid slave accounts'}
            
            logger.info(f"[COPY_HANDLER] Processing signal for {len(valid_pairs)} slave(s)")
            
            success_count = 0
            failed_count = 0
            skipped_count = 0
            results = []
            
            for pair in valid_pairs:
                slave_account = pair.get('slave_account')
                
                try:
                    # ⭐ สร้างสำเนาใหม่ทุกครั้ง โดยใช้ Symbol ต้นฉบับ
                    sdata = dict(signal_data)
                    sdata['symbol'] = original_master_symbol  # ⭐ บังคับใช้ต้นฉบับ
                    
                    logger.info(
                        f"[COPY_HANDLER] Processing slave {slave_account}: "
                        f"original_symbol={original_master_symbol}, master_volume={master_volume}"
                    )
                    
                    # ⭐ แปล Symbol สำหรับ Slave นี้โดยเฉพาะ
                    mapped_symbol = None
                    
                    if self.broker_manager:
                        from app.signal_translator import SignalTranslator
                        # ⭐ ส่ง session_manager เพื่อให้เช็ค per-account symbol mapping ที่ User ตั้งไว้
                        translator = SignalTranslator(
                            self.broker_manager,
                            self.symbol_mapper,
                            self.balance_helper.session_manager
                        )
                        
                        settings = pair.get('settings', {}) or {}
                        auto_map = settings.get('autoMapSymbol', settings.get('auto_map_symbol', True))
                        
                        logger.info(f"[COPY_HANDLER] Translating for slave {slave_account}: auto_map={auto_map}")
                        
                        translated = translator.translate_for_account(sdata, slave_account, auto_map_symbol=auto_map)
                        
                        if not translated:
                            error_msg = f"Cannot translate symbol '{original_master_symbol}' for slave broker"
                            logger.warning(f"[COPY_HANDLER] ❌ {error_msg} (slave: {slave_account})")
                            failed_count += 1

                            # แจ้งเตือน symbol translation error
                            if self.email_handler:
                                try:
                                    self.email_handler.send_copy_trading_error_alert(
                                        error_type='Symbol Translation Failed',
                                        master_account=master_account,
                                        slave_account=slave_account,
                                        error_message=error_msg,
                                        signal_data=sdata
                                    )
                                except Exception as email_err:
                                    logger.error(f"[COPY_HANDLER] Failed to send error email: {email_err}")

                            # ✅ บันทึก Error สำหรับ Symbol Translation Failed
                            try:
                                self.copy_executor.copy_history.record_copy_event({
                                    'master': master_account,
                                    'slave': slave_account,
                                    'action': self._get_action_type(signal_data),
                                    'order_type': signal_data.get('order_type', 'market'),
                                    'symbol': original_master_symbol,
                                    'volume': signal_data.get('volume', ''),
                                    'price': signal_data.get('price', ''),
                                    'tp': signal_data.get('tp', ''),
                                    'sl': signal_data.get('sl', ''),
                                    'status': 'error',
                                    'message': f'Symbol translation failed: {original_master_symbol} not available for slave broker'
                                })
                            except Exception as log_err:
                                logger.error(f"[COPY_HANDLER] Failed to log symbol translation error: {log_err}")

                            results.append({
                                'slave_account': slave_account,
                                'success': False,
                                'error': f'Symbol {original_master_symbol} not available'
                            })
                            continue
                        
                        mapped_symbol = translated['symbol']
                        sdata['symbol'] = mapped_symbol
                        sdata['mapped_symbol'] = mapped_symbol
                        sdata['original_symbol'] = original_master_symbol
                        
                        logger.info(
                            f"[COPY_HANDLER] ✅ Symbol translated for slave {slave_account}: "
                            f"{original_master_symbol} → {mapped_symbol}"
                        )
                    else:
                        mapped_symbol = original_master_symbol
                        logger.warning(f"[COPY_HANDLER] No broker_manager, using original: {original_master_symbol}")
                    
                    # 🔥 คำนวณ Volume - สำคัญสำหรับ Partial Close
                    settings = pair.get('settings', {}) or {}
                    calculated_volume = self._calculate_slave_volume(
                        master_volume=master_volume,  # 🔥 ใช้ master_volume ที่แท้จริง
                        settings=settings,
                        slave_account=slave_account,
                        symbol=mapped_symbol,
                        master_account=master_account,
                        master_symbol=original_master_symbol
                    )
                    sdata['volume'] = calculated_volume  # 🔥 อัปเดต volume ที่คำนวณแล้ว
                    
                    logger.info(
                        f"[COPY_HANDLER] 🔥 Volume calculated for slave {slave_account}: "
                        f"master={master_volume} → slave={calculated_volume}"
                    )

                    # ปิด auto map ในรอบส่งคำสั่ง
                    temp_pair = dict(pair)
                    temp_settings = dict(settings)
                    temp_settings['auto_map_symbol'] = False
                    temp_settings['autoMapSymbol'] = False
                    temp_settings['auto_map_volume'] = False
                    temp_settings['autoMapVolume'] = False
                    temp_settings['volume_mode'] = 'fixed'
                    temp_settings['multiplier'] = calculated_volume
                    temp_pair['settings'] = temp_settings

                    # แปลง Signal เป็น Command
                    slave_command = self._convert_signal_to_command(sdata, temp_pair)
                    if not slave_command:
                        logger.info(f"[COPY_HANDLER] ⚠️ Skipped slave {slave_account} (command not applicable)")
                        skipped_count += 1
                        results.append({
                            'slave_account': slave_account,
                            'success': False,
                            'error': 'command not applicable'
                        })
                        continue
                    
                    result = self.copy_executor.execute_on_slave(
                        slave_account=slave_account,
                        command=slave_command,
                        pair=pair
                    )
                    
                    if result.get('success'):
                        success_count += 1
                        logger.info(
                            f"[COPY_HANDLER] ✅ Successfully sent to slave {slave_account}: "
                            f"{original_master_symbol} → {mapped_symbol}, volume={calculated_volume}"
                        )

                        # ✅ บันทึก Success Event พร้อม TP/SL
                        try:
                            self.copy_executor.copy_history.record_copy_event({
                                'master': master_account,
                                'slave': slave_account,
                                'action': self._get_action_type(signal_data),
                                'order_type': signal_data.get('order_type', 'market'),
                                'symbol': original_master_symbol,
                                'volume': calculated_volume,
                                'price': signal_data.get('price', ''),
                                'tp': signal_data.get('tp', ''),
                                'sl': signal_data.get('sl', ''),
                                'status': 'success',
                                'message': f'Copied: {mapped_symbol} {calculated_volume} lots'
                            })
                        except Exception as log_err:
                            logger.error(f"[COPY_HANDLER] Failed to log success event: {log_err}")
                    else:
                        failed_count += 1
                        error_msg = result.get('error', 'Unknown error')
                        logger.error(
                            f"[COPY_HANDLER] ❌ Failed to send to slave {slave_account}: {error_msg}"
                        )

                        # ✅ บันทึก Error Event
                        try:
                            self.copy_executor.copy_history.record_copy_event({
                                'master': master_account,
                                'slave': slave_account,
                                'action': self._get_action_type(signal_data),
                                'order_type': signal_data.get('order_type', 'market'),
                                'symbol': mapped_symbol or original_master_symbol,
                                'volume': calculated_volume,
                                'price': signal_data.get('price', ''),
                                'tp': signal_data.get('tp', ''),
                                'sl': signal_data.get('sl', ''),
                                'status': 'error',
                                'message': f'Command failed: {error_msg}'
                            })
                        except Exception as log_err:
                            logger.error(f"[COPY_HANDLER] Failed to log error event: {log_err}")

                        # แจ้งเตือน command execution error (เฉพาะถ้า account online)
                        # ถ้า offline ไม่ต้องแจ้งเพราะมีการแจ้งเตือน online/offline อยู่แล้ว
                        is_alive = self.balance_helper.session_manager.is_instance_alive(slave_account)
                        if self.email_handler and is_alive:
                            try:
                                self.email_handler.send_copy_trading_error_alert(
                                    error_type='Command Execution Failed',
                                    master_account=master_account,
                                    slave_account=slave_account,
                                    error_message=f"Failed to execute command: {error_msg}",
                                    signal_data=sdata
                                )
                            except Exception as email_err:
                                logger.error(f"[COPY_HANDLER] Failed to send error email: {email_err}")
                    
                    results.append({
                        'slave_account': slave_account,
                        'success': result.get('success', False),
                        'error': result.get('error'),
                        'original_symbol': original_master_symbol,
                        'mapped_symbol': mapped_symbol,
                        'volume': calculated_volume
                    })
                
                except Exception as e:
                    failed_count += 1
                    error_msg = str(e)
                    logger.error(
                        f"[COPY_HANDLER] Exception processing slave {slave_account}: {error_msg}",
                        exc_info=True
                    )

                    # ✅ บันทึก Exception Error
                    try:
                        self.copy_executor.copy_history.record_copy_event({
                            'master': master_account,
                            'slave': slave_account,
                            'action': self._get_action_type(signal_data),
                            'order_type': signal_data.get('order_type', 'market'),
                            'symbol': original_master_symbol,
                            'volume': signal_data.get('volume', ''),
                            'price': signal_data.get('price', ''),
                            'tp': signal_data.get('tp', ''),
                            'sl': signal_data.get('sl', ''),
                            'status': 'error',
                            'message': f'Exception: {error_msg}'
                        })
                    except Exception as log_err:
                        logger.error(f"[COPY_HANDLER] Failed to log exception error: {log_err}")

                    results.append({
                        'slave_account': slave_account,
                        'success': False,
                        'error': error_msg
                    })
            
            # สรุปผล
            total = len(valid_pairs)
            logger.info(
                f"[COPY_HANDLER] 📊 Signal processed: {success_count}/{total} successful, "
                f"{failed_count}/{total} failed, {skipped_count}/{total} skipped"
            )
            
            if success_count > 0:
                return {
                    'success': True,
                    'message': f'Processed {success_count}/{total} slaves',
                    'slaves_processed': success_count,
                    'results': results
                }
            else:
                return {
                    'success': False,
                    'error': f'All slaves failed ({failed_count} failed, {skipped_count} skipped)',
                    'results': results
                }
        
        except Exception as e:
            logger.error(f"[COPY_HANDLER] Critical error: {str(e)}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    def _get_all_pairs_by_api_key(self, api_key: str) -> List[Dict]:
        """หาทุก Pairs ที่ใช้ API Key นี้"""
        all_pairs = self.copy_manager.get_all_pairs()
        matching = []
        
        for pair in all_pairs:
            if pair.get('api_key') == api_key:
                matching.append(pair)
        
        return matching
    
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
        คำนวณ Volume สำหรับ Slave
        🔥 v3.4: รองรับ partial close volume calculation
        """
        try:
            def get_setting(key_snake, key_camel, default):
                return settings.get(key_snake, settings.get(key_camel, default))
            
            volume_mode = get_setting('volume_mode', 'volumeMode', 'multiply').lower()
            multiplier = float(get_setting('multiplier', 'volumeMultiplier', 1.0))
            auto_map_volume = get_setting('auto_map_volume', 'autoMapVolume', True)
            
            logger.info(
                f"[COPY_HANDLER] Volume Calculation: "
                f"Mode={volume_mode} | Multiplier={multiplier} | AutoMap={auto_map_volume} | "
                f"Master={master_volume}"
            )
            
            # 1. Fixed mode - ใช้ค่าคงที่ (ไม่เหมาะสำหรับ partial close)
            if volume_mode == 'fixed':
                logger.warning(f"[COPY_HANDLER] ⚠️ Fixed mode may not work well with partial close")
                result = multiplier
                logger.info(f"[COPY_HANDLER] Fixed volume: {result}")
                return result
            
            # 2. Multiply mode - เหมาะสำหรับ partial close
            if volume_mode == 'multiply':
                result = master_volume * multiplier
                logger.info(f"[COPY_HANDLER] Multiply mode: {master_volume} × {multiplier} = {result}")
                
                # Auto map volume based on contract size
                if auto_map_volume and self.broker_manager and master_account and master_symbol:
                    master_contract = self.broker_manager.get_contract_size(master_account, master_symbol)
                    slave_contract = self.broker_manager.get_contract_size(slave_account, symbol)
                    
                    if master_contract and slave_contract and master_contract > 0:
                        ratio = master_contract / slave_contract
                        adjusted = result * ratio
                        logger.info(
                            f"[COPY_HANDLER] Contract size adjustment: "
                            f"Master={master_contract} | Slave={slave_contract} | "
                            f"Ratio={ratio:.4f} | {result} → {adjusted}"
                        )
                        result = adjusted
                
                return result
            
            # 3. Percent mode - คำนวณจาก balance
            if volume_mode == 'percent':
                # ดึง balance ของ slave account
                slave_balance = self.balance_helper.get_account_balance(slave_account)

                if slave_balance and slave_balance > 0:
                    # คำนวณ volume จาก percent of balance
                    # multiplier = percent (เช่น 0.1 = 10%)
                    # ตัวอย่าง: balance 10000, percent 10% (0.1) = 1000 / price ต่อ lot
                    # เพื่อความง่าย: ใช้ balance * percent / 1000 (สมมติ 1 lot = $1000)
                    percent = multiplier * 100  # แปลงเป็น %
                    volume_per_percent = slave_balance / 100 / 1000  # 1% ของ balance / 1000
                    result = volume_per_percent * percent

                    # ปัดเศษให้เหมาะสม (min 0.01, max 100)
                    result = max(0.01, min(result, 100.0))
                    result = round(result, 2)

                    logger.info(
                        f"[COPY_HANDLER] Percent mode: "
                        f"Balance={slave_balance:.2f} × {percent:.1f}% = {result} lots"
                    )
                    return result
                else:
                    # ถ้าไม่มี balance หรือ balance = 0 → fallback เป็น multiply
                    logger.warning(
                        f"[COPY_HANDLER] No balance data for {slave_account}, "
                        f"using multiply mode as fallback"
                    )
                    result = master_volume * multiplier
                    logger.info(f"[COPY_HANDLER] Fallback multiply: {master_volume} × {multiplier} = {result}")
                    return result
            
            # 4. Default
            logger.info(f"[COPY_HANDLER] Using master volume: {master_volume}")
            return master_volume
            
        except Exception as e:
            logger.error(f"[COPY_HANDLER] Volume calculation error: {str(e)}")
            return master_volume
