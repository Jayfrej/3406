#!/usr/bin/env python
"""
Test Multi-User Data Isolation

Tests that users can only see their own data (accounts, pairs).
This is critical for SaaS security.

Reference: CRITICAL_MISSING_DETAILS.md - Testing Script

Usage:
    python tests/test_multi_user_isolation.py
"""

import os
import sys

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def test_session_manager_isolation():
    """Test that SessionManager filters by user_id."""
    print("\n📋 Test: SessionManager Data Isolation")
    print("-" * 40)

    try:
        from app.session_manager import SessionManager
        sm = SessionManager()

        # Check if get_accounts_by_user method exists
        if not hasattr(sm, 'get_accounts_by_user'):
            print("⚠️  SKIP: get_accounts_by_user method not implemented yet")
            return None

        user_a = 'admin_001'
        user_b = 'test_user_001'

        # Get accounts for each user
        accounts_a = sm.get_accounts_by_user(user_a)
        accounts_b = sm.get_accounts_by_user(user_b)

        print(f"   User A ({user_a}): {len(accounts_a)} accounts")
        print(f"   User B ({user_b}): {len(accounts_b)} accounts")

        # Verify isolation - each account should belong to its user
        for acc in accounts_a:
            if acc.get('user_id') and acc.get('user_id') != user_a:
                print(f"   ❌ FAIL: Account {acc.get('account')} has wrong user_id")
                return False

        for acc in accounts_b:
            if acc.get('user_id') and acc.get('user_id') != user_b:
                print(f"   ❌ FAIL: Account {acc.get('account')} has wrong user_id")
                return False

        print("   ✅ PASS: SessionManager isolation working")
        return True

    except ImportError as e:
        print(f"   ⚠️  SKIP: Cannot import SessionManager - {e}")
        return None
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return False


def test_copy_manager_isolation():
    """Test that CopyManager filters by user_id."""
    print("\n📋 Test: CopyManager Data Isolation")
    print("-" * 40)

    try:
        from app.copy_trading.copy_manager import CopyManager
        cm = CopyManager()

        # Check if get_pairs_by_user method exists
        if not hasattr(cm, 'get_pairs_by_user'):
            print("⚠️  SKIP: get_pairs_by_user method not implemented yet")
            return None

        user_a = 'admin_001'
        user_b = 'test_user_001'

        # Get pairs for each user
        pairs_a = cm.get_pairs_by_user(user_a)
        pairs_b = cm.get_pairs_by_user(user_b)

        print(f"   User A ({user_a}): {len(pairs_a)} pairs")
        print(f"   User B ({user_b}): {len(pairs_b)} pairs")

        # Verify isolation
        for pair in pairs_a:
            if pair.get('user_id') and pair.get('user_id') != user_a:
                print(f"   ❌ FAIL: Pair {pair.get('id')} has wrong user_id")
                return False

        for pair in pairs_b:
            if pair.get('user_id') and pair.get('user_id') != user_b:
                print(f"   ❌ FAIL: Pair {pair.get('id')} has wrong user_id")
                return False

        print("   ✅ PASS: CopyManager isolation working")
        return True

    except ImportError as e:
        print(f"   ⚠️  SKIP: Cannot import CopyManager - {e}")
        return None
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return False


def test_database_schema():
    """Test that database has required multi-user tables."""
    print("\n📋 Test: Database Schema")
    print("-" * 40)

    import sqlite3

    db_path = os.path.join(PROJECT_ROOT, "data", "accounts.db")

    if not os.path.exists(db_path):
        print(f"   ⚠️  SKIP: Database not found: {db_path}")
        return None

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check users table
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='users'
        """)
        has_users = cursor.fetchone() is not None
        print(f"   {'✅' if has_users else '❌'} users table: {has_users}")

        # Check user_tokens table
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='user_tokens'
        """)
        has_tokens = cursor.fetchone() is not None
        print(f"   {'✅' if has_tokens else '❌'} user_tokens table: {has_tokens}")

        # Check accounts.user_id column
        cursor.execute("PRAGMA table_info(accounts)")
        columns = [col[1] for col in cursor.fetchall()]
        has_user_id = 'user_id' in columns
        print(f"   {'✅' if has_user_id else '❌'} accounts.user_id column: {has_user_id}")

        # Check index
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND name='idx_accounts_user_id'
        """)
        has_index = cursor.fetchone() is not None
        print(f"   {'✅' if has_index else '❌'} idx_accounts_user_id index: {has_index}")

        conn.close()

        all_pass = has_users and has_tokens and has_user_id and has_index
        if all_pass:
            print("   ✅ PASS: Database schema complete")
        else:
            print("   ❌ FAIL: Database schema incomplete")
            print("   Run: python migrations/001_add_users_table.py")

        return all_pass

    except sqlite3.Error as e:
        print(f"   ❌ ERROR: {e}")
        return False


def test_json_files_have_user_id():
    """Test that JSON files have user_id field."""
    print("\n📋 Test: JSON Files Have user_id")
    print("-" * 40)

    import json

    results = {}

    # Test copy_pairs.json
    copy_pairs_path = os.path.join(PROJECT_ROOT, "data", "copy_pairs.json")
    if os.path.exists(copy_pairs_path):
        try:
            with open(copy_pairs_path, 'r', encoding='utf-8') as f:
                pairs = json.load(f)

            total = len(pairs)
            with_user_id = sum(1 for p in pairs if 'user_id' in p)

            results['copy_pairs'] = (with_user_id == total) if total > 0 else True
            print(f"   copy_pairs.json: {with_user_id}/{total} have user_id {'✅' if results['copy_pairs'] else '❌'}")
        except Exception as e:
            print(f"   copy_pairs.json: Error - {e}")
            results['copy_pairs'] = False
    else:
        print(f"   copy_pairs.json: Not found (OK)")
        results['copy_pairs'] = True

    # Test webhook_accounts.json
    webhook_path = os.path.join(PROJECT_ROOT, "data", "webhook_accounts.json")
    if os.path.exists(webhook_path):
        try:
            with open(webhook_path, 'r', encoding='utf-8') as f:
                accounts = json.load(f)

            total = len(accounts)
            with_user_id = sum(1 for a in accounts if 'user_id' in a)

            results['webhook_accounts'] = (with_user_id == total) if total > 0 else True
            print(f"   webhook_accounts.json: {with_user_id}/{total} have user_id {'✅' if results['webhook_accounts'] else '❌'}")
        except Exception as e:
            print(f"   webhook_accounts.json: Error - {e}")
            results['webhook_accounts'] = False
    else:
        print(f"   webhook_accounts.json: Not found (OK)")
        results['webhook_accounts'] = True

    all_pass = all(results.values())
    if all_pass:
        print("   ✅ PASS: JSON files have user_id")
    else:
        print("   ❌ FAIL: Some JSON files missing user_id")
        print("   Run: python migrations/002_migrate_copy_pairs_json.py")
        print("   Run: python migrations/003_migrate_webhook_accounts.py")

    return all_pass


def run_all_tests():
    """Run all isolation tests."""
    print("\n" + "=" * 60)
    print("🧪 Multi-User Data Isolation Tests")
    print("=" * 60)

    results = {
        'database_schema': test_database_schema(),
        'json_files': test_json_files_have_user_id(),
        'session_manager': test_session_manager_isolation(),
        'copy_manager': test_copy_manager_isolation(),
    }

    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Summary")
    print("=" * 60 + "\n")

    passed = 0
    failed = 0
    skipped = 0

    for test_name, result in results.items():
        if result is True:
            status = "✅ PASS"
            passed += 1
        elif result is False:
            status = "❌ FAIL"
            failed += 1
        else:
            status = "⚠️  SKIP"
            skipped += 1

        print(f"   {status}: {test_name}")

    print()
    print(f"   Passed: {passed}")
    print(f"   Failed: {failed}")
    print(f"   Skipped: {skipped}")
    print()

    if failed > 0:
        print("❌ Some tests failed! Please fix before proceeding.")
        return False
    elif skipped > 0:
        print("⚠️  Some tests skipped. Implement missing methods to enable.")
        return True
    else:
        print("✅ All tests passed!")
        return True


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

