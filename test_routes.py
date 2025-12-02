"""Quick test script to verify routes are working"""
from app.core.app_factory import create_app

app = create_app()

print("=" * 80)
print("UI ROUTES TEST")
print("=" * 80)

# Show UI routes
print("\n=== UI ROUTES ===")
for rule in app.url_map.iter_rules():
    if 'ui' in rule.endpoint or rule.rule == '/':
        methods = ','.join(sorted(rule.methods - {'HEAD', 'OPTIONS'}))
        print(f"{rule.endpoint:40} {rule.rule:50} [{methods}]")

# Test the root route
print("\n=== TESTING / ROUTE ===")
with app.test_client() as client:
    resp = client.get('/')
    print(f"Status Code: {resp.status_code}")
    print(f"Content-Type: {resp.content_type}")
    print(f"Content Length: {len(resp.data)} bytes")

    if resp.status_code == 200:
        print("✅ ROOT ROUTE WORKS!")
    else:
        print("❌ ROOT ROUTE RETURNS 404!")
        print(f"Response: {resp.data[:200]}")

# Test webhook-url
print("\n=== TESTING /webhook-url ROUTE ===")
with app.test_client() as client:
    resp = client.get('/webhook-url')
    print(f"Status Code: {resp.status_code}")
    print(f"Content-Type: {resp.content_type}")

    if resp.status_code == 200:
        print("✅ WEBHOOK-URL ROUTE WORKS!")
        print(f"Response: {resp.data.decode()}")
    else:
        print("❌ WEBHOOK-URL ROUTE FAILED!")

print("\n" + "=" * 80)

