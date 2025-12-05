#!/usr/bin/env python3
"""
Database Auto-Initialization Module
Built-in migration - runs automatically on app startup
Creates tables IF NOT EXISTS (safe to run multiple times)

This is a SAFETY NET:
- Primary initialization happens in setup.py
- This ensures database is ready even if someone skips setup.py
"""
import sqlite3
import os
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List

logger = logging.getLogger(__name__)


def get_database_path() -> Path:
    """Get the database file path"""
    base_dir = Path(__file__).parent.parent.parent
    return base_dir / 'data' / 'accounts.db'


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
                webhook_secret TEXT UNIQUE
            )
        ''')

        # Ensure license_key and webhook_secret columns exist (for legacy databases)
        cursor.execute("PRAGMA table_info(users)")
        user_columns = [col[1] for col in cursor.fetchall()]

        if 'license_key' not in user_columns:
            cursor.execute('ALTER TABLE users ADD COLUMN license_key TEXT UNIQUE')
            logger.info("[DB_INIT] Added 'license_key' column to users")

        if 'webhook_secret' not in user_columns:
            cursor.execute('ALTER TABLE users ADD COLUMN webhook_secret TEXT UNIQUE')
            logger.info("[DB_INIT] Added 'webhook_secret' column to users")

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

