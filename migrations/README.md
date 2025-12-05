# Migrations Folder

## ⚠️ LEGACY - ไม่ต้องใช้แล้ว!

ไฟล์ migration ใน `archive/` folder เป็น **legacy files** ที่ไม่จำเป็นต้องรันแยกอีกต่อไป

## ✅ ระบบปัจจุบัน (Built-in Migration)

Database migrations ถูก built-in เข้าไปใน:

1. **`setup.py`** → `run_database_migrations()` method
   - สร้าง tables ทั้งหมดอัตโนมัติตอนกด "Start Server"
   - Migrate JSON files อัตโนมัติ

2. **`app/core/database_init.py`** → `ensure_database_schema()` function
   - Safety net - ตรวจสอบและสร้าง tables ทุกครั้งที่ server start
   - ใช้ `CREATE TABLE IF NOT EXISTS` = ปลอดภัย รันกี่ครั้งก็ได้

## 📁 Archive Folder

ไฟล์เก่าถูกเก็บไว้ใน `archive/` สำหรับอ้างอิง:
- `001_add_users_table.py` - สร้าง users/user_tokens tables
- `002_migrate_copy_pairs_json.py` - เพิ่ม user_id ใน copy_pairs.json
- `003_migrate_webhook_accounts.py` - เพิ่ม user_id ใน webhook_accounts.json
- `rollback_001.py` - Rollback script (ไม่จำเป็นแล้ว)

## 🚀 วิธีใช้งาน

แค่รัน:
```bash
python setup.py
```

กรอกข้อมูล → กด "Start Server" → **เสร็จ!** ไม่ต้องทำอะไรเพิ่ม

