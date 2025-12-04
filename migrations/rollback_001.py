#!/usr/bin/env python
"""
Rollback Migration 001: Undo Multi-User Schema Changes

This script reverses the changes made by migration 001:
- Drops users table
- Drops user_tokens table
- Removes user_id column from accounts table

WARNING: This will remove all multi-user data!

Reference: CRITICAL_MISSING_DETAILS.md - Rollback Script
"""

import os
import sys
import sqlite3
from datetime import datetime

# Add project root to path for imports
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Configuration
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
DB_PATH = os.path.join(DATA_DIR, "accounts.db")


def get_accounts_columns(cursor: sqlite3.Cursor) -> list:
    """Get current columns in accounts table."""
    cursor.execute("PRAGMA table_info(accounts)")
    return [col[1] for col in cursor.fetchall()]


def rollback_migration() -> bool:
    """
    Rollback Phase 1 database changes.

    Returns:
        bool: True if rollback succeeded
    """
    print("\n" + "=" * 60)
    print("🔄 Rollback Migration 001: Undo Multi-User Changes")
    print("=" * 60 + "\n")

    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found: {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Step 1: Check current state
        print("🔍 Step 1: Checking current schema...")

        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='users'
        """)
        has_users_table = cursor.fetchone() is not None

        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='user_tokens'
        """)
        has_user_tokens_table = cursor.fetchone() is not None

        columns = get_accounts_columns(cursor)
        has_user_id_column = "user_id" in columns

        print(f"   users table exists: {has_users_table}")
        print(f"   user_tokens table exists: {has_user_tokens_table}")
        print(f"   accounts.user_id column exists: {has_user_id_column}")

        if not any([has_users_table, has_user_tokens_table, has_user_id_column]):
            print("\n✅ Nothing to rollback - migration not applied")
            return True

        # Step 2: Drop new tables
        print("\n🗑️  Step 2: Dropping new tables...")

        if has_user_tokens_table:
            cursor.execute("DROP TABLE IF EXISTS user_tokens")
            print("   ✅ Dropped user_tokens table")

        if has_users_table:
            cursor.execute("DROP TABLE IF EXISTS users")
            print("   ✅ Dropped users table")

        # Step 3: Remove user_id from accounts
        # SQLite limitation: can't drop column directly in older versions
        # Need to recreate table
        if has_user_id_column:
            print("\n📝 Step 3: Removing user_id column from accounts...")

            # Get current data (excluding user_id)
            base_columns = [c for c in columns if c != "user_id"]
            columns_str = ", ".join(base_columns)

            cursor.execute(f"SELECT {columns_str} FROM accounts")
            accounts_data = cursor.fetchall()
            print(f"   📊 Found {len(accounts_data)} accounts to preserve")

            # Drop index first
            cursor.execute("DROP INDEX IF EXISTS idx_accounts_user_id")
            print("   ✅ Dropped index idx_accounts_user_id")

            # Rename old table
            cursor.execute("ALTER TABLE accounts RENAME TO accounts_old")
            print("   ✅ Renamed accounts to accounts_old")

            # Create new table without user_id
            # Using the original schema from session_manager.py
            cursor.execute("""
                CREATE TABLE accounts (
                    account TEXT PRIMARY KEY,
                    nickname TEXT,
                    status TEXT DEFAULT 'Wait for Activate',
                    broker TEXT,
                    last_seen TEXT,
                    created TEXT,
                    symbol_mappings TEXT DEFAULT NULL,
                    pid INTEGER DEFAULT NULL,
                    symbol_received INTEGER DEFAULT 0
                )
            """)
            print("   ✅ Created new accounts table without user_id")

            # Re-insert data
            if accounts_data:
                placeholders = ", ".join(["?" for _ in base_columns])
                cursor.executemany(f"""
                    INSERT INTO accounts ({columns_str})
                    VALUES ({placeholders})
                """, accounts_data)
                print(f"   ✅ Restored {len(accounts_data)} accounts")

            # Drop old table
            cursor.execute("DROP TABLE accounts_old")
            print("   ✅ Dropped accounts_old table")

        # Commit all changes
        conn.commit()

        print("\n" + "=" * 60)
        print("✅ Rollback completed successfully!")
        print("   Multi-user schema changes have been reversed.")
        print("=" * 60 + "\n")

        return True

    except Exception as e:
        print(f"\n❌ Rollback failed: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def dry_run() -> None:
    """
    Check what would be rolled back without making changes.
    """
    print("\n" + "=" * 60)
    print("🔍 Rollback 001: Dry Run (Status Check)")
    print("=" * 60 + "\n")

    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='users'
        """)
        has_users_table = cursor.fetchone() is not None

        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='user_tokens'
        """)
        has_user_tokens_table = cursor.fetchone() is not None

        columns = get_accounts_columns(cursor)
        has_user_id_column = "user_id" in columns

        print("Current schema status:")
        print(f"   {'✅' if has_users_table else '❌'} users table exists: {has_users_table}")
        print(f"   {'✅' if has_user_tokens_table else '❌'} user_tokens table exists: {has_user_tokens_table}")
        print(f"   {'✅' if has_user_id_column else '❌'} accounts.user_id column exists: {has_user_id_column}")

        if has_users_table:
            cursor.execute("SELECT COUNT(*) FROM users")
            user_count = cursor.fetchone()[0]
            print(f"\n   📊 Users in database: {user_count}")

        if has_user_tokens_table:
            cursor.execute("SELECT COUNT(*) FROM user_tokens")
            token_count = cursor.fetchone()[0]
            print(f"   📊 Tokens in database: {token_count}")

        if any([has_users_table, has_user_tokens_table, has_user_id_column]):
            print("\n⚠️  Rollback would remove the above items.")
            print("   Run without --dry-run to execute rollback.")
        else:
            print("\n✅ Nothing to rollback - migration not applied")

    except sqlite3.Error as e:
        print(f"❌ Error checking status: {e}")
    finally:
        conn.close()


def print_usage() -> None:
    """Print usage information."""
    print("""
Usage: python migrations/rollback_001.py [OPTIONS]

Options:
    --dry-run    Check what would be rolled back without making changes
    --force      Skip confirmation prompt
    --help       Show this help message

Examples:
    python migrations/rollback_001.py              # Run rollback (with confirmation)
    python migrations/rollback_001.py --dry-run    # Check status only
    python migrations/rollback_001.py --force      # Run without confirmation

WARNING: This will remove all multi-user data including:
- All users
- All user tokens
- User assignments on accounts
""")


if __name__ == "__main__":
    args = sys.argv[1:]

    if "--help" in args or "-h" in args:
        print_usage()
        sys.exit(0)

    if "--dry-run" in args:
        dry_run()
        sys.exit(0)

    # Confirmation prompt (unless --force)
    if "--force" not in args:
        print("\n⚠️  WARNING: This will undo all multi-user changes!")
        print("   - Drop users table")
        print("   - Drop user_tokens table")
        print("   - Remove user_id from accounts")
        print()
        confirm = input("Are you sure you want to continue? (yes/no): ")
        if confirm.lower() != "yes":
            print("Cancelled")
            sys.exit(0)

    # Execute rollback
    success = rollback_migration()
    sys.exit(0 if success else 1)

