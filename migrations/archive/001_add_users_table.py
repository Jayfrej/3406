#!/usr/bin/env python
"""
Migration 001: Add Users Table and User-Related Schema Changes

This migration creates the multi-user infrastructure for the SaaS platform:
- Creates `users` table for storing Google OAuth users
- Creates `user_tokens` table for per-user webhook tokens
- Adds `user_id` column to existing `accounts` table
- Assigns existing accounts to a default admin user

Reference: MIGRATION_ROADMAP.md Phase 1.1

Safety Features:
- Automatic backup before migration
- Rollback capability
- Non-destructive migration (preserves existing data)
"""

import os
import sys
import sqlite3
import shutil
from datetime import datetime
from typing import Optional

# Add project root to path for imports
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Configuration
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
DB_PATH = os.path.join(DATA_DIR, "accounts.db")
BACKUP_DIR = os.path.join(PROJECT_ROOT, "backups")
DEFAULT_ADMIN_USER_ID = "admin_001"
DEFAULT_ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com")


def create_backup() -> Optional[str]:
    """
    Create backup of database and JSON files before migration.

    Returns:
        str: Path to backup directory, or None if backup failed
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"pre_migration_001_{timestamp}")

    try:
        os.makedirs(backup_path, exist_ok=True)

        # Backup database
        if os.path.exists(DB_PATH):
            shutil.copy2(DB_PATH, os.path.join(backup_path, "accounts.db"))
            print(f"✅ Database backed up: accounts.db")

        # Backup JSON files
        json_files = ["copy_pairs.json", "api_keys.json", "master_accounts.json",
                      "slave_accounts.json", "webhook_accounts.json"]
        for json_file in json_files:
            src_path = os.path.join(DATA_DIR, json_file)
            if os.path.exists(src_path):
                shutil.copy2(src_path, os.path.join(backup_path, json_file))
                print(f"✅ JSON backed up: {json_file}")

        # Create restore manifest
        manifest_path = os.path.join(backup_path, "RESTORE.md")
        with open(manifest_path, "w", encoding="utf-8") as f:
            f.write(f"""# Migration 001 Backup
Created: {datetime.now().isoformat()}

## Files Backed Up
- accounts.db
- JSON data files

## To Restore (Rollback)
```bash
python migrations/001_add_users_table.py --rollback {backup_path}
```

Or manually:
```bash
cp {backup_path}/accounts.db {DATA_DIR}/
cp {backup_path}/*.json {DATA_DIR}/
```
""")

        print(f"✅ Backup created: {backup_path}")
        return backup_path

    except Exception as e:
        print(f"❌ Backup failed: {e}")
        return None


def check_migration_status(conn: sqlite3.Connection) -> dict:
    """
    Check current state of database schema.

    Returns:
        dict: Status of each migration component
    """
    cursor = conn.cursor()
    status = {
        "users_table_exists": False,
        "user_tokens_table_exists": False,
        "accounts_has_user_id": False,
        "accounts_user_id_index_exists": False
    }

    # Check if users table exists
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='users'
    """)
    status["users_table_exists"] = cursor.fetchone() is not None

    # Check if user_tokens table exists
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='user_tokens'
    """)
    status["user_tokens_table_exists"] = cursor.fetchone() is not None

    # Check if accounts has user_id column
    cursor.execute("PRAGMA table_info(accounts)")
    columns = [col[1] for col in cursor.fetchall()]
    status["accounts_has_user_id"] = "user_id" in columns

    # Check if index exists
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='index' AND name='idx_accounts_user_id'
    """)
    status["accounts_user_id_index_exists"] = cursor.fetchone() is not None

    return status


def create_users_table(conn: sqlite3.Connection) -> bool:
    """
    Create users table for Google OAuth users.

    Schema from MIGRATION_ROADMAP.md Phase 1.1
    """
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                name TEXT,
                picture TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_login TEXT,
                is_active INTEGER DEFAULT 1,
                is_admin INTEGER DEFAULT 0
            )
        """)
        print("✅ Created users table")
        return True
    except sqlite3.Error as e:
        print(f"❌ Failed to create users table: {e}")
        return False


def create_user_tokens_table(conn: sqlite3.Connection) -> bool:
    """
    Create user_tokens table for per-user webhook tokens.

    Schema from MIGRATION_ROADMAP.md Phase 1.1
    """
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_tokens (
                token_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                webhook_token TEXT UNIQUE NOT NULL,
                webhook_url TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                expires_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        """)
        print("✅ Created user_tokens table")
        return True
    except sqlite3.Error as e:
        print(f"❌ Failed to create user_tokens table: {e}")
        return False


def add_user_id_to_accounts(conn: sqlite3.Connection) -> bool:
    """
    Add user_id column to accounts table and create index.

    Schema from MIGRATION_ROADMAP.md Phase 1.1
    """
    cursor = conn.cursor()

    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(accounts)")
        columns = [col[1] for col in cursor.fetchall()]

        if "user_id" not in columns:
            conn.execute("""
                ALTER TABLE accounts 
                ADD COLUMN user_id TEXT REFERENCES users(user_id)
            """)
            print("✅ Added user_id column to accounts table")
        else:
            print("⏭️  user_id column already exists in accounts table")

        # Create index if not exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND name='idx_accounts_user_id'
        """)
        if cursor.fetchone() is None:
            conn.execute("""
                CREATE INDEX idx_accounts_user_id ON accounts(user_id)
            """)
            print("✅ Created index idx_accounts_user_id")
        else:
            print("⏭️  Index idx_accounts_user_id already exists")

        return True

    except sqlite3.Error as e:
        print(f"❌ Failed to modify accounts table: {e}")
        return False


def create_default_admin_user(conn: sqlite3.Connection) -> bool:
    """
    Create default admin user for legacy data assignment.

    Per copilot-instructions.md: Legacy data must be assigned to a default Admin user
    """
    try:
        cursor = conn.cursor()

        # Check if admin user already exists
        cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (DEFAULT_ADMIN_USER_ID,))
        if cursor.fetchone() is not None:
            print(f"⏭️  Default admin user '{DEFAULT_ADMIN_USER_ID}' already exists")
            return True

        # Create admin user
        conn.execute("""
            INSERT INTO users (user_id, email, name, is_active, is_admin, created_at)
            VALUES (?, ?, ?, 1, 1, ?)
        """, (
            DEFAULT_ADMIN_USER_ID,
            DEFAULT_ADMIN_EMAIL,
            "System Administrator",
            datetime.now().isoformat()
        ))
        print(f"✅ Created default admin user: {DEFAULT_ADMIN_USER_ID} ({DEFAULT_ADMIN_EMAIL})")
        return True

    except sqlite3.Error as e:
        print(f"❌ Failed to create default admin user: {e}")
        return False


def assign_existing_accounts_to_admin(conn: sqlite3.Connection) -> int:
    """
    Assign all existing accounts (without user_id) to the default admin user.

    Per copilot-instructions.md: Non-destructive migration, preserve existing data

    Returns:
        int: Number of accounts assigned
    """
    try:
        cursor = conn.cursor()

        # Count accounts without user_id
        cursor.execute("SELECT COUNT(*) FROM accounts WHERE user_id IS NULL")
        count = cursor.fetchone()[0]

        if count == 0:
            print("⏭️  No accounts need assignment (all have user_id)")
            return 0

        # Assign to admin user
        conn.execute("""
            UPDATE accounts 
            SET user_id = ? 
            WHERE user_id IS NULL
        """, (DEFAULT_ADMIN_USER_ID,))

        print(f"✅ Assigned {count} existing accounts to admin user '{DEFAULT_ADMIN_USER_ID}'")
        return count

    except sqlite3.Error as e:
        print(f"❌ Failed to assign accounts: {e}")
        return -1


def run_migration() -> bool:
    """
    Execute the full migration.

    Returns:
        bool: True if migration succeeded, False otherwise
    """
    print("\n" + "=" * 60)
    print("🚀 Migration 001: Add Users Table")
    print("=" * 60 + "\n")

    # Step 1: Create backup
    print("📦 Step 1: Creating backup...")
    backup_path = create_backup()
    if backup_path is None:
        print("❌ Migration aborted: Backup failed")
        return False

    # Step 2: Connect to database
    print("\n📊 Step 2: Connecting to database...")
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found: {DB_PATH}")
        return False

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA foreign_keys = ON")
        print(f"✅ Connected to: {DB_PATH}")
    except sqlite3.Error as e:
        print(f"❌ Failed to connect: {e}")
        return False

    try:
        # Step 3: Check current status
        print("\n🔍 Step 3: Checking current schema...")
        status = check_migration_status(conn)
        for key, value in status.items():
            emoji = "✅" if value else "❌"
            print(f"   {emoji} {key}: {value}")

        # Step 4: Create users table
        print("\n👥 Step 4: Creating users table...")
        if not create_users_table(conn):
            raise Exception("Failed to create users table")

        # Step 5: Create user_tokens table
        print("\n🔑 Step 5: Creating user_tokens table...")
        if not create_user_tokens_table(conn):
            raise Exception("Failed to create user_tokens table")

        # Step 6: Add user_id to accounts
        print("\n📝 Step 6: Adding user_id to accounts table...")
        if not add_user_id_to_accounts(conn):
            raise Exception("Failed to modify accounts table")

        # Step 7: Create default admin user
        print("\n👤 Step 7: Creating default admin user...")
        if not create_default_admin_user(conn):
            raise Exception("Failed to create admin user")

        # Step 8: Assign existing accounts to admin
        print("\n🔗 Step 8: Assigning existing accounts to admin...")
        assigned = assign_existing_accounts_to_admin(conn)
        if assigned < 0:
            raise Exception("Failed to assign accounts")

        # Commit all changes
        conn.commit()
        print("\n✅ All changes committed successfully!")

        # Final status check
        print("\n📊 Final schema status:")
        final_status = check_migration_status(conn)
        for key, value in final_status.items():
            emoji = "✅" if value else "❌"
            print(f"   {emoji} {key}: {value}")

        print("\n" + "=" * 60)
        print("✅ Migration 001 completed successfully!")
        print(f"   Backup location: {backup_path}")
        print("=" * 60 + "\n")

        return True

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        print("🔄 Rolling back...")
        conn.rollback()
        print(f"⚠️  To restore from backup, run:")
        print(f"   python migrations/001_add_users_table.py --rollback {backup_path}")
        return False

    finally:
        conn.close()


def rollback_migration(backup_path: str) -> bool:
    """
    Rollback migration by restoring from backup.

    Args:
        backup_path: Path to backup directory

    Returns:
        bool: True if rollback succeeded
    """
    print("\n" + "=" * 60)
    print("🔄 Rolling back Migration 001")
    print("=" * 60 + "\n")

    if not os.path.exists(backup_path):
        print(f"❌ Backup not found: {backup_path}")
        return False

    try:
        # Restore database
        db_backup = os.path.join(backup_path, "accounts.db")
        if os.path.exists(db_backup):
            shutil.copy2(db_backup, DB_PATH)
            print(f"✅ Restored database from backup")

        # Restore JSON files
        for filename in os.listdir(backup_path):
            if filename.endswith(".json"):
                src = os.path.join(backup_path, filename)
                dst = os.path.join(DATA_DIR, filename)
                shutil.copy2(src, dst)
                print(f"✅ Restored: {filename}")

        print("\n✅ Rollback completed successfully!")
        return True

    except Exception as e:
        print(f"❌ Rollback failed: {e}")
        return False


def print_usage():
    """Print usage information."""
    print("""
Usage: python migrations/001_add_users_table.py [OPTIONS]

Options:
    --dry-run           Check current status without making changes
    --rollback <path>   Rollback using specified backup directory
    --help              Show this help message

Examples:
    python migrations/001_add_users_table.py              # Run migration
    python migrations/001_add_users_table.py --dry-run    # Check status only
    python migrations/001_add_users_table.py --rollback backups/pre_migration_001_20251204_120000
""")


def dry_run() -> None:
    """
    Check current migration status without making changes.
    """
    print("\n" + "=" * 60)
    print("🔍 Migration 001: Dry Run (Status Check)")
    print("=" * 60 + "\n")

    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found: {DB_PATH}")
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        status = check_migration_status(conn)

        print("Current schema status:")
        for key, value in status.items():
            emoji = "✅" if value else "❌"
            print(f"   {emoji} {key}: {value}")

        # Check accounts count
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM accounts")
        total_accounts = cursor.fetchone()[0]

        print(f"\n   📊 Total accounts: {total_accounts}")

        # Only check unassigned if user_id column exists
        if status["accounts_has_user_id"]:
            cursor.execute("SELECT COUNT(*) FROM accounts WHERE user_id IS NULL")
            unassigned = cursor.fetchone()[0]
            print(f"   📊 Accounts without user_id: {unassigned}")
        else:
            print(f"   📊 Accounts without user_id: {total_accounts} (column not exists)")

        if all(status.values()):
            print("\n✅ Migration already applied!")
        else:
            print("\n⚠️  Migration needed. Run without --dry-run to apply.")

        conn.close()

    except sqlite3.Error as e:
        print(f"❌ Error checking status: {e}")


if __name__ == "__main__":
    import sys

    args = sys.argv[1:]

    if "--help" in args or "-h" in args:
        print_usage()
        sys.exit(0)

    if "--dry-run" in args:
        dry_run()
        sys.exit(0)

    if "--rollback" in args:
        try:
            idx = args.index("--rollback")
            backup_path = args[idx + 1]
            success = rollback_migration(backup_path)
            sys.exit(0 if success else 1)
        except (IndexError, ValueError):
            print("❌ Error: --rollback requires backup path argument")
            print_usage()
            sys.exit(1)

    # Default: run migration
    success = run_migration()
    sys.exit(0 if success else 1)

