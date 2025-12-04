#!/usr/bin/env python3
"""
Test script สำหรับทดสอบ Cascade Delete ผ่าน API endpoint
"""
import json
import sys
sys.path.insert(0, '/home/user/3406')

from app.copy_trading.copy_manager import CopyManager
from app.copy_trading.copy_history import CopyHistory
from pathlib import Path

print("=" * 80)
print("TEST: Cascade Delete via API Endpoint (Master Account)")
print("=" * 80)

# ===================== ก่อนลบ =====================
print("\n📊 BEFORE DELETE:")
print("-" * 80)

# 1. Master Accounts
master_file = Path('data/master_accounts.json')
if master_file.exists():
    with open(master_file, 'r') as f:
        masters = json.load(f)
    print(f"\n1️⃣ Master Accounts: {len(masters)}")
    for m in masters:
        print(f"   - ID: {m['id']}, Account: {m['account']}, Nickname: {m['nickname']}")
else:
    masters = []
    print("\n1️⃣ Master Accounts: 0 (file not found)")

# 2. Copy Pairs
copy_manager = CopyManager()
all_pairs = copy_manager.get_all_pairs()
print(f"\n2️⃣ Copy Pairs: {len(all_pairs)}")
for pair in all_pairs:
    print(f"   - ID: {pair['id']}, Master: {pair['master_account']}, Slave: {pair['slave_account']}")

# 3. Copy History
copy_history = CopyHistory()
all_history = copy_history.get_history(limit=1000)
print(f"\n3️⃣ Copy History: {len(all_history)}")
for event in all_history:
    print(f"   - ID: {event['id']}, Master: {event['master']}, Slave: {event['slave']}")

# ===================== จำลองการลบผ่าน API =====================
print("\n" + "=" * 80)
print("🗑️  SIMULATING DELETE /api/copy/master-accounts/master001")
print("=" * 80)

# หา account_number จาก master_accounts.json
account_id = "master001"
account_number = None
for m in masters:
    if m.get('id') == account_id or m.get('account') == account_id:
        account_number = m.get('account')
        break

print(f"\n⚙️  Found account_number: {account_number}")

# ลบจาก master_accounts.json
masters_after = [m for m in masters if m.get('id') != account_id and m.get('account') != account_id]
with open(master_file, 'w', encoding='utf-8') as f:
    json.dump(masters_after, f, indent=2, ensure_ascii=False)
print(f"✅ Removed from master_accounts.json")

# CASCADE DELETE: ลบ Pairs และ History
deleted_pairs = 0
deleted_history = 0

if account_number:
    deleted_pairs = copy_manager.delete_pairs_by_account(account_number)
    print(f"✅ Deleted {deleted_pairs} pair(s)")

    deleted_history = copy_history.delete_by_account(account_number)
    print(f"✅ Deleted {deleted_history} history event(s)")

# ===================== หลังลบ =====================
print("\n" + "=" * 80)
print("📊 AFTER DELETE:")
print("-" * 80)

# Reload
copy_manager_after = CopyManager()
copy_history_after = CopyHistory()

# 1. Master Accounts
if master_file.exists():
    with open(master_file, 'r') as f:
        masters_after = json.load(f)
    print(f"\n1️⃣ Master Accounts: {len(masters_after)}")
    for m in masters_after:
        print(f"   - ID: {m['id']}, Account: {m['account']}, Nickname: {m['nickname']}")
else:
    print("\n1️⃣ Master Accounts: 0")

# 2. Copy Pairs
all_pairs_after = copy_manager_after.get_all_pairs()
print(f"\n2️⃣ Copy Pairs: {len(all_pairs_after)}")
for pair in all_pairs_after:
    print(f"   - ID: {pair['id']}, Master: {pair['master_account']}, Slave: {pair['slave_account']}")

# 3. Copy History
all_history_after = copy_history_after.get_history(limit=1000)
print(f"\n3️⃣ Copy History: {len(all_history_after)}")
for event in all_history_after:
    print(f"   - ID: {event['id']}, Master: {event['master']}, Slave: {event['slave']}")

# ===================== สรุปผล =====================
print("\n" + "=" * 80)
print("📋 SUMMARY:")
print("=" * 80)

print(f"\n✅ Cascade Delete Results:")
print(f"   - Master Accounts: {len(masters)} → {len(masters_after)}")
print(f"   - Pairs deleted: {deleted_pairs} ({len(all_pairs)} → {len(all_pairs_after)})")
print(f"   - History deleted: {deleted_history} ({len(all_history)} → {len(all_history_after)})")

# ตรวจสอบข้อมูลขยะ
orphan_pairs = [p for p in all_pairs_after if p['master_account'] == account_number or p['slave_account'] == account_number]
orphan_history = [e for e in all_history_after if e['master'] == account_number or e['slave'] == account_number]

print(f"\n🔍 Orphan Data Check:")
if orphan_pairs:
    print(f"   ❌ Found {len(orphan_pairs)} orphan pair(s)!")
else:
    print(f"   ✅ No orphan pairs")

if orphan_history:
    print(f"   ❌ Found {len(orphan_history)} orphan history event(s)!")
else:
    print(f"   ✅ No orphan history")

print("\n" + "=" * 80)
if not orphan_pairs and not orphan_history:
    print("🎉 SUCCESS: Cascade Delete ทำงานถูกต้อง!")
else:
    print("⚠️  WARNING: มีข้อมูลขยะหลงเหลือ!")
print("=" * 80)
