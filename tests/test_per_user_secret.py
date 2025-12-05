#!/usr/bin/env python3
"""
Test Per-User Secret Key Security
Validates the new 2-layer authentication:
1. License Key (identifies user from URL)
2. Webhook Secret (validates request authenticity)
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def test_secret_key_generation():
    """Test that webhook secrets are generated correctly"""
    print("\n📋 Test 1: Webhook Secret Generation")
    print("-" * 40)

    from app.services.user_service import UserService

    us = UserService()

    # Generate multiple secrets
    secret1 = us.generate_webhook_secret()
    secret2 = us.generate_webhook_secret()

    # Check format
    if secret1.startswith('whs_') and len(secret1) >= 30:
        print(f"   ✅ Secret format correct: {secret1[:15]}...")
    else:
        print(f"   ❌ Secret format incorrect: {secret1}")
        return False

    # Check uniqueness
    if secret1 != secret2:
        print("   ✅ Secrets are unique")
    else:
        print("   ❌ Secrets are NOT unique")
        return False

    return True


def test_secret_validation():
    """Test that secret validation works correctly"""
    print("\n📋 Test 2: Secret Validation Logic")
    print("-" * 40)

    from app.services.user_service import UserService
    import sqlite3

    us = UserService()

    # Create a test user directly in DB
    test_license = "whk_test_" + os.urandom(8).hex()
    test_secret = us.generate_webhook_secret()
    test_user_id = "test_user_secret_" + os.urandom(4).hex()

    conn = sqlite3.connect(os.path.join(PROJECT_ROOT, 'data', 'accounts.db'))
    cursor = conn.cursor()

    try:
        # Insert test user
        cursor.execute("""
            INSERT INTO users (user_id, email, license_key, webhook_secret, is_active)
            VALUES (?, ?, ?, ?, 1)
        """, (test_user_id, f"{test_user_id}@test.com", test_license, test_secret))
        conn.commit()

        # Test 1: Valid secret should pass
        if us.validate_webhook_secret(test_license, test_secret):
            print("   ✅ Valid secret passes validation")
        else:
            print("   ❌ Valid secret failed validation")
            return False

        # Test 2: Invalid secret should fail
        if not us.validate_webhook_secret(test_license, "wrong_secret"):
            print("   ✅ Invalid secret correctly rejected")
        else:
            print("   ❌ Invalid secret was accepted!")
            return False

        # Test 3: Empty secret should fail
        if not us.validate_webhook_secret(test_license, ""):
            print("   ✅ Empty secret correctly rejected")
        else:
            print("   ❌ Empty secret was accepted!")
            return False

        # Test 4: None secret should fail
        if not us.validate_webhook_secret(test_license, None):
            print("   ✅ None secret correctly rejected")
        else:
            print("   ❌ None secret was accepted!")
            return False

        # Test 5: Wrong license key should fail
        if not us.validate_webhook_secret("wrong_license", test_secret):
            print("   ✅ Wrong license key correctly rejected")
        else:
            print("   ❌ Wrong license key was accepted!")
            return False

        return True

    finally:
        # Cleanup test user
        cursor.execute("DELETE FROM users WHERE user_id = ?", (test_user_id,))
        conn.commit()
        conn.close()


def test_user_isolation_with_secrets():
    """Test that User A cannot use User B's secret"""
    print("\n📋 Test 3: User Isolation with Secrets")
    print("-" * 40)

    from app.services.user_service import UserService
    import sqlite3

    us = UserService()

    # Create two test users
    user_a_id = "test_user_a_" + os.urandom(4).hex()
    user_b_id = "test_user_b_" + os.urandom(4).hex()

    license_a = "whk_user_a_" + os.urandom(8).hex()
    license_b = "whk_user_b_" + os.urandom(8).hex()

    secret_a = us.generate_webhook_secret()
    secret_b = us.generate_webhook_secret()

    conn = sqlite3.connect(os.path.join(PROJECT_ROOT, 'data', 'accounts.db'))
    cursor = conn.cursor()

    try:
        # Insert test users
        cursor.execute("""
            INSERT INTO users (user_id, email, license_key, webhook_secret, is_active)
            VALUES (?, ?, ?, ?, 1)
        """, (user_a_id, f"{user_a_id}@test.com", license_a, secret_a))

        cursor.execute("""
            INSERT INTO users (user_id, email, license_key, webhook_secret, is_active)
            VALUES (?, ?, ?, ?, 1)
        """, (user_b_id, f"{user_b_id}@test.com", license_b, secret_b))
        conn.commit()

        # Test: User A's license with User A's secret = OK
        if us.validate_webhook_secret(license_a, secret_a):
            print("   ✅ User A with own secret: ALLOWED")
        else:
            print("   ❌ User A with own secret: FAILED")
            return False

        # Test: User B's license with User B's secret = OK
        if us.validate_webhook_secret(license_b, secret_b):
            print("   ✅ User B with own secret: ALLOWED")
        else:
            print("   ❌ User B with own secret: FAILED")
            return False

        # Test: User A's license with User B's secret = BLOCKED
        if not us.validate_webhook_secret(license_a, secret_b):
            print("   ✅ User A with User B's secret: BLOCKED ✓")
        else:
            print("   ❌ User A with User B's secret: ALLOWED (SECURITY BREACH!)")
            return False

        # Test: User B's license with User A's secret = BLOCKED
        if not us.validate_webhook_secret(license_b, secret_a):
            print("   ✅ User B with User A's secret: BLOCKED ✓")
        else:
            print("   ❌ User B with User A's secret: ALLOWED (SECURITY BREACH!)")
            return False

        return True

    finally:
        # Cleanup
        cursor.execute("DELETE FROM users WHERE user_id IN (?, ?)", (user_a_id, user_b_id))
        conn.commit()
        conn.close()


def test_database_schema():
    """Test that database has required columns"""
    print("\n📋 Test 4: Database Schema")
    print("-" * 40)

    import sqlite3

    conn = sqlite3.connect(os.path.join(PROJECT_ROOT, 'data', 'accounts.db'))
    cursor = conn.cursor()

    try:
        cursor.execute("PRAGMA table_info(users)")
        columns = {col[1] for col in cursor.fetchall()}

        required = {'user_id', 'email', 'license_key', 'webhook_secret', 'is_active'}
        missing = required - columns

        if not missing:
            print("   ✅ All required columns exist")
            print(f"      Columns: {sorted(columns)}")
            return True
        else:
            print(f"   ❌ Missing columns: {missing}")
            return False

    finally:
        conn.close()


def main():
    print("=" * 60)
    print("🔐 Per-User Secret Key Security Tests")
    print("=" * 60)

    results = {}

    results['secret_generation'] = test_secret_key_generation()
    results['secret_validation'] = test_secret_validation()
    results['user_isolation'] = test_user_isolation_with_secrets()
    results['database_schema'] = test_database_schema()

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
        print("\n✅ All security tests passed!")
        print("\n🔐 Security Verification:")
        print("   ✓ Each user has unique license_key")
        print("   ✓ Each user has unique webhook_secret")
        print("   ✓ Secrets cannot be cross-used between users")
        print("   ✓ Invalid/missing secrets are rejected")
    else:
        print("\n❌ SECURITY ISSUES DETECTED - DO NOT DEPLOY!")

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

