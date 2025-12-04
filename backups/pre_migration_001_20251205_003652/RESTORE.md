# Migration 001 Backup
Created: 2025-12-05T00:36:52.090394

## Files Backed Up
- accounts.db
- JSON data files

## To Restore (Rollback)
```bash
python migrations/001_add_users_table.py --rollback C:\Users\usEr\PycharmProjects\3406\backups\pre_migration_001_20251205_003652
```

Or manually:
```bash
cp C:\Users\usEr\PycharmProjects\3406\backups\pre_migration_001_20251205_003652/accounts.db C:\Users\usEr\PycharmProjects\3406\data/
cp C:\Users\usEr\PycharmProjects\3406\backups\pre_migration_001_20251205_003652/*.json C:\Users\usEr\PycharmProjects\3406\data/
```
