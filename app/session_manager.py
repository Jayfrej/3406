import os
import shutil
import subprocess
import time
import json
import logging
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional

try:
    import psutil  # process management
except Exception:
    psutil = None  # we'll guard usage

logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )

class SessionManager:
    """
    Manages per-account portable MT5 instances.
    """

    def __init__(self):
        self.base_dir = os.path.abspath(os.getcwd())
        self.instances_dir = os.path.abspath(
            os.getenv("MT5_INSTANCES_DIR", os.path.join(self.base_dir, "mt5_instances"))
        )
        os.makedirs(self.instances_dir, exist_ok=True)
        self.mt5_path = os.getenv("MT5_PATH", r"C:\Program Files\MetaTrader 5\terminal64.exe")
        self.profile_source = os.getenv("MT5_PROFILE_SOURCE") or self._auto_detect_profile_source()
        data_dir = os.path.join(self.base_dir, "data")
        os.makedirs(data_dir, exist_ok=True)
        self.db_path = os.path.join(data_dir, "accounts.db")
        self._init_db()

    # -------------------------- DB --------------------------
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            # Accounts table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS accounts (
                    account TEXT PRIMARY KEY,
                    nickname TEXT,
                    status TEXT DEFAULT 'Wait for Activate',
                    broker TEXT,
                    last_seen TEXT,
                    created TEXT,
                    symbol_mappings TEXT DEFAULT NULL,
                    pid INTEGER DEFAULT NULL
                )
                """
            )

            # Global settings table (key-value format)
            # Note: Uses key-value format to be compatible with database_init.py

            # First check if global_settings exists with old schema (id-based)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='global_settings'")
            table_exists = cursor.fetchone() is not None

            if table_exists:
                # Check if it's old schema (has 'id' column) or new schema (has 'key' column)
                cursor.execute("PRAGMA table_info(global_settings)")
                gs_columns = [col[1] for col in cursor.fetchall()]

                if 'id' in gs_columns and 'key' not in gs_columns:
                    # Old schema detected - migrate to new format
                    logger.info("[DB] Migrating global_settings from old schema to key-value format...")

                    # Get existing secret_key if any
                    try:
                        cursor.execute("SELECT secret_key, updated FROM global_settings WHERE id = 1")
                        row = cursor.fetchone()
                        old_secret = row[0] if row else None
                        old_updated = row[1] if row and len(row) > 1 else None
                    except:
                        old_secret = None
                        old_updated = None

                    # Drop old table and create new one
                    conn.execute("DROP TABLE global_settings")
                    conn.execute(
                        """
                        CREATE TABLE global_settings (
                            key TEXT PRIMARY KEY,
                            value TEXT
                        )
                        """
                    )

                    # Migrate old data to new format
                    if old_secret:
                        conn.execute("INSERT INTO global_settings (key, value) VALUES ('secret_key', ?)", (old_secret,))
                    if old_updated:
                        conn.execute("INSERT INTO global_settings (key, value) VALUES ('secret_key_updated', ?)", (old_updated,))

                    logger.info("[DB] ✓ global_settings migration complete")
            else:
                # Table doesn't exist, create with new schema
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS global_settings (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    )
                    """
                )

            # ตรวจสอบและเพิ่มคอลัมน์ใหม่ถ้ายังไม่มี (สำหรับ database เดิม)

            # ตรวจสอบคอลัมน์ที่มีอยู่
            cursor.execute("PRAGMA table_info(accounts)")
            columns = [column[1] for column in cursor.fetchall()]

            # เพิ่มคอลัมน์ symbol_mappings ถ้ายังไม่มี
            if 'symbol_mappings' not in columns:
                logger.info("[DB] Adding column: symbol_mappings")
                conn.execute("ALTER TABLE accounts ADD COLUMN symbol_mappings TEXT DEFAULT NULL")

            # เพิ่มคอลัมน์ pid ถ้ายังไม่มี (สำหรับ instance mode)
            if 'pid' not in columns:
                logger.info("[DB] Adding column: pid")
                conn.execute("ALTER TABLE accounts ADD COLUMN pid INTEGER DEFAULT NULL")

            # เพิ่มคอลัมน์ symbol_received สำหรับติดตามการ activate ด้วย Symbol
            if 'symbol_received' not in columns:
                logger.info("[DB] Adding column: symbol_received")
                conn.execute("ALTER TABLE accounts ADD COLUMN symbol_received INTEGER DEFAULT 0")

            # ลบคอลัมน์ secret_key ถ้ามี (migration to global secret)
            if 'secret_key' in columns:
                logger.info("[DB] Migrating from per-account to global secret key")
                # SQLite ไม่รองรับ DROP COLUMN โดยตรง แต่เราจะไม่ใช้มันแล้ว

            conn.commit()
            logger.info("[DB] Database initialized successfully")

    def get_all_accounts(self) -> List[Dict]:
        """
        ดึงรายการบัญชีทั้งหมด (เวอร์ชัน Remote)
        """
        # เช็คสถานะก่อน
        self.check_account_online_status()

        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT account, nickname, status, broker, last_seen, created, symbol_received
                FROM accounts
                ORDER BY created DESC
                """
            ).fetchall()

        accounts = []
        for row in rows:
            acc = {
                'account': row[0],
                'nickname': row[1] or '',
                'status': row[2] or 'Wait for Activate',
                'broker': row[3] or '-',
                'last_seen': row[4],
                'created': row[5],
                'pid': None,  # ไม่มี PID ในระบบ Remote
                'symbol_received': bool(row[6]) if len(row) > 6 and row[6] is not None else False
            }
            accounts.append(acc)

        return accounts

    def account_exists(self, account: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT 1 FROM accounts WHERE account = ?", (account,)
            ).fetchone()
            return row is not None

    def get_account_info(self, account: str) -> Optional[Dict]:
        """
        ดึงข้อมูลบัญชีเดียว

        Args:
            account: หมายเลขบัญชี

        Returns:
            Dict หรือ None ถ้าไม่พบบัญชี
        """
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT account, nickname, status, broker, last_seen, created, symbol_received
                FROM accounts
                WHERE account = ?
                """,
                (account,)
            ).fetchone()

        if not row:
            return None

        return {
            'account': row[0],
            'nickname': row[1] or '',
            'status': row[2] or 'Wait for Activate',
            'broker': row[3] or '-',
            'last_seen': row[4],
            'created': row[5],
            'pid': None,
            'symbol_received': bool(row[6]) if row[6] is not None else False
        }

    # ============= Remote Mode Functions =============

    def add_remote_account(self, account: str, nickname: str = "") -> bool:
        """
        เพิ่มบัญชีแบบ Remote (ไม่สร้าง instance folder)
        สถานะเริ่มต้น: 'Wait for Activate'
        """
        try:
            if self.account_exists(account):
                logger.info(f"[REMOTE] Account {account} already exists")
                return False

            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO accounts
                    (account, nickname, status, created)
                    VALUES (?, ?, 'Wait for Activate', ?)
                    """,
                    (account, nickname, datetime.now().isoformat())
                )
                conn.commit()

            logger.info(f"[REMOTE] Account {account} added (waiting for EA connection)")
            return True

        except Exception as e:
            logger.error(f"[REMOTE_ADD_ERROR] {e}")
            return False

    def activate_remote_account(self, account: str, broker: str = "", symbol: str = "") -> bool:
        """
        Activate บัญชี Remote เมื่อ EA ส่งข้อมูลมา
        เปลี่ยนจาก 'Wait for Activate' → 'Online'
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    "SELECT status FROM accounts WHERE account = ?",
                    (account,)
                ).fetchone()

                if not row:
                    logger.warning(f"[REMOTE] Account {account} not found for activation")
                    return False

                current_status = row[0]

                # ✅ บันทึก log เมื่อเปลี่ยนจาก 'Wait for Activate' → 'Online'
                if current_status == 'Wait for Activate':
                    logger.info(f"[REMOTE] 🟢 Account {account} is being ACTIVATED (First Connection)")

                conn.execute(
                    """
                    UPDATE accounts
                    SET status = 'Online',
                        broker = ?,
                        last_seen = ?
                    WHERE account = ?
                    """,
                    (broker, datetime.now().isoformat(), account)
                )
                conn.commit()

            logger.info(f"[REMOTE] ✅ Account {account} activated (Broker: {broker})")
            return True

        except Exception as e:
            logger.error(f"[REMOTE_ACTIVATE_ERROR] {e}")
            return False

    def is_symbol_received(self, account: str) -> bool:
        """
        ตรวจสอบว่า account ได้รับ Symbol data แล้วหรือยัง

        Args:
            account: หมายเลขบัญชี

        Returns:
            bool: True ถ้าได้รับ Symbol แล้ว
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    "SELECT symbol_received FROM accounts WHERE account = ?",
                    (account,)
                ).fetchone()

                if row:
                    return bool(row[0])
                return False

        except Exception as e:
            logger.error(f"[IS_SYMBOL_RECEIVED_ERROR] {e}")
            return False

    def activate_by_symbol(self, account: str, broker: str = "", symbol: str = "") -> bool:
        """
        Activate บัญชีเมื่อได้รับ Symbol data จาก EA
        ⚠️ นี่คือวิธีเดียวที่จะ activate account ได้

        เปลี่ยนจาก 'Wait for Activate' → 'Online'
        และตั้ง symbol_received = 1

        Args:
            account: หมายเลขบัญชี
            broker: ชื่อโบรกเกอร์
            symbol: Symbol ที่ส่งมา

        Returns:
            bool: True ถ้า activate สำเร็จ
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    "SELECT status, symbol_received FROM accounts WHERE account = ?",
                    (account,)
                ).fetchone()

                if not row:
                    logger.warning(f"[SYMBOL_ACTIVATE] Account {account} not found")
                    return False

                current_status = row[0]
                already_received = bool(row[1])

                # ถ้าได้รับ Symbol แล้ว ให้แค่อัพเดท heartbeat
                if already_received:
                    conn.execute(
                        "UPDATE accounts SET last_seen = ? WHERE account = ?",
                        (datetime.now().isoformat(), account)
                    )
                    conn.commit()
                    logger.info(f"[SYMBOL_ACTIVATE] Account {account} already activated, updating heartbeat")
                    return True

                # ✅ Activate account เมื่อได้รับ Symbol ครั้งแรก
                logger.info(f"[SYMBOL_ACTIVATE] 🟢 Account {account} is being ACTIVATED by Symbol data")

                conn.execute(
                    """
                    UPDATE accounts
                    SET status = 'Online',
                        broker = ?,
                        last_seen = ?,
                        symbol_received = 1
                    WHERE account = ?
                    """,
                    (broker, datetime.now().isoformat(), account)
                )
                conn.commit()

            logger.info(f"[SYMBOL_ACTIVATE] ✅ Account {account} activated by Symbol (Broker: {broker}, Symbol: {symbol})")
            return True

        except Exception as e:
            logger.error(f"[SYMBOL_ACTIVATE_ERROR] {e}")
            return False

    def can_receive_orders(self, account: str) -> tuple:
        """
        ตรวจสอบว่า account สามารถรับคำสั่งซื้อขายได้หรือไม่

        Returns:
            tuple: (can_receive: bool, reason: str)
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    "SELECT status, symbol_received FROM accounts WHERE account = ?",
                    (account,)
                ).fetchone()

                if not row:
                    return (False, "Account not found")

                status = row[0]
                symbol_received = bool(row[1])

                # ถ้ายังไม่ได้รับ Symbol
                if not symbol_received:
                    return (False, "Account not activated - waiting for Symbol data from EA")

                # ถ้า status เป็น Wait for Activate (ไม่ควรเกิดขึ้นถ้า symbol_received=1)
                if status == 'Wait for Activate':
                    return (False, "Account not activated - waiting for Symbol data from EA")

                # ถ้า PAUSE
                if status == 'PAUSE':
                    return (False, "Account is paused")

                # ✅ สามารถรับ order ได้
                return (True, "OK")

        except Exception as e:
            logger.error(f"[CAN_RECEIVE_ORDERS_ERROR] {e}")
            return (False, f"Error: {e}")

    def update_account_heartbeat(self, account: str) -> bool:
        """
        อัพเดท last_seen timestamp เมื่อ EA ส่งข้อมูลมา
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "UPDATE accounts SET last_seen = ? WHERE account = ?",
                    (datetime.now().isoformat(), account)
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"[HEARTBEAT_ERROR] {e}")
            return False

    def set_account_online(self, account: str, broker: str = "") -> bool:
        """
        เปลี่ยนสถานะจาก Offline กลับเป็น Online
        ⚠️ จะไม่เปลี่ยนถ้าสถานะปัจจุบันเป็น PAUSE

        Args:
            account: หมายเลขบัญชี
            broker: ชื่อโบรกเกอร์ (optional)

        Returns:
            bool: True ถ้าอัพเดทสำเร็จ
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                # ⚠️ ตรวจสอบสถานะปัจจุบันก่อน - ไม่ให้ overwrite PAUSE
                cursor = conn.cursor()
                cursor.execute("SELECT status FROM accounts WHERE account = ?", (account,))
                row = cursor.fetchone()
                if row and row[0] == 'PAUSE':
                    logger.info(f"[SESSION] Account {account} is PAUSED - not changing to Online")
                    return False

                if broker:
                    conn.execute(
                        """
                        UPDATE accounts
                        SET status = 'Online',
                            broker = ?,
                            last_seen = ?
                        WHERE account = ? AND status != 'PAUSE'
                        """,
                        (broker, datetime.now().isoformat(), account)
                    )
                else:
                    conn.execute(
                        """
                        UPDATE accounts
                        SET status = 'Online',
                            last_seen = ?
                        WHERE account = ? AND status != 'PAUSE'
                        """,
                        (datetime.now().isoformat(), account)
                    )
                conn.commit()

            logger.info(f"[SESSION] Account {account} set to Online")
            return True

        except Exception as e:
            logger.error(f"[SET_ONLINE_ERROR] {e}")
            return False

    def check_account_online_status(self) -> None:
        """
        เช็คว่าบัญชีไหนไม่มี heartbeat มานานเกิน 2 นาที
        ให้เปลี่ยนสถานะเป็น Offline

        ⚠️ แต่ถ้าบัญชียังไม่เคย Activate (status = 'Wait for Activate')
           จะไม่ถูกเปลี่ยนสถานะ
        ⚠️ Account ที่เป็น 'Online' แต่ last_seen IS NULL (ยังไม่เคย activate)
           จะไม่ถูกเปลี่ยนเป็น 'Offline'
        """
        try:
            from datetime import timedelta
            timeout_minutes = 2
            cutoff_time = (datetime.now() - timedelta(minutes=timeout_minutes)).isoformat()

            with sqlite3.connect(self.db_path) as conn:
                # ✅ เพิ่มเงื่อนไข: เฉพาะ Account ที่เป็น 'Online' เท่านั้นถึงจะเปลี่ยนเป็น 'Offline'
                # ✅ และต้องมี last_seen (เคย activate แล้ว) และ heartbeat หมดอายุ
                # Account ที่ยังเป็น 'Wait for Activate' จะไม่ถูกแตะต้อง
                conn.execute(
                    """
                    UPDATE accounts
                    SET status = 'Offline'
                    WHERE status = 'Online'
                    AND last_seen IS NOT NULL
                    AND last_seen < ?
                    """,
                    (cutoff_time,)
                )
                conn.commit()

        except Exception as e:
            logger.error(f"[CHECK_STATUS_ERROR] {e}")

    def delete_account(self, account: str) -> bool:
        """
        ลบบัญชีออกจาก database (ไม่มี folder ให้ลบ)
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM accounts WHERE account = ?", (account,))
                conn.commit()

            logger.info(f"[REMOTE] Account {account} deleted")
            return True

        except Exception as e:
            logger.error(f"[DELETE_ERROR] {e}")
            return False

    # ============= Global Secret Key Management =============

    def get_global_secret(self) -> Optional[str]:
        """
        ดึง Global Secret Key

        Returns:
            str: Secret Key หรือ None ถ้าไม่มี
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    "SELECT value FROM global_settings WHERE key = 'secret_key'"
                ).fetchone()

                return row[0] if row and row[0] else None

        except Exception as e:
            logger.error(f"[GET_GLOBAL_SECRET_ERROR] {e}")
            return None

    def update_global_secret(self, secret_key: str = None) -> bool:
        """
        อัพเดท Global Secret Key

        Args:
            secret_key: Secret Key (ถ้าเป็น None หรือ empty string จะลบ secret key)

        Returns:
            bool: True ถ้าอัพเดทสำเร็จ
        """
        try:
            secret_key = secret_key.strip() if secret_key else None

            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO global_settings (key, value)
                    VALUES ('secret_key', ?)
                    """,
                    (secret_key,)
                )
                # Also store the update timestamp
                conn.execute(
                    """
                    INSERT OR REPLACE INTO global_settings (key, value)
                    VALUES ('secret_key_updated', ?)
                    """,
                    (datetime.now().isoformat(),)
                )
                conn.commit()

            logger.info(f"[GLOBAL_SECRET] Updated (enabled: {bool(secret_key)})")
            return True

        except Exception as e:
            logger.error(f"[UPDATE_GLOBAL_SECRET_ERROR] {e}")
            return False

    def validate_global_secret(self, provided_secret: str) -> bool:
        """
        ตรวจสอบว่า Secret Key ที่ส่งมาตรงกับ Global Secret หรือไม่

        Args:
            provided_secret: Secret Key ที่ส่งมา

        Returns:
            bool: True ถ้า Secret ถูกต้อง หรือไม่มีการตั้ง Global Secret
        """
        stored_secret = self.get_global_secret()

        # ถ้าไม่มีการตั้ง Secret Key ให้ผ่านเสมอ
        if not stored_secret:
            return True

        # ตรวจสอบว่าตรงกันหรือไม่
        return str(provided_secret).strip() == stored_secret

    # ============= Symbol Mapping Management =============

    def update_symbol_mappings(self, account: str, mappings: list) -> bool:
        """
        อัพเดท Symbol Mappings สำหรับ account

        Args:
            account: หมายเลขบัญชี
            mappings: List ของ mappings [{"from": "XAUUSD", "to": "GOLD"}, ...]

        Returns:
            bool: True ถ้าอัพเดทสำเร็จ
        """
        try:
            import json

            # แปลงเป็น JSON string
            mappings_json = json.dumps(mappings) if mappings else None

            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "UPDATE accounts SET symbol_mappings = ? WHERE account = ?",
                    (mappings_json, account)
                )
                conn.commit()

            logger.info(f"[SYMBOL_MAPPING] Updated for account {account} ({len(mappings or [])} mappings)")
            return True

        except Exception as e:
            logger.error(f"[SYMBOL_MAPPING_ERROR] {e}")
            return False

    def get_symbol_mappings(self, account: str) -> list:
        """
        ดึง Symbol Mappings ของ account

        Args:
            account: หมายเลขบัญชี

        Returns:
            list: List ของ mappings หรือ [] ถ้าไม่มี
        """
        try:
            import json

            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    "SELECT symbol_mappings FROM accounts WHERE account = ?",
                    (account,)
                ).fetchone()

                if row and row[0]:
                    return json.loads(row[0])
                return []

        except Exception as e:
            logger.error(f"[GET_SYMBOL_MAPPING_ERROR] {e}")
            return []

    def map_symbol(self, account: str, symbol: str) -> str:
        """
        แปลง Symbol ตาม mapping ที่ตั้งไว้

        Args:
            account: หมายเลขบัญชี
            symbol: Symbol ต้นทาง (จาก TradingView)

        Returns:
            str: Symbol ปลายทาง (ไปยังโบรกเกอร์) หรือ Symbol เดิมถ้าไม่มี mapping
        """
        try:
            mappings = self.get_symbol_mappings(account)

            # หา mapping ที่ตรงกัน (case-insensitive)
            symbol_upper = symbol.upper()
            for mapping in mappings:
                if mapping.get('from', '').upper() == symbol_upper:
                    return mapping.get('to', symbol)

            # ถ้าไม่มี mapping ให้คืน symbol เดิม
            return symbol

        except Exception as e:
            logger.error(f"[MAP_SYMBOL_ERROR] {e}")
            return symbol

    def get_all_symbol_mappings(self) -> dict:
        """
        ดึง Symbol Mappings ของทุก Account

        Returns:
            dict: {account: {'nickname': ..., 'mappings': [...]}, ...}
        """
        try:
            import json

            result = {}

            with sqlite3.connect(self.db_path) as conn:
                rows = conn.execute(
                    """
                    SELECT account, nickname, symbol_mappings
                    FROM accounts
                    WHERE symbol_mappings IS NOT NULL
                    ORDER BY account
                    """
                ).fetchall()

                for row in rows:
                    account = row[0]
                    nickname = row[1]
                    mappings_json = row[2]

                    if mappings_json:
                        try:
                            mappings = json.loads(mappings_json)
                            if mappings:  # เฉพาะ account ที่มี mappings
                                result[account] = {
                                    'nickname': nickname,
                                    'mappings': mappings
                                }
                        except:
                            pass

            return result

        except Exception as e:
            logger.error(f"[GET_ALL_MAPPINGS_ERROR] {e}")
            return {}

    # ⭐ Added: Get symbol info (placed after account_exists and before update_account_status)
    def get_symbol_info(self, account: str, symbol: str) -> Optional[Dict]:
        """
        ดึงข้อมูล Symbol จาก MT5 instance รวมถึง Contract Size

        Args:
            account: หมายเลขบัญชี
            symbol: Symbol ที่ต้องการดึงข้อมูล

        Returns:
            Dict หรือ None: {
                'volume_min': float,
                'volume_max': float,
                'volume_step': float,
                'trade_contract_size': float  # ⭐ Contract Size สำหรับคำนวณ Tick Value
            }
        """
        try:
            instance_path = self.get_instance_path(account)
            if not instance_path:
                logger.warning(f"[SESSION_MANAGER] Cannot find instance for account {account}")
                return None

            # รองรับทั้งโหมด portable (Data/MQL5/Files) และโครงสร้างเดิม (MQL5/Files)
            fname = f"symbol_info_{symbol}.json"
            primary_path = os.path.join(instance_path, "Data", "MQL5", "Files", fname)
            fallback_path = os.path.join(instance_path, "MQL5", "Files", fname)
            symbol_info_file = primary_path if os.path.exists(primary_path) else fallback_path

            if os.path.exists(symbol_info_file):
                with open(symbol_info_file, 'r', encoding='utf-8') as f:
                    symbol_data = json.load(f)
                logger.debug(f"[SESSION_MANAGER] Symbol info for {symbol}: {symbol_data}")
                return symbol_data
            else:
                # ถ้าไม่มีไฟล์ ให้คืนค่า default
                logger.warning(f"[SESSION_MANAGER] Symbol info file not found for {symbol}, using defaults")
                return {
                    'volume_min': 0.01,
                    'volume_max': 100.0,
                    'volume_step': 0.01,
                    'trade_contract_size': 0.0  # ⚠️ ไม่รู้ค่าจริง
                }

        except Exception as e:
            logger.error(f"[SESSION_MANAGER] Failed to get symbol info for {account}/{symbol}: {e}")
            return None

    def update_account_status(self, account: str, status: str, pid: Optional[int] = None):
        with sqlite3.connect(self.db_path) as conn:
            if pid is not None:
                conn.execute(
                    "UPDATE accounts SET status = ?, pid = ? WHERE account = ?",
                    (status, pid, account),
                )
            else:
                conn.execute(
                    "UPDATE accounts SET status = ? WHERE account = ?",
                    (status, account),
                )
            conn.commit()

    # ---------------------- Paths & Detect ----------------------
    def get_instance_path(self, account: str) -> str:
        return os.path.join(self.instances_dir, str(account))

    def get_bat_path(self, account: str) -> str:
        """Get path to the BAT launcher file for this account"""
        instance_path = self.get_instance_path(account)
        return os.path.join(instance_path, f"launch_mt5_{account}.bat")

    def _auto_detect_profile_source(self) -> Optional[str]:
        appdata = os.getenv("APPDATA")
        if not appdata:
            return None
        candidates_root = os.path.join(appdata, "MetaQuotes", "Terminal")
        if not os.path.isdir(candidates_root):
            return None
        newest = None
        newest_mtime = 0
        for child in os.listdir(candidates_root):
            p = os.path.join(candidates_root, child)
            if os.path.isdir(p) and os.path.exists(os.path.join(p, "MQL5")):
                mtime = os.path.getmtime(p)
                if mtime > newest_mtime:
                    newest_mtime = mtime
                    newest = p
        return newest

    def diagnose_profile_source(self) -> Dict:
        p = self.profile_source
        info = {"exists": bool(p and os.path.exists(p)), "path": p}
        if info["exists"]:
            info["subdirs"] = [d for d in ("config", "profiles", "MQL5", "bases") if os.path.exists(os.path.join(p, d))]
        return info

    # -------------------- BAT File Creation --------------------
    def create_bat_launcher(self, account: str) -> bool:
        """Create a BAT file to launch MT5 in portable mode for this account"""
        try:
            instance_path = self.get_instance_path(account)
            bat_path = self.get_bat_path(account)
            
            # Find MT5 executable in instance
            terminal_exe = os.path.join(instance_path, "terminal64.exe")
            if not os.path.exists(terminal_exe):
                terminal_exe = os.path.join(instance_path, "terminal.exe")
                if not os.path.exists(terminal_exe):
                    logger.error(f"[CREATE_BAT] No MT5 executable found in: {instance_path}")
                    return False
            
            # Create portable data path
            data_path = os.path.join(instance_path, "Data")
            os.makedirs(data_path, exist_ok=True)
            
            # Create BAT content with portable mode
            bat_content = f'''@echo off
REM Auto-generated BAT launcher for MT5 Account {account}
REM This launches MT5 in portable mode with dedicated data path

echo Starting MT5 for Account {account} in Portable Mode...
echo Data Path: {data_path}
echo Instance Path: {instance_path}

cd /d "{instance_path}"

REM Launch MT5 with portable mode and custom data path
"{terminal_exe}" /portable /datapath="{data_path}"

pause
'''
            
            # Write BAT file
            with open(bat_path, 'w', encoding='utf-8') as f:
                f.write(bat_content)
            
            logger.info(f"[CREATE_BAT] ✓ Created BAT launcher: {bat_path}")
            return True
            
        except Exception as e:
            logger.error(f"[CREATE_BAT] Failed to create BAT for {account}: {e}")
            return False

    def launch_bat_file(self, account: str) -> bool:
        """Launch the BAT file for this account"""
        try:
            bat_path = self.get_bat_path(account)
            if not os.path.exists(bat_path):
                logger.error(f"[LAUNCH_BAT] BAT file not found: {bat_path}")
                return False
            
            logger.info(f"[LAUNCH_BAT] Launching BAT: {bat_path}")
            
            # Launch BAT file
            proc = subprocess.Popen(
                [bat_path],
                cwd=os.path.dirname(bat_path),
                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
                shell=True
            )
            
            # Give it a moment to start
            time.sleep(2)
            
            # Try to get the actual MT5 process PID
            pid = self._find_mt5_pid_for_account(account)
            if pid:
                self.update_account_status(account, "Online", pid)
                logger.info(f"[LAUNCH_BAT] ✓ MT5 started for {account}, PID: {pid}")
                return True
            else:
                logger.warning(f"[LAUNCH_BAT] BAT launched but MT5 PID not found for {account}")
                self.update_account_status(account, "Starting", None)
                return True  # Still consider success since BAT launched
                
        except Exception as e:
            logger.error(f"[LAUNCH_BAT] Failed to launch BAT for {account}: {e}")
            return False

    def _find_mt5_pid_for_account(self, account: str) -> Optional[int]:
        """Try to find the MT5 process PID for this account"""
        if psutil is None:
            return None
        
        try:
            instance_path = os.path.abspath(self.get_instance_path(account))
            
            for proc in psutil.process_iter(["pid", "name", "exe", "cwd"]):
                try:
                    name = (proc.info.get("name") or "").lower()
                    if name not in ("terminal64.exe", "terminal.exe"):
                        continue
                    
                    exe = proc.info.get("exe") or ""
                    cwd = proc.info.get("cwd") or ""
                    
                    # Check if this process is running from our instance
                    if (instance_path in os.path.abspath(exe) or 
                        instance_path in os.path.abspath(cwd)):
                        return proc.info["pid"]
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                    
        except Exception as e:
            logger.debug(f"[FIND_PID] Error finding PID for {account}: {e}")
            
        return None

    # -------------------- MT5 Process Utils --------------------
    def _close_all_mt5_processes(self):
        """Terminate only MT5-related processes we own. Never wait() on all system processes."""
        if psutil is None:
            logger.warning("[PROCESS] psutil not installed; cannot close MT5 processes automatically.")
            return
        names = {"terminal64.exe", "terminal.exe", "metatester64.exe", "metaeditor64.exe"}
        targets = []
        try:
            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    name = (proc.info.get("name") or "").lower()
                    if name in names:
                        targets.append(proc)
                except Exception:
                    continue
            # terminate gently
            for proc in targets:
                try:
                    proc.terminate()
                except Exception:
                    pass
            psutil.wait_procs(targets, timeout=3)
            # kill survivors
            survivors = []
            for proc in targets:
                try:
                    if proc.is_running():
                        survivors.append(proc)
                except Exception:
                    continue
            for proc in survivors:
                try:
                    proc.kill()
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"[PROCESS] Best-effort close MT5 processes raised: {e}")

    def _iter_instance_procs(self, account: str):
        if psutil is None:
            return
        inst = os.path.abspath(self.get_instance_path(account))
        for proc in psutil.process_iter(["pid", "name", "exe", "cwd"]):
            try:
                name = (proc.info.get("name") or "").lower()
                if name not in ("terminal64.exe", "terminal.exe"):
                    continue
                exe = proc.info.get("exe") or ""
                cwd = proc.info.get("cwd") or ""
                if inst in os.path.abspath(exe) or inst in os.path.abspath(cwd):
                    yield proc
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

    def is_instance_alive(self, account: str) -> bool:
        """
        ตรวจสอบว่า account ยังทำงานอยู่หรือไม่
        - สำหรับ Remote Mode: เช็คจาก last_seen (heartbeat)
        - สำหรับ Instance Mode: เช็คจาก PID
        """
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT pid, last_seen, status FROM accounts WHERE account = ?",
                (account,)
            ).fetchone()

            if not row:
                return False

            pid, last_seen, status = row

        # ตรวจสอบ Remote Mode ก่อน (มี last_seen = เป็น remote account)
        if last_seen:
            try:
                from datetime import timedelta
                last_beat = datetime.fromisoformat(last_seen)
                # ถือว่า alive ถ้า heartbeat ไม่เกิน 30 วินาที
                is_alive = (datetime.now() - last_beat) < timedelta(seconds=30)
                logger.debug(f"[REMOTE_CHECK] Account {account} - last_seen: {last_seen}, alive: {is_alive}")
                return is_alive
            except Exception as e:
                logger.warning(f"[REMOTE_CHECK] Error checking heartbeat for {account}: {e}")
                return False

        # ถ้าไม่มี last_seen = เป็น instance mode, เช็คจาก PID
        if psutil and pid:
            try:
                proc = psutil.Process(pid)
                if proc.is_running():
                    return True
            except psutil.Error:
                pass

        return False

    # =================== Multi-User Methods (Phase 1.2) ===================
    # Reference: MIGRATION_ROADMAP.md Phase 1.2 - SessionManager Extensions

    def get_accounts_by_user(self, user_id: str) -> List[Dict]:
        """
        Get all accounts for a specific user.

        Per MIGRATION_ROADMAP.md: Must filter by WHERE user_id = ?

        Args:
            user_id: User ID to filter by

        Returns:
            List of account dictionaries belonging to the user
        """
        # Check online status first
        self.check_account_online_status()

        with sqlite3.connect(self.db_path) as conn:
            # Check if user_id column exists
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(accounts)")
            columns = [col[1] for col in cursor.fetchall()]

            if 'user_id' not in columns:
                logger.warning("[MULTI_USER] user_id column not found - run migration 001 first")
                # Fallback: return all accounts (legacy behavior)
                return self.get_all_accounts()

            rows = conn.execute(
                """
                SELECT account, nickname, status, broker, last_seen, created, symbol_received, user_id
                FROM accounts
                WHERE user_id = ?
                ORDER BY created DESC
                """,
                (user_id,)
            ).fetchall()

        accounts = []
        for row in rows:
            acc = {
                'account': row[0],
                'nickname': row[1] or '',
                'status': row[2] or 'Wait for Activate',
                'broker': row[3] or '-',
                'last_seen': row[4],
                'created': row[5],
                'pid': None,
                'symbol_received': bool(row[6]) if row[6] is not None else False,
                'user_id': row[7]
            }
            accounts.append(acc)

        return accounts

    def assign_account_to_user(self, account: str, user_id: str) -> bool:
        """
        Assign an account to a specific user.

        Per MIGRATION_ROADMAP.md Phase 1.2

        Args:
            account: Account number to assign
            user_id: User ID to assign to

        Returns:
            bool: True if assignment succeeded
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Check if user_id column exists
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(accounts)")
                columns = [col[1] for col in cursor.fetchall()]

                if 'user_id' not in columns:
                    logger.error("[MULTI_USER] user_id column not found - run migration 001 first")
                    return False

                conn.execute(
                    "UPDATE accounts SET user_id = ? WHERE account = ?",
                    (user_id, account)
                )
                conn.commit()

            logger.info(f"[MULTI_USER] Assigned account {account} to user {user_id}")
            return True

        except Exception as e:
            logger.error(f"[MULTI_USER] Failed to assign account: {e}")
            return False

    def remove_user_accounts(self, user_id: str) -> bool:
        """
        Remove all accounts for a user (for deletion/cleanup).

        Per MIGRATION_ROADMAP.md Phase 1.2

        Args:
            user_id: User ID whose accounts should be removed

        Returns:
            bool: True if removal succeeded
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Check if user_id column exists
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(accounts)")
                columns = [col[1] for col in cursor.fetchall()]

                if 'user_id' not in columns:
                    logger.error("[MULTI_USER] user_id column not found - run migration 001 first")
                    return False

                # Get count before deletion
                cursor.execute(
                    "SELECT COUNT(*) FROM accounts WHERE user_id = ?",
                    (user_id,)
                )
                count = cursor.fetchone()[0]

                # Delete accounts
                conn.execute(
                    "DELETE FROM accounts WHERE user_id = ?",
                    (user_id,)
                )
                conn.commit()

            logger.info(f"[MULTI_USER] Removed {count} accounts for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"[MULTI_USER] Failed to remove user accounts: {e}")
            return False

    def get_account_owner(self, account: str) -> Optional[str]:
        """
        Get the user_id who owns this account.

        Args:
            account: Account number

        Returns:
            str: User ID or None if not found
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Check if user_id column exists
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(accounts)")
                columns = [col[1] for col in cursor.fetchall()]

                if 'user_id' not in columns:
                    return None

                row = conn.execute(
                    "SELECT user_id FROM accounts WHERE account = ?",
                    (account,)
                ).fetchone()

                return row[0] if row else None

        except Exception as e:
            logger.error(f"[MULTI_USER] Failed to get account owner: {e}")
            return None

    def add_remote_account_with_user(self, account: str, nickname: str = "", user_id: str = None) -> bool:
        """
        Add a remote account with user assignment.

        Extended version of add_remote_account for multi-user support.

        Args:
            account: Account number
            nickname: Account nickname
            user_id: User ID to assign (optional)

        Returns:
            bool: True if account was added successfully
        """
        try:
            if self.account_exists(account):
                logger.info(f"[REMOTE] Account {account} already exists")
                return False

            with sqlite3.connect(self.db_path) as conn:
                # Check if user_id column exists
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(accounts)")
                columns = [col[1] for col in cursor.fetchall()]

                if 'user_id' in columns and user_id:
                    conn.execute(
                        """
                        INSERT INTO accounts
                        (account, nickname, status, created, user_id)
                        VALUES (?, ?, 'Wait for Activate', ?, ?)
                        """,
                        (account, nickname, datetime.now().isoformat(), user_id)
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO accounts
                        (account, nickname, status, created)
                        VALUES (?, ?, 'Wait for Activate', ?)
                        """,
                        (account, nickname, datetime.now().isoformat())
                    )
                conn.commit()

            logger.info(f"[REMOTE] Account {account} added (user: {user_id or 'none'})")
            return True

        except Exception as e:
            logger.error(f"[REMOTE_ADD_ERROR] {e}")
            return False
