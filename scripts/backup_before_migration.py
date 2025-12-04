#!/usr/bin/env python
"""
Backup Before Migration Script (Windows Compatible)

Creates a complete backup of all data files before running migrations.

Reference: CRITICAL_MISSING_DETAILS.md - Backup Script

Usage:
    python scripts/backup_before_migration.py
"""

import os
import sys
import shutil
from datetime import datetime

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Configuration
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
BACKUP_DIR = os.path.join(PROJECT_ROOT, "backups")
ENV_FILE = os.path.join(PROJECT_ROOT, ".env")


def create_backup() -> bool:
    """
    Create complete backup of database, JSON files, and .env.

    Returns:
        bool: True if backup succeeded
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"pre_migration_{timestamp}")

    print("\n" + "=" * 60)
    print(f"🔄 Creating Backup: {backup_path}")
    print("=" * 60 + "\n")

    try:
        os.makedirs(backup_path, exist_ok=True)
        backed_up = []

        # Backup database
        db_path = os.path.join(DATA_DIR, "accounts.db")
        if os.path.exists(db_path):
            shutil.copy2(db_path, os.path.join(backup_path, "accounts.db"))
            backed_up.append("accounts.db")
            print("✅ Database backed up: accounts.db")
        else:
            print("⚠️  Database not found: accounts.db")

        # Backup JSON files
        json_files = [
            "copy_pairs.json",
            "api_keys.json",
            "master_accounts.json",
            "slave_accounts.json",
            "webhook_accounts.json"
        ]

        for json_file in json_files:
            src_path = os.path.join(DATA_DIR, json_file)
            if os.path.exists(src_path):
                shutil.copy2(src_path, os.path.join(backup_path, json_file))
                backed_up.append(json_file)
                print(f"✅ JSON backed up: {json_file}")

        # Backup .env
        if os.path.exists(ENV_FILE):
            shutil.copy2(ENV_FILE, os.path.join(backup_path, ".env"))
            backed_up.append(".env")
            print("✅ Environment file backed up: .env")
        else:
            print("⚠️  Environment file not found: .env")

        # Create restore manifest
        manifest_path = os.path.join(backup_path, "RESTORE.md")
        with open(manifest_path, "w", encoding="utf-8") as f:
            f.write(f"""# Backup Created: {datetime.now().isoformat()}

## Files Backed Up
{chr(10).join(f'- {f}' for f in backed_up)}

## To Restore

### Option 1: Manual restore
```powershell
# Stop server first
# Copy files back:
Copy-Item "{backup_path}\\accounts.db" "{DATA_DIR}\\"
Copy-Item "{backup_path}\\*.json" "{DATA_DIR}\\"
Copy-Item "{backup_path}\\.env" "{PROJECT_ROOT}\\"
# Restart server
```

### Option 2: Using restore script
```powershell
python scripts/restore_backup.py "{backup_path}"
```

## Backup Location
{backup_path}
""")

        print(f"\n✅ Backup manifest created: RESTORE.md")

        # Summary
        print("\n" + "=" * 60)
        print("✅ Backup completed successfully!")
        print(f"   📊 Files backed up: {len(backed_up)}")
        print(f"   📦 Backup location: {backup_path}")
        print("=" * 60 + "\n")

        return True

    except Exception as e:
        print(f"❌ Backup failed: {e}")
        return False


def list_backups() -> None:
    """List all available backups."""
    print("\n" + "=" * 60)
    print("📦 Available Backups")
    print("=" * 60 + "\n")

    if not os.path.exists(BACKUP_DIR):
        print("No backups found.")
        return

    backups = sorted([
        d for d in os.listdir(BACKUP_DIR)
        if os.path.isdir(os.path.join(BACKUP_DIR, d))
    ], reverse=True)

    if not backups:
        print("No backups found.")
        return

    for backup in backups:
        backup_path = os.path.join(BACKUP_DIR, backup)
        files = os.listdir(backup_path)
        file_count = len([f for f in files if not f.endswith('.md')])
        print(f"   📁 {backup} ({file_count} files)")

    print(f"\n   Total backups: {len(backups)}")


def print_usage() -> None:
    """Print usage information."""
    print("""
Usage: python scripts/backup_before_migration.py [OPTIONS]

Options:
    --list       List all available backups
    --help       Show this help message

Examples:
    python scripts/backup_before_migration.py          # Create backup
    python scripts/backup_before_migration.py --list   # List backups
""")


if __name__ == "__main__":
    args = sys.argv[1:]

    if "--help" in args or "-h" in args:
        print_usage()
        sys.exit(0)

    if "--list" in args:
        list_backups()
        sys.exit(0)

    # Default: create backup
    success = create_backup()
    sys.exit(0 if success else 1)

