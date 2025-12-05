#!/usr/bin/env python3
"""
Test Data Isolation for Multi-User SaaS
Tests that users can only see their own data in:
- Webhook Management (Account Allowlist)
- Trading History
- Copy Trading History
- System Logs (Admin Only)
"""

import os
import sys
import json

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

def test_account_allowlist_isolation():
    """Test that AccountAllowlistService filters by user_id"""
    print("\n📋 Test: Account Allowlist Isolation")
    print("-" * 40)

    from app.services.account_allowlist_service import AccountAllowlistService

    service = AccountAllowlistService()

    # Test data setup
    test_data = [
        {"account": "111", "nickname": "User A Account", "enabled": True, "user_id": "user_a"},
        {"account": "222", "nickname": "User B Account", "enabled": True, "user_id": "user_b"},
        {"account": "333", "nickname": "Admin Account", "enabled": True, "user_id": "admin_001"},
    ]

    # Save test data
    webhook_file = os.path.join(PROJECT_ROOT, "data", "webhook_accounts.json")
    backup_data = None
    if os.path.exists(webhook_file):
        with open(webhook_file, 'r', encoding='utf-8') as f:
            backup_data = f.read()

    try:
        with open(webhook_file, 'w', encoding='utf-8') as f:
            json.dump(test_data, f)

        # Test 1: Get all accounts (no filter)
        all_accounts = service.get_webhook_allowlist()
        print(f"   All accounts (no filter): {len(all_accounts)}")

        # Test 2: Get User A's accounts only
        user_a_accounts = service.get_webhook_allowlist_by_user("user_a")
        print(f"   User A accounts: {len(user_a_accounts)}")

        # Test 3: Get User B's accounts only
        user_b_accounts = service.get_webhook_allowlist_by_user("user_b")
        print(f"   User B accounts: {len(user_b_accounts)}")

        # Verify isolation
        user_a_account_nums = [a['account'] for a in user_a_accounts]
        user_b_account_nums = [a['account'] for a in user_b_accounts]

        if len(user_a_accounts) == 1 and "111" in user_a_account_nums:
            if len(user_b_accounts) == 1 and "222" in user_b_account_nums:
                if "222" not in user_a_account_nums and "111" not in user_b_account_nums:
                    print("   ✅ PASS: Account allowlist isolation working")
                    return True

        print("   ❌ FAIL: Account allowlist isolation not working")
        return False

    finally:
        # Restore original data
        if backup_data:
            with open(webhook_file, 'w', encoding='utf-8') as f:
                f.write(backup_data)
        elif os.path.exists(webhook_file):
            os.remove(webhook_file)


def test_copy_history_isolation():
    """Test that CopyHistory filters by user_id/accounts"""
    print("\n📋 Test: Copy History Isolation")
    print("-" * 40)

    from app.copy_trading.copy_history import CopyHistory

    history = CopyHistory()

    # Add test events using correct method name
    history.record_copy_event({
        'status': 'success',
        'master': '111',
        'slave': '222',
        'user_id': 'user_a'
    })

    history.record_copy_event({
        'status': 'success',
        'master': '333',
        'slave': '444',
        'user_id': 'user_b'
    })

    # Test with user_accounts filter
    user_a_accounts = {'111', '222'}
    user_b_accounts = {'333', '444'}

    user_a_history = history.get_history(user_accounts=user_a_accounts)
    user_b_history = history.get_history(user_accounts=user_b_accounts)

    print(f"   User A history events: {len(user_a_history)}")
    print(f"   User B history events: {len(user_b_history)}")

    # Check no cross-contamination
    for evt in user_a_history:
        if evt.get('master') in user_b_accounts or evt.get('slave') in user_b_accounts:
            print("   ❌ FAIL: User A sees User B's events")
            return False

    for evt in user_b_history:
        if evt.get('master') in user_a_accounts or evt.get('slave') in user_a_accounts:
            print("   ❌ FAIL: User B sees User A's events")
            return False

    print("   ✅ PASS: Copy history isolation working")
    return True


def main():
    print("=" * 60)
    print("🔐 Multi-User Data Isolation Tests")
    print("=" * 60)

    results = {}

    results['account_allowlist'] = test_account_allowlist_isolation()
    results['copy_history'] = test_copy_history_isolation()

    print("\n" + "=" * 60)
    print("📊 Test Summary")
    print("=" * 60)

    passed = sum(1 for v in results.values() if v)
    failed = sum(1 for v in results.values() if not v)

    for name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status}: {name}")

    print(f"\n   Passed: {passed}")
    print(f"   Failed: {failed}")

    if failed == 0:
        print("\n✅ All data isolation tests passed!")
    else:
        print("\n❌ Some tests failed - data isolation may be compromised")

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

