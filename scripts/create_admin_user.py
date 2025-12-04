#!/usr/bin/env python
"""
Create Admin User Script

Interactive script to create an admin user for the multi-user system.

Reference: CRITICAL_MISSING_DETAILS.md - Admin User Creation Script

Usage:
    python scripts/create_admin_user.py
    python scripts/create_admin_user.py --email admin@example.com --name "Admin"
"""

import os
import sys
import sqlite3
import secrets
from datetime import datetime

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Try to load .env
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
except ImportError:
    pass

# Configuration
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
DB_PATH = os.path.join(DATA_DIR, "accounts.db")


def generate_user_id(email: str) -> str:
    """Generate a unique user_id from email."""
    username = email.split("@")[0]
    return f"admin_{username}"


def generate_webhook_token() -> str:
    """Generate a unique webhook token."""
    return f"whk_{secrets.token_urlsafe(32)}"


def check_database() -> bool:
    """Check if database and users table exist."""
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found: {DB_PATH}")
        print("   Please run migration 001 first:")
        print("   python migrations/001_add_users_table.py")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='users'
        """)
        if cursor.fetchone() is None:
            print("❌ users table not found")
            print("   Please run migration 001 first:")
            print("   python migrations/001_add_users_table.py")
            return False
        return True
    finally:
        conn.close()


def get_existing_admins() -> list:
    """Get list of existing admin users."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT user_id, email, name FROM users WHERE is_admin = 1
        """)
        return cursor.fetchall()
    finally:
        conn.close()


def create_admin(email: str, name: str) -> bool:
    """
    Create admin user in database.

    Args:
        email: Admin email address
        name: Admin display name

    Returns:
        bool: True if created successfully
    """
    user_id = generate_user_id(email)
    webhook_token = generate_webhook_token()
    now = datetime.now().isoformat()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if user exists
        cursor.execute("SELECT user_id, is_admin FROM users WHERE email = ?", (email,))
        existing = cursor.fetchone()

        if existing:
            existing_user_id, is_admin = existing
            if is_admin:
                print(f"⚠️  User already exists and is admin: {email}")
                return True
            else:
                # Update to admin
                confirm = input(f"User exists but is not admin. Promote to admin? (yes/no): ")
                if confirm.lower() == "yes":
                    cursor.execute("""
                        UPDATE users SET is_admin = 1 WHERE email = ?
                    """, (email,))
                    conn.commit()
                    print(f"✅ User promoted to admin: {email}")
                    return True
                else:
                    print("Cancelled")
                    return False

        # Create new user
        cursor.execute("""
            INSERT INTO users (user_id, email, name, is_active, is_admin, created_at, last_login)
            VALUES (?, ?, ?, 1, 1, ?, ?)
        """, (user_id, email, name, now, now))

        # Create webhook token
        token_id = f"tok_{secrets.token_urlsafe(16)}"
        cursor.execute("""
            INSERT INTO user_tokens (token_id, user_id, webhook_token, created_at)
            VALUES (?, ?, ?, ?)
        """, (token_id, user_id, webhook_token, now))

        conn.commit()

        print(f"\n✅ Admin user created successfully!")
        print(f"   User ID: {user_id}")
        print(f"   Email: {email}")
        print(f"   Name: {name}")
        print(f"   Webhook Token: {webhook_token}")

        return True

    except sqlite3.IntegrityError as e:
        print(f"❌ Database error: {e}")
        return False
    finally:
        conn.close()


def interactive_create() -> bool:
    """Interactive admin creation flow."""
    print("\n" + "=" * 60)
    print("👤 Create Admin User")
    print("=" * 60 + "\n")

    # Get default email from .env
    default_email = os.getenv("ADMIN_EMAIL", "")

    # Get email
    if default_email:
        email = input(f"Admin email [{default_email}]: ").strip() or default_email
    else:
        email = input("Admin email: ").strip()

    if not email:
        print("❌ Email is required")
        return False

    if "@" not in email:
        print("❌ Invalid email format")
        return False

    # Get name
    default_name = email.split("@")[0].title()
    name = input(f"Display name [{default_name}]: ").strip() or default_name

    # Confirm
    print()
    print(f"Creating admin user:")
    print(f"   Email: {email}")
    print(f"   Name: {name}")
    print()

    confirm = input("Continue? (yes/no): ")
    if confirm.lower() != "yes":
        print("Cancelled")
        return False

    return create_admin(email, name)


def print_usage() -> None:
    """Print usage information."""
    print("""
Usage: python scripts/create_admin_user.py [OPTIONS]

Options:
    --email EMAIL    Admin email address
    --name NAME      Admin display name
    --list           List existing admin users
    --help           Show this help message

Examples:
    python scripts/create_admin_user.py                           # Interactive mode
    python scripts/create_admin_user.py --email admin@example.com # With email
    python scripts/create_admin_user.py --list                    # List admins
""")


if __name__ == "__main__":
    args = sys.argv[1:]

    if "--help" in args or "-h" in args:
        print_usage()
        sys.exit(0)

    # Check database first
    if not check_database():
        sys.exit(1)

    if "--list" in args:
        print("\n" + "=" * 60)
        print("👥 Existing Admin Users")
        print("=" * 60 + "\n")

        admins = get_existing_admins()
        if admins:
            for user_id, email, name in admins:
                print(f"   {email} ({name}) - ID: {user_id}")
            print(f"\n   Total: {len(admins)} admin(s)")
        else:
            print("   No admin users found")
        sys.exit(0)

    # Check for command line args
    email = None
    name = None

    if "--email" in args:
        idx = args.index("--email")
        if idx + 1 < len(args):
            email = args[idx + 1]

    if "--name" in args:
        idx = args.index("--name")
        if idx + 1 < len(args):
            name = args[idx + 1]

    if email:
        # Non-interactive mode
        if not name:
            name = email.split("@")[0].title()
        success = create_admin(email, name)
    else:
        # Interactive mode
        success = interactive_create()

    sys.exit(0 if success else 1)

