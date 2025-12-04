#!/usr/bin/env python
"""
Run All Migrations Script

Executes all migration scripts in sequence:
1. Backup data
2. Database migration (001)
3. Copy pairs JSON migration (002)
4. Webhook accounts JSON migration (003)

Usage:
    python scripts/run_all_migrations.py
    python scripts/run_all_migrations.py --dry-run
"""

import os
import sys
import subprocess

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def run_migration(script_name: str, dry_run: bool = False) -> bool:
    """Run a migration script."""
    script_path = os.path.join(PROJECT_ROOT, "migrations", script_name)
    
    if not os.path.exists(script_path):
        print(f"❌ Script not found: {script_path}")
        return False
    
    args = ["python", script_path]
    if dry_run:
        args.append("--dry-run")
    
    result = subprocess.run(args, cwd=PROJECT_ROOT)
    return result.returncode == 0


def run_backup() -> bool:
    """Run backup script."""
    script_path = os.path.join(PROJECT_ROOT, "scripts", "backup_before_migration.py")
    
    if not os.path.exists(script_path):
        print(f"❌ Backup script not found: {script_path}")
        return False
    
    result = subprocess.run(["python", script_path], cwd=PROJECT_ROOT)
    return result.returncode == 0


def main():
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    
    print("\n" + "=" * 60)
    print("🚀 Multi-User SaaS Migration Runner")
    print("=" * 60)
    
    if dry_run:
        print("\n⚠️  DRY RUN MODE - No changes will be made\n")
    
    # Step 1: Backup (skip in dry-run)
    if not dry_run:
        print("\n📦 Step 1: Creating backup...")
        if not run_backup():
            print("❌ Backup failed! Aborting.")
            return False
    else:
        print("\n📦 Step 1: Backup (skipped in dry-run)")
    
    # Step 2: Database migration
    print("\n📊 Step 2: Running database migration...")
    if not run_migration("001_add_users_table.py", dry_run):
        print("❌ Database migration failed!")
        return False
    
    # Step 3: Copy pairs migration
    print("\n📝 Step 3: Migrating copy_pairs.json...")
    if not run_migration("002_migrate_copy_pairs_json.py", dry_run):
        print("❌ Copy pairs migration failed!")
        return False
    
    # Step 4: Webhook accounts migration
    print("\n📝 Step 4: Migrating webhook_accounts.json...")
    if not run_migration("003_migrate_webhook_accounts.py", dry_run):
        print("❌ Webhook accounts migration failed!")
        return False
    
    # Summary
    print("\n" + "=" * 60)
    if dry_run:
        print("✅ Dry run completed!")
        print("   Run without --dry-run to apply changes.")
    else:
        print("✅ All migrations completed successfully!")
        print("\n📋 Next steps:")
        print("   1. Run: python scripts/create_admin_user.py")
        print("   2. Configure .env with Google OAuth credentials")
        print("   3. Restart server: python server.py")
        print("   4. Test: python tests/test_multi_user_isolation.py")
    print("=" * 60 + "\n")
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

