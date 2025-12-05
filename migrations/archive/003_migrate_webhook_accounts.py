#!/usr/bin/env python
"""
Migration 003: Migrate Webhook Accounts JSON

This migration adds user_id to all existing webhook accounts in the JSON file,
assigning them to the default admin user for data ownership.

Reference: CRITICAL_MISSING_DETAILS.md - JSON Data Migration

Safety Features:
- Creates backup before modification
- Preserves UTF-8 encoding
- Non-destructive (only adds missing user_id)
"""

import os
import sys
import json
import shutil
from datetime import datetime
from typing import Optional, List, Dict, Any

# Add project root to path for imports
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Configuration
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
WEBHOOK_ACCOUNTS_PATH = os.path.join(DATA_DIR, "webhook_accounts.json")
BACKUP_DIR = os.path.join(PROJECT_ROOT, "backups")
DEFAULT_ADMIN_USER_ID = "admin_001"


def create_backup() -> Optional[str]:
    """
    Create backup of webhook_accounts.json before migration.
    
    Returns:
        str: Path to backup file, or None if backup failed
    """
    if not os.path.exists(WEBHOOK_ACCOUNTS_PATH):
        print(f"⏭️  File not found, skipping backup: {WEBHOOK_ACCOUNTS_PATH}")
        return None
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"pre_migration_003_{timestamp}")
    
    try:
        os.makedirs(backup_path, exist_ok=True)
        backup_file = os.path.join(backup_path, "webhook_accounts.json")
        shutil.copy2(WEBHOOK_ACCOUNTS_PATH, backup_file)
        print(f"✅ Backup created: {backup_file}")
        return backup_path
    except Exception as e:
        print(f"❌ Backup failed: {e}")
        return None


def load_webhook_accounts() -> Optional[List[Dict[str, Any]]]:
    """
    Load webhook accounts from JSON file.
    
    Returns:
        List of webhook accounts, or None if file doesn't exist or is invalid
    """
    if not os.path.exists(WEBHOOK_ACCOUNTS_PATH):
        print(f"⏭️  File not found: {WEBHOOK_ACCOUNTS_PATH}")
        return None
    
    try:
        with open(WEBHOOK_ACCOUNTS_PATH, "r", encoding="utf-8") as f:
            accounts = json.load(f)
        
        if not isinstance(accounts, list):
            print(f"❌ Invalid format: expected list, got {type(accounts).__name__}")
            return None
        
        print(f"✅ Loaded {len(accounts)} webhook accounts from file")
        return accounts
    
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON: {e}")
        return None
    except Exception as e:
        print(f"❌ Failed to load file: {e}")
        return None


def migrate_webhook_accounts(accounts: List[Dict[str, Any]]) -> int:
    """
    Add user_id to all webhook accounts that don't have one.
    
    Args:
        accounts: List of webhook account dictionaries
        
    Returns:
        int: Number of accounts modified
    """
    modified = 0
    
    for account in accounts:
        if "user_id" not in account:
            account["user_id"] = DEFAULT_ADMIN_USER_ID
            modified += 1
            account_id = account.get("id", account.get("account", "unknown"))
            print(f"   📝 Added user_id to account: {account_id}")
    
    return modified


def save_webhook_accounts(accounts: List[Dict[str, Any]]) -> bool:
    """
    Save webhook accounts back to JSON file with UTF-8 encoding.
    
    Args:
        accounts: List of webhook account dictionaries
        
    Returns:
        bool: True if save succeeded
    """
    try:
        with open(WEBHOOK_ACCOUNTS_PATH, "w", encoding="utf-8") as f:
            json.dump(accounts, f, indent=2, ensure_ascii=False)
        print(f"✅ Saved {len(accounts)} webhook accounts to file")
        return True
    except Exception as e:
        print(f"❌ Failed to save file: {e}")
        return False


def run_migration() -> bool:
    """
    Execute the full migration.
    
    Returns:
        bool: True if migration succeeded
    """
    print("\n" + "=" * 60)
    print("🚀 Migration 003: Migrate Webhook Accounts JSON")
    print("=" * 60 + "\n")
    
    # Step 1: Check if file exists
    print("📂 Step 1: Checking file...")
    if not os.path.exists(WEBHOOK_ACCOUNTS_PATH):
        print(f"⏭️  {WEBHOOK_ACCOUNTS_PATH} not found, nothing to migrate")
        print("\n✅ Migration 003 completed (no action needed)")
        return True
    
    # Step 2: Create backup
    print("\n📦 Step 2: Creating backup...")
    backup_path = create_backup()
    if backup_path is None and os.path.exists(WEBHOOK_ACCOUNTS_PATH):
        print("❌ Migration aborted: Backup failed")
        return False
    
    # Step 3: Load accounts
    print("\n📖 Step 3: Loading webhook accounts...")
    accounts = load_webhook_accounts()
    if accounts is None:
        print("❌ Migration aborted: Failed to load file")
        return False
    
    if len(accounts) == 0:
        print("⏭️  No accounts in file, nothing to migrate")
        print("\n✅ Migration 003 completed (no action needed)")
        return True
    
    # Step 4: Check current state
    print("\n🔍 Step 4: Checking current state...")
    accounts_with_user_id = sum(1 for a in accounts if "user_id" in a)
    accounts_without_user_id = len(accounts) - accounts_with_user_id
    print(f"   📊 Total accounts: {len(accounts)}")
    print(f"   📊 Accounts with user_id: {accounts_with_user_id}")
    print(f"   📊 Accounts without user_id: {accounts_without_user_id}")
    
    if accounts_without_user_id == 0:
        print("\n✅ All accounts already have user_id, nothing to migrate")
        return True
    
    # Step 5: Migrate accounts
    print(f"\n📝 Step 5: Adding user_id to {accounts_without_user_id} accounts...")
    modified = migrate_webhook_accounts(accounts)
    
    # Step 6: Save changes
    print("\n💾 Step 6: Saving changes...")
    if not save_webhook_accounts(accounts):
        print("❌ Migration failed: Could not save file")
        print(f"⚠️  To restore from backup: cp {backup_path}/webhook_accounts.json {WEBHOOK_ACCOUNTS_PATH}")
        return False
    
    # Summary
    print("\n" + "=" * 60)
    print(f"✅ Migration 003 completed successfully!")
    print(f"   📊 Modified {modified} webhook accounts")
    print(f"   📊 Assigned to user: {DEFAULT_ADMIN_USER_ID}")
    if backup_path:
        print(f"   📦 Backup location: {backup_path}")
    print("=" * 60 + "\n")
    
    return True


def dry_run() -> None:
    """
    Check current state without making changes.
    """
    print("\n" + "=" * 60)
    print("🔍 Migration 003: Dry Run (Status Check)")
    print("=" * 60 + "\n")
    
    if not os.path.exists(WEBHOOK_ACCOUNTS_PATH):
        print(f"⏭️  File not found: {WEBHOOK_ACCOUNTS_PATH}")
        print("   Nothing to migrate")
        return
    
    accounts = load_webhook_accounts()
    if accounts is None:
        return
    
    accounts_with_user_id = sum(1 for a in accounts if "user_id" in a)
    accounts_without_user_id = len(accounts) - accounts_with_user_id
    
    print(f"\n   📊 Total accounts: {len(accounts)}")
    print(f"   📊 Accounts with user_id: {accounts_with_user_id}")
    print(f"   📊 Accounts without user_id: {accounts_without_user_id}")
    
    if accounts_without_user_id == 0:
        print("\n✅ Migration already applied!")
    else:
        print(f"\n⚠️  Migration needed: {accounts_without_user_id} accounts need user_id")
        print("   Run without --dry-run to apply.")


def print_usage() -> None:
    """Print usage information."""
    print("""
Usage: python migrations/003_migrate_webhook_accounts.py [OPTIONS]

Options:
    --dry-run    Check current status without making changes
    --help       Show this help message

Examples:
    python migrations/003_migrate_webhook_accounts.py              # Run migration
    python migrations/003_migrate_webhook_accounts.py --dry-run    # Check status only
""")


if __name__ == "__main__":
    args = sys.argv[1:]
    
    if "--help" in args or "-h" in args:
        print_usage()
        sys.exit(0)
    
    if "--dry-run" in args:
        dry_run()
        sys.exit(0)
    
    # Default: run migration
    success = run_migration()
    sys.exit(0 if success else 1)

