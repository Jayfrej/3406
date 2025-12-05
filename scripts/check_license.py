"""Check license keys in database"""
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'accounts.db')
print(f"DB Path: {db_path}")
print(f"Exists: {os.path.exists(db_path)}")

conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Get all tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cur.fetchall()
print(f"\nTables: {[t[0] for t in tables]}")

# Check users table
print("\n=== USERS TABLE ===")
cur.execute("SELECT user_id, email, license_key, webhook_secret FROM users")
for row in cur.fetchall():
    print(f"User: {row[0]}")
    print(f"  Email: {row[1]}")
    print(f"  License: {row[2]}")
    print(f"  Secret: {row[3][:20] if row[3] else None}...")
    print()

# Check user_tokens table if exists
if ('user_tokens',) in tables:
    print("\n=== USER_TOKENS TABLE ===")
    cur.execute("SELECT * FROM user_tokens")
    for row in cur.fetchall():
        print(f"Token Row: {row}")

conn.close()

