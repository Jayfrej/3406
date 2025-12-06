#!/usr/bin/env python3
"""
Database Auto-Initialization & Migration Module
Built-in migration - runs automatically on app startup
Creates tables IF NOT EXISTS (safe to run multiple times)

This module handles:
1. Database schema creation
2. Auto-migration of legacy data to Multi-User format
3. Generating missing webhook tokens for users
4. Migrating copy_pairs.json with user_id

NO MANUAL MIGRATION SCRIPTS REQUIRED - everything runs on app startup!
"""
import sqlite3
import os
import json
import secrets
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def get_database_path() -> Path:
    """Get the database file path"""
    base_dir = Path(__file__).parent.parent.parent
    return base_dir / 'data' / 'accounts.db'


def get_data_dir() -> Path:
    """Get the data directory path"""
    return Path(__file__).parent.parent.parent / 'data'


def _get_first_admin_user(cursor) -> Optional[str]:
    """Get first admin user_id from database"""
    try:
        cursor.execute("""
            SELECT user_id FROM users 
            WHERE is_admin = 1 AND is_active = 1 
            ORDER BY created_at ASC LIMIT 1
        """)
        row = cursor.fetchone()
        if row:
            return row[0]

        # No admin found - check for any user
        cursor.execute("SELECT user_id FROM users ORDER BY created_at ASC LIMIT 1")
        row = cursor.fetchone()
        if row:
            return row[0]
    except:
        pass

    return None


def _migrate_accounts_user_id(conn, cursor) -> int:
    """
    Auto-migrate accounts without user_id to admin user.
    Called automatically during startup.
    """
    migrated = 0

    try:
        # Check if there are accounts without user_id
        cursor.execute("SELECT COUNT(*) FROM accounts WHERE user_id IS NULL OR user_id = ''")
        null_count = cursor.fetchone()[0]

        if null_count > 0:
            admin_user = _get_first_admin_user(cursor)
            if admin_user:
                cursor.execute(
                    "UPDATE accounts SET user_id = ? WHERE user_id IS NULL OR user_id = ''",
                    (admin_user,)
                )
                conn.commit()
                migrated = cursor.rowcount
                if migrated > 0:
                    logger.info(f"[DB_INIT] Auto-migrated {migrated} accounts to user: {admin_user}")
    except Exception as e:
        logger.debug(f"[DB_INIT] Account migration check: {e}")

    return migrated


def _migrate_copy_pairs_user_id() -> int:
    """
    Auto-migrate copy_pairs.json entries without user_id.
    Called automatically during startup.
    """
    migrated = 0
    copy_pairs_file = get_data_dir() / 'copy_pairs.json'

    if not copy_pairs_file.exists():
        return 0

    try:
        with open(copy_pairs_file, 'r', encoding='utf-8') as f:
            pairs = json.load(f)

        if not isinstance(pairs, list):
            return 0

        # Get admin user from database
        admin_user = None
        db_path = get_database_path()
        if db_path.exists():
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            admin_user = _get_first_admin_user(cursor)
            conn.close()

        if not admin_user:
            return 0

        # Migrate pairs without user_id
        modified = False
        for pair in pairs:
            if not pair.get('user_id'):
                pair['user_id'] = admin_user
                migrated += 1
                modified = True

        if modified:
            with open(copy_pairs_file, 'w', encoding='utf-8') as f:
                json.dump(pairs, f, ensure_ascii=False, indent=2)
            logger.info(f"[DB_INIT] Auto-migrated {migrated} copy pairs to user: {admin_user}")

    except Exception as e:
        logger.debug(f"[DB_INIT] Copy pairs migration check: {e}")

    return migrated


def _migrate_master_slave_accounts_user_id() -> int:
    """
    Auto-migrate master_accounts.json and slave_accounts.json entries without user_id.
    Called automatically during startup.
    """
    migrated = 0
    data_dir = get_data_dir()

    # Get admin user from database
    admin_user = None
    db_path = get_database_path()
    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            admin_user = _get_first_admin_user(cursor)
            conn.close()
        except:
            pass

    if not admin_user:
        return 0

    # Migrate both master and slave accounts files
    for filename in ['master_accounts.json', 'slave_accounts.json']:
        file_path = data_dir / filename
        if not file_path.exists():
            continue

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                accounts = json.load(f)

            if not isinstance(accounts, list):
                continue

            modified = False
            for account in accounts:
                if not account.get('user_id'):
                    account['user_id'] = admin_user
                    migrated += 1
                    modified = True

            if modified:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(accounts, f, ensure_ascii=False, indent=2)
                logger.info(f"[DB_INIT] Auto-migrated {filename} entries to user: {admin_user}")

        except Exception as e:
            logger.debug(f"[DB_INIT] {filename} migration check: {e}")

    return migrated


def _ensure_user_webhook_tokens(conn, cursor) -> int:
    """
    Auto-generate webhook tokens for users who don't have them.
    Called automatically during startup.
    """
    created = 0

    try:
        # Find users without tokens
        cursor.execute("""
            SELECT u.user_id FROM users u
            LEFT JOIN user_tokens t ON u.user_id = t.user_id
            WHERE t.token_id IS NULL AND u.is_active = 1
        """)
        users_without_tokens = cursor.fetchall()

        for (user_id,) in users_without_tokens:
            # Generate unique token
            token = f"whk_{secrets.token_urlsafe(32)}"
            now = datetime.now().isoformat()

            cursor.execute("""
                INSERT INTO user_tokens (user_id, webhook_token, created_at)
                VALUES (?, ?, ?)
            """, (user_id, token, now))
            created += 1

        if created > 0:
            conn.commit()
            logger.info(f"[DB_INIT] Auto-generated {created} webhook tokens for users")

    except Exception as e:
        logger.debug(f"[DB_INIT] Token generation check: {e}")

    return created


def _ensure_user_license_keys(conn, cursor) -> int:
    """
    Auto-generate license keys for users who don't have them.
    Called automatically during startup.
    """
    generated = 0

    try:
        cursor.execute("""
            SELECT user_id FROM users 
            WHERE (license_key IS NULL OR license_key = '') AND is_active = 1
        """)
        users_without_keys = cursor.fetchall()

        for (user_id,) in users_without_keys:
            license_key = f"whk_{secrets.token_urlsafe(18)[:24]}"
            webhook_secret = f"whs_{secrets.token_urlsafe(24)[:32]}"

            cursor.execute("""
                UPDATE users SET license_key = ?, webhook_secret = ?
                WHERE user_id = ? AND (license_key IS NULL OR license_key = '')
            """, (license_key, webhook_secret, user_id))
            generated += 1

        if generated > 0:
            conn.commit()
            logger.info(f"[DB_INIT] Auto-generated {generated} license keys for users")

    except Exception as e:
        logger.debug(f"[DB_INIT] License key generation check: {e}")

    return generated


def run_auto_migrations() -> Dict:
    """
    Run all automatic migrations on startup.
    This is called after ensure_database_schema().

    Returns:
        dict: Migration results summary
    """
    results = {
        'accounts_migrated': 0,
        'copy_pairs_migrated': 0,
        'master_slave_migrated': 0,
        'tokens_generated': 0,
        'license_keys_generated': 0,
        'success': True
    }

    db_path = get_database_path()
    if not db_path.exists():
        return results

    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Run all migrations
        results['accounts_migrated'] = _migrate_accounts_user_id(conn, cursor)
        results['tokens_generated'] = _ensure_user_webhook_tokens(conn, cursor)
        results['license_keys_generated'] = _ensure_user_license_keys(conn, cursor)

        conn.close()

        # Migrate JSON files (separate from DB connection)
        results['copy_pairs_migrated'] = _migrate_copy_pairs_user_id()
        results['master_slave_migrated'] = _migrate_master_slave_accounts_user_id()

        # Log summary if anything was migrated
        total = sum([
            results['accounts_migrated'],
            results['copy_pairs_migrated'],
            results['master_slave_migrated'],
            results['tokens_generated'],
            results['license_keys_generated']
        ])

        if total > 0:
            logger.info(f"[DB_INIT] Auto-migration complete: {total} items processed")

    except Exception as e:
        logger.error(f"[DB_INIT] Auto-migration error: {e}")
        results['success'] = False

    return results


def ensure_database_schema() -> bool:
    """
    Ensure all required tables exist in the database.
    Safe to call on every app startup - uses IF NOT EXISTS.

    This is idempotent - running multiple times has no negative effect.

    Returns:
        bool: True if successful, False if error
    """
    db_path = get_database_path()

    # Ensure data directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"[DB_INIT] Checking database schema: {db_path}")

    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # ========================================
        # TABLE 1: users (Multi-User SaaS)
        # ========================================
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                name TEXT,
                picture TEXT,
                is_active INTEGER DEFAULT 1,
                is_admin INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_login TEXT,
                license_key TEXT UNIQUE,
                webhook_secret TEXT
            )
        ''')

        # Ensure license_key and webhook_secret columns exist (for legacy databases)
        cursor.execute("PRAGMA table_info(users)")
        user_columns = [col[1] for col in cursor.fetchall()]

        # Note: SQLite cannot add UNIQUE column to table with existing data
        # Add without UNIQUE constraint, uniqueness enforced at creation time
        if 'license_key' not in user_columns:
            try:
                cursor.execute('ALTER TABLE users ADD COLUMN license_key TEXT')
                logger.info("[DB_INIT] Added 'license_key' column to users")
            except sqlite3.OperationalError as e:
                if 'duplicate column' not in str(e).lower():
                    logger.warning(f"[DB_INIT] Could not add license_key column: {e}")

        if 'webhook_secret' not in user_columns:
            try:
                cursor.execute('ALTER TABLE users ADD COLUMN webhook_secret TEXT')
                logger.info("[DB_INIT] Added 'webhook_secret' column to users")
            except sqlite3.OperationalError as e:
                if 'duplicate column' not in str(e).lower():
                    logger.warning(f"[DB_INIT] Could not add webhook_secret column: {e}")


        logger.debug("[DB_INIT] ✓ Table 'users' ready")

        # ========================================
        # TABLE 2: user_tokens (Webhook tokens per user)
        # ========================================
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_tokens (
                token_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                webhook_token TEXT UNIQUE NOT NULL,
                webhook_url TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        logger.debug("[DB_INIT] ✓ Table 'user_tokens' ready")

        # ========================================
        # TABLE 3: accounts (Trading accounts)
        # ========================================
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account TEXT UNIQUE,
                nickname TEXT,
                status TEXT DEFAULT 'inactive',
                broker TEXT,
                last_seen TEXT,
                created TEXT,
                symbol_received INTEGER DEFAULT 0,
                user_id TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')

        # Check if user_id column exists (for legacy databases)
        cursor.execute("PRAGMA table_info(accounts)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'user_id' not in columns:
            cursor.execute('ALTER TABLE accounts ADD COLUMN user_id TEXT')
            logger.info("[DB_INIT] Added 'user_id' column to accounts")

        logger.debug("[DB_INIT] ✓ Table 'accounts' ready")

        # ========================================
        # TABLE 4: global_settings (key-value format)
        # ========================================
        # Check if global_settings exists with old schema (id-based)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='global_settings'")
        gs_table_exists = cursor.fetchone() is not None

        if gs_table_exists:
            cursor.execute("PRAGMA table_info(global_settings)")
            gs_columns = [col[1] for col in cursor.fetchall()]

            if 'id' in gs_columns and 'key' not in gs_columns:
                # Old schema detected - migrate to new format
                logger.info("[DB_INIT] Migrating global_settings from old schema to key-value format...")

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
                cursor.execute("DROP TABLE global_settings")
                cursor.execute('''
                    CREATE TABLE global_settings (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    )
                ''')

                # Migrate old data to new format
                if old_secret:
                    cursor.execute("INSERT INTO global_settings (key, value) VALUES ('secret_key', ?)", (old_secret,))
                if old_updated:
                    cursor.execute("INSERT INTO global_settings (key, value) VALUES ('secret_key_updated', ?)", (old_updated,))

                logger.info("[DB_INIT] ✓ global_settings migration complete")
        else:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS global_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
        logger.debug("[DB_INIT] ✓ Table 'global_settings' ready")

        # ========================================
        # TABLE 5: sessions (for session tracking)
        # ========================================
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                expires_at TEXT,
                ip_address TEXT,
                user_agent TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        logger.debug("[DB_INIT] ✓ Table 'sessions' ready")

        # ========================================
        # Create indexes for performance
        # ========================================
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_accounts_user_id ON accounts(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_tokens_user_id ON user_tokens(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)')
        logger.debug("[DB_INIT] ✓ Indexes ready")

        # ========================================
        # Create Admin User if ADMIN_EMAIL is set and no admin exists
        # ========================================
        admin_email = os.getenv('ADMIN_EMAIL')
        if admin_email:
            cursor.execute(
                'SELECT user_id FROM users WHERE email = ?',
                (admin_email,)
            )
            if not cursor.fetchone():
                import secrets
                admin_id = f"admin_{secrets.token_hex(4)}"
                cursor.execute('''
                    INSERT INTO users (user_id, email, name, is_active, is_admin, created_at)
                    VALUES (?, ?, 'Admin', 1, 1, ?)
                ''', (admin_id, admin_email, datetime.now().isoformat()))
                logger.info(f"[DB_INIT] Created admin user: {admin_email}")

        conn.commit()
        conn.close()

        logger.info("[DB_INIT] ✓ Database schema initialization complete")

        # ========================================
        # AUTO-MIGRATIONS: Run on every startup
        # Ensures Multi-User data is properly configured
        # ========================================
        run_auto_migrations()

        return True

    except Exception as e:
        logger.error(f"[DB_INIT] ✗ Database initialization error: {e}")
        return False


def verify_database_health() -> Dict:
    """
    Verify database health and return status.
    Useful for debugging and health checks.

    Returns:
        dict: Database health status
    """
    db_path = get_database_path()
    status = {
        'healthy': False,
        'path': str(db_path),
        'exists': db_path.exists(),
        'tables': [],
        'user_count': 0,
        'account_count': 0,
        'error': None
    }

    if not db_path.exists():
        status['error'] = 'Database file not found'
        return status

    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        status['tables'] = [row[0] for row in cursor.fetchall()]

        # Check required tables
        required_tables = ['users', 'user_tokens', 'accounts']
        missing_tables = [t for t in required_tables if t not in status['tables']]

        if missing_tables:
            status['error'] = f"Missing tables: {missing_tables}"
        else:
            # Get counts
            cursor.execute("SELECT COUNT(*) FROM users")
            status['user_count'] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM accounts")
            status['account_count'] = cursor.fetchone()[0]

            status['healthy'] = True

        conn.close()

    except Exception as e:
        status['error'] = str(e)

    return status


def get_table_schema(table_name: str) -> List[Dict]:
    """
    Get schema information for a table.

    Args:
        table_name: Name of the table

    Returns:
        List of column info dicts
    """
    db_path = get_database_path()

    if not db_path.exists():
        return []

    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = []
        for row in cursor.fetchall():
            columns.append({
                'cid': row[0],
                'name': row[1],
                'type': row[2],
                'notnull': bool(row[3]),
                'default': row[4],
                'pk': bool(row[5])
            })

        conn.close()
        return columns

    except Exception:
        return []

