#!/usr/bin/env python
"""
Migration 002: Migrate Copy Pairs JSON

This migration adds user_id to all existing copy pairs in the JSON file,
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
COPY_PAIRS_PATH = os.path.join(DATA_DIR, "copy_pairs.json")
BACKUP_DIR = os.path.join(PROJECT_ROOT, "backups")
DEFAULT_ADMIN_USER_ID = "admin_001"


def create_backup() -> Optional[str]:
    """
    Create backup of copy_pairs.json before migration.

    Returns:
        str: Path to backup file, or None if backup failed
    """
    if not os.path.exists(COPY_PAIRS_PATH):
        print(f"⏭️  File not found, skipping backup: {COPY_PAIRS_PATH}")
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"pre_migration_002_{timestamp}")

    try:
        os.makedirs(backup_path, exist_ok=True)
        backup_file = os.path.join(backup_path, "copy_pairs.json")
        shutil.copy2(COPY_PAIRS_PATH, backup_file)
        print(f"✅ Backup created: {backup_file}")
        return backup_path
    except Exception as e:
        print(f"❌ Backup failed: {e}")
        return None


def load_copy_pairs() -> Optional[List[Dict[str, Any]]]:
    """
    Load copy pairs from JSON file.

    Returns:
        List of copy pairs, or None if file doesn't exist or is invalid
    """
    if not os.path.exists(COPY_PAIRS_PATH):
        print(f"⏭️  File not found: {COPY_PAIRS_PATH}")
        return None

    try:
        with open(COPY_PAIRS_PATH, "r", encoding="utf-8") as f:
            pairs = json.load(f)

        if not isinstance(pairs, list):
            print(f"❌ Invalid format: expected list, got {type(pairs).__name__}")
            return None

        print(f"✅ Loaded {len(pairs)} copy pairs from file")
        return pairs

    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON: {e}")
        return None
    except Exception as e:
        print(f"❌ Failed to load file: {e}")
        return None


def migrate_copy_pairs(pairs: List[Dict[str, Any]]) -> int:
    """
    Add user_id to all copy pairs that don't have one.

    Args:
        pairs: List of copy pair dictionaries

    Returns:
        int: Number of pairs modified
    """
    modified = 0

    for pair in pairs:
        if "user_id" not in pair:
            pair["user_id"] = DEFAULT_ADMIN_USER_ID
            modified += 1
            pair_id = pair.get("id", "unknown")
            print(f"   📝 Added user_id to pair: {pair_id}")

    return modified


def save_copy_pairs(pairs: List[Dict[str, Any]]) -> bool:
    """
    Save copy pairs back to JSON file with UTF-8 encoding.

    Args:
        pairs: List of copy pair dictionaries

    Returns:
        bool: True if save succeeded
    """
    try:
        with open(COPY_PAIRS_PATH, "w", encoding="utf-8") as f:
            json.dump(pairs, f, indent=2, ensure_ascii=False)
        print(f"✅ Saved {len(pairs)} copy pairs to file")
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
    print("🚀 Migration 002: Migrate Copy Pairs JSON")
    print("=" * 60 + "\n")

    # Step 1: Check if file exists
    print("📂 Step 1: Checking file...")
    if not os.path.exists(COPY_PAIRS_PATH):
        print(f"⏭️  {COPY_PAIRS_PATH} not found, nothing to migrate")
        print("\n✅ Migration 002 completed (no action needed)")
        return True

    # Step 2: Create backup
    print("\n📦 Step 2: Creating backup...")
    backup_path = create_backup()
    if backup_path is None and os.path.exists(COPY_PAIRS_PATH):
        print("❌ Migration aborted: Backup failed")
        return False

    # Step 3: Load pairs
    print("\n📖 Step 3: Loading copy pairs...")
    pairs = load_copy_pairs()
    if pairs is None:
        print("❌ Migration aborted: Failed to load file")
        return False

    if len(pairs) == 0:
        print("⏭️  No pairs in file, nothing to migrate")
        print("\n✅ Migration 002 completed (no action needed)")
        return True

    # Step 4: Check current state
    print("\n🔍 Step 4: Checking current state...")
    pairs_with_user_id = sum(1 for p in pairs if "user_id" in p)
    pairs_without_user_id = len(pairs) - pairs_with_user_id
    print(f"   📊 Total pairs: {len(pairs)}")
    print(f"   📊 Pairs with user_id: {pairs_with_user_id}")
    print(f"   📊 Pairs without user_id: {pairs_without_user_id}")

    if pairs_without_user_id == 0:
        print("\n✅ All pairs already have user_id, nothing to migrate")
        return True

    # Step 5: Migrate pairs
    print(f"\n📝 Step 5: Adding user_id to {pairs_without_user_id} pairs...")
    modified = migrate_copy_pairs(pairs)

    # Step 6: Save changes
    print("\n💾 Step 6: Saving changes...")
    if not save_copy_pairs(pairs):
        print("❌ Migration failed: Could not save file")
        print(f"⚠️  To restore from backup: cp {backup_path}/copy_pairs.json {COPY_PAIRS_PATH}")
        return False

    # Summary
    print("\n" + "=" * 60)
    print(f"✅ Migration 002 completed successfully!")
    print(f"   📊 Modified {modified} copy pairs")
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
    print("🔍 Migration 002: Dry Run (Status Check)")
    print("=" * 60 + "\n")

    if not os.path.exists(COPY_PAIRS_PATH):
        print(f"⏭️  File not found: {COPY_PAIRS_PATH}")
        print("   Nothing to migrate")
        return

    pairs = load_copy_pairs()
    if pairs is None:
        return

    pairs_with_user_id = sum(1 for p in pairs if "user_id" in p)
    pairs_without_user_id = len(pairs) - pairs_with_user_id

    print(f"\n   📊 Total pairs: {len(pairs)}")
    print(f"   📊 Pairs with user_id: {pairs_with_user_id}")
    print(f"   📊 Pairs without user_id: {pairs_without_user_id}")

    if pairs_without_user_id == 0:
        print("\n✅ Migration already applied!")
    else:
        print(f"\n⚠️  Migration needed: {pairs_without_user_id} pairs need user_id")
        print("   Run without --dry-run to apply.")


def print_usage() -> None:
    """Print usage information."""
    print("""
Usage: python migrations/002_migrate_copy_pairs_json.py [OPTIONS]

Options:
    --dry-run    Check current status without making changes
    --help       Show this help message

Examples:
    python migrations/002_migrate_copy_pairs_json.py              # Run migration
    python migrations/002_migrate_copy_pairs_json.py --dry-run    # Check status only
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

