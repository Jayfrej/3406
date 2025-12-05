#!/usr/bin/env python
"""
Test script to verify all unified routes are working
"""
import requests
import json
import sys

BASE_URL = "http://localhost:5000"

# Replace with your actual license key
TEST_LICENSE_KEY = "whk_dd7_990KfkwaCXHH6rjaYpLe"
TEST_ACCOUNT = "279289341"
TEST_SECRET = "your_webhook_secret"  # Replace with actual secret

def test_route(method, path, data=None, expected_status=None):
    """Test a single route"""
    url = f"{BASE_URL}{path}"
    try:
        if method == "GET":
            response = requests.get(url, timeout=5)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=5)
        else:
            print(f"❌ Unknown method: {method}")
            return False

        status = response.status_code
        if expected_status and status != expected_status:
            print(f"⚠️  {method} {path} → {status} (expected {expected_status})")
        elif status in [200, 401, 403]:
            print(f"✅ {method} {path} → {status}")
        else:
            print(f"❌ {method} {path} → {status}")

        return status in [200, 401, 403, 400]
    except requests.exceptions.ConnectionError:
        print(f"❌ {method} {path} → Connection refused (server not running?)")
        return False
    except Exception as e:
        print(f"❌ {method} {path} → Error: {e}")
        return False

def main():
    print("=" * 60)
    print("Testing Unified Routes")
    print("=" * 60)
    print(f"Base URL: {BASE_URL}")
    print(f"License Key: {TEST_LICENSE_KEY}")
    print(f"Account: {TEST_ACCOUNT}")
    print("=" * 60)

    results = []

    # Test all unified routes
    routes = [
        # Main webhook endpoints
        ("GET", f"/{TEST_LICENSE_KEY}", None),
        ("POST", f"/{TEST_LICENSE_KEY}", {"action": "BUY", "symbol": "EURUSD", "secret": TEST_SECRET}),

        # EA API endpoints
        ("POST", f"/{TEST_LICENSE_KEY}/api/ea/heartbeat", {"account": TEST_ACCOUNT, "broker": "Test"}),
        ("GET", f"/{TEST_LICENSE_KEY}/api/ea/get_signals?account={TEST_ACCOUNT}", None),
        ("POST", f"/{TEST_LICENSE_KEY}/api/ea/get_signals", {"account": TEST_ACCOUNT}),
        ("POST", f"/{TEST_LICENSE_KEY}/api/ea/confirm_execution", {"account": TEST_ACCOUNT, "status": "success"}),
        ("POST", f"/{TEST_LICENSE_KEY}/api/ea/register", {"account": TEST_ACCOUNT, "broker": "Test"}),
        ("GET", f"/{TEST_LICENSE_KEY}/api/ea/get_copy_pairs?account={TEST_ACCOUNT}", None),
        ("GET", f"/{TEST_LICENSE_KEY}/api/ea/status", None),

        # Broker API endpoints
        ("POST", f"/{TEST_LICENSE_KEY}/api/broker/register", {"account": TEST_ACCOUNT, "broker": "Test"}),

        # Commands API endpoints
        ("GET", f"/{TEST_LICENSE_KEY}/api/commands/{TEST_ACCOUNT}", None),
        ("POST", f"/{TEST_LICENSE_KEY}/api/commands/{TEST_ACCOUNT}/ack", {"command_id": "test", "status": "success"}),

        # Balance API endpoints
        ("GET", f"/{TEST_LICENSE_KEY}/api/balance/need-update/{TEST_ACCOUNT}", None),
        ("POST", f"/{TEST_LICENSE_KEY}/api/account/balance", {"account": TEST_ACCOUNT, "balance": 10000}),
        ("GET", f"/{TEST_LICENSE_KEY}/api/account/{TEST_ACCOUNT}/balance", None),
    ]

    for method, path, data in routes:
        result = test_route(method, path, data)
        results.append(result)

    print("=" * 60)
    success = sum(results)
    total = len(results)
    print(f"Results: {success}/{total} routes responding")

    if success == 0:
        print("\n⚠️  Server may not be running. Start with: python server.py")
    elif success < total:
        print("\n⚠️  Some routes failed. Check the logs for details.")
    else:
        print("\n✅ All routes are responding!")

    return 0 if success == total else 1

if __name__ == "__main__":
    sys.exit(main())

