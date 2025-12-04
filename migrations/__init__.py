"""
Database Migrations Package

This package contains migration scripts for the Multi-User SaaS migration.

Migration Scripts:
- 001_add_users_table.py: Creates users, user_tokens tables and adds user_id to accounts

Usage:
    python migrations/001_add_users_table.py          # Run migration
    python migrations/001_add_users_table.py --dry-run  # Check status only
    python migrations/001_add_users_table.py --rollback <backup_path>  # Rollback

Safety Rules (from copilot-instructions.md):
1. Always create backup before migration
2. Non-destructive: preserve existing data
3. Assign legacy data to default admin user
"""

