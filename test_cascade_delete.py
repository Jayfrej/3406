#!/usr/bin/env python3
"""
Test script สำหรับทดสอบ Cascade Delete
"""
import json
import os

# เพิ่ม path ให้สามารถ import modules ได้
import sys
sys.path.insert(0, '/home/user/3406')

from app.copy_trading.copy_manager import CopyManager
from app.copy_trading.copy_history import CopyHistory

print("=" * 80)
print("TEST: Cascade Delete for Account Deletion")
print("=" * 80)

# ===================== ก่อนลบ =====================
print("\n📊 BEFORE DELETE:")
print("-" * 80)

# 1. ตรวจสอบ Copy Pairs
print("\n1️⃣ Copy Pairs:")
copy_manager = CopyManager()
all_pairs = copy_manager.get_all_pairs()
print(f"   Total pairs: {len(all_pairs)}")
for pair in all_pairs:
    print(f"   - ID: {pair['id']}, Master: {pair['master_account']}, Slave: {pair['slave_account']}")

# 2. ตรวจสอบ Copy History
print("\n2️⃣ Copy History:")
copy_history = CopyHistory()
all_history = copy_history.get_history(limit=1000)
print(f"   Total history events: {len(all_history)}")
for event in all_history:
    print(f"   - ID: {event['id']}, Master: {event['master']}, Slave: {event['slave']}, Action: {event['action']}")

# 3. ตรวจสอบ API Keys
print("\n3️⃣ API Keys:")
print(f"   Total API keys: {len(copy_manager.api_keys)}")
for key, value in copy_manager.api_keys.items():
    print(f"   - {key}: {value}")

# ===================== ทดสอบการลบ Account 12345 =====================
print("\n" + "=" * 80)
print("🗑️  DELETING ACCOUNT: 12345")
print("=" * 80)

account_to_delete = "12345"

print(f"\n⚙️  Account '{account_to_delete}' is used as:")
pairs_as_master = copy_manager.get_pairs_by_master(account_to_delete)
pairs_as_slave = copy_manager.get_pairs_by_slave(account_to_delete)
print(f"   - Master in {len(pairs_as_master)} pair(s)")
print(f"   - Slave in {len(pairs_as_slave)} pair(s)")

# ลบ Pairs
print(f"\n🔥 Calling: copy_manager.delete_pairs_by_account('{account_to_delete}')")
deleted_pairs = copy_manager.delete_pairs_by_account(account_to_delete)
print(f"   ✅ Deleted {deleted_pairs} pair(s)")

# ลบ History
print(f"\n🔥 Calling: copy_history.delete_by_account('{account_to_delete}')")
deleted_history = copy_history.delete_by_account(account_to_delete)
print(f"   ✅ Deleted {deleted_history} history event(s)")

# ===================== หลังลบ =====================
print("\n" + "=" * 80)
print("📊 AFTER DELETE:")
print("-" * 80)

# Reload data
copy_manager_after = CopyManager()
copy_history_after = CopyHistory()

# 1. ตรวจสอบ Copy Pairs
print("\n1️⃣ Copy Pairs:")
all_pairs_after = copy_manager_after.get_all_pairs()
print(f"   Total pairs: {len(all_pairs_after)}")
for pair in all_pairs_after:
    print(f"   - ID: {pair['id']}, Master: {pair['master_account']}, Slave: {pair['slave_account']}")

# 2. ตรวจสอบ Copy History
print("\n2️⃣ Copy History:")
all_history_after = copy_history_after.get_history(limit=1000)
print(f"   Total history events: {len(all_history_after)}")
for event in all_history_after:
    print(f"   - ID: {event['id']}, Master: {event['master']}, Slave: {event['slave']}, Action: {event['action']}")

# 3. ตรวจสอบ API Keys
print("\n3️⃣ API Keys:")
print(f"   Total API keys: {len(copy_manager_after.api_keys)}")
for key, value in copy_manager_after.api_keys.items():
    print(f"   - {key}: {value}")

# ===================== สรุปผล =====================
print("\n" + "=" * 80)
print("📋 SUMMARY:")
print("=" * 80)

print(f"\n✅ Cascade Delete Results for Account '{account_to_delete}':")
print(f"   - Pairs deleted: {deleted_pairs} (Before: {len(all_pairs)} → After: {len(all_pairs_after)})")
print(f"   - History deleted: {deleted_history} (Before: {len(all_history)} → After: {len(all_history_after)})")
print(f"   - API Keys cleaned: {len(copy_manager.api_keys) - len(copy_manager_after.api_keys)}")

# ตรวจสอบว่ายังมีข้อมูลของ account 12345 หลงเหลืออยู่หรือไม่
orphan_pairs = [p for p in all_pairs_after if p['master_account'] == account_to_delete or p['slave_account'] == account_to_delete]
orphan_history = [e for e in all_history_after if e['master'] == account_to_delete or e['slave'] == account_to_delete]

print(f"\n🔍 Orphan Data Check (ข้อมูลขยะที่เหลือ):")
if orphan_pairs:
    print(f"   ❌ Found {len(orphan_pairs)} orphan pair(s)!")
    for pair in orphan_pairs:
        print(f"      - {pair['id']}: Master={pair['master_account']}, Slave={pair['slave_account']}")
else:
    print(f"   ✅ No orphan pairs found")

if orphan_history:
    print(f"   ❌ Found {len(orphan_history)} orphan history event(s)!")
    for event in orphan_history:
        print(f"      - {event['id']}: Master={event['master']}, Slave={event['slave']}")
else:
    print(f"   ✅ No orphan history found")

# Final verdict
print("\n" + "=" * 80)
if not orphan_pairs and not orphan_history:
    print("🎉 SUCCESS: Cascade Delete ทำงานถูกต้อง! ไม่มีข้อมูลขยะหลงเหลือ")
else:
    print("⚠️  WARNING: Cascade Delete มีปัญหา! พบข้อมูลขยะหลงเหลือ")
print("=" * 80)
