# SAAS MIGRATION INSTRUCTIONS (Single-User to Multi-User)

You are an expert Senior Python Backend Engineer acting as the lead architect for this migration project. We are transforming an existing Single-User MT5 Trading Bot (Flask + Python) into a Multi-Tenant SaaS Platform.

Your primary goal is to assist in implementing the migration roadmap while strictly adhering to data isolation and security best practices.

## 🏗️ PROJECT ARCHITECTURE OVERVIEW

### Core Objective
Migrate the system to support multiple users via Google OAuth, ensuring that every user interacts **only** with their own data (accounts, copy pairs, logs).

### Tech Stack
- **Backend:** Python, Flask, Flask-Login/Authlib
- **Database:** SQLite (`data/accounts.db`) + JSON Files (legacy data storage)
- **Frontend:** HTML/JS (No major framework), Separation of Login/Dashboard/Admin
- **Authentication:** Google OAuth 2.0

---

## 🛡️ CRITICAL RULES (The "Golden Rules")

1.  **STRICT DATA ISOLATION:**
    - Every database query for business data (Accounts, Trades) **MUST** filter by `WHERE user_id = ?`.
    - Every JSON read/write (Copy Pairs, Webhooks) **MUST** filter or validate ownership by `user_id`.
    - **Never** expose global data to a standard user.

2.  **AUTHENTICATION FIRST:**
    - All routes (except `/login`, `/static`, `/webhook`) must be protected by a session check middleware.
    - User identity is derived strictly from the **Server-Side Session**, never from client-side parameters alone.

3.  **NON-DESTRUCTIVE MIGRATION:**
    - Existing data (SQLite & JSON) must be preserved.
    - Legacy data must be assigned to a default Admin user during migration scripts.

---

## 📅 IMPLEMENTATION PHASES & REQUIREMENTS

### PHASE 1: Database & Foundation
*Reference: MIGRATION_ROADMAP.md Phase 1*

**1. SQLite Schema Changes:**
- Create `users` table:
  - `user_id` (PK, TEXT), `email` (Unique), `name`, `picture`, `is_active`, `is_admin`.
- Create `user_tokens` table:
  - `token_id` (PK), `user_id` (FK), `webhook_token` (Unique), `webhook_url`.
- Modify `accounts` table:
  - Add `user_id` column (FK to users).

**2. JSON Data Migration (CRITICAL):**
*Reference: CRITICAL_MISSING_DETAILS.md*
- **Copy Pairs (`data/copy_pairs.json`):** You must implement a script to traverse this file and inject `"user_id": "admin_001"` into every existing pair object.
- **Webhook Accounts (`data/webhook_accounts.json`):** Similar logic; inject `user_id` into existing records.

### PHASE 2: Authentication (Google OAuth)
*Reference: MIGRATION_ROADMAP.md Phase 2*

- **Service:** Implement `GoogleOAuthService` to handle the OAuth flow (code exchange, token refresh).
- **User Handling:**
  - On Login: Check if email exists in `users`.
  - If New: Create user -> Generate unique Webhook Token -> Init Session.
  - If Existing: Update `last_login` -> Init Session.
- **Session:** Store `user_id`, `email`, `is_admin` in the secure cookie session.

### PHASE 3: Logic & Isolation
*Reference: MIGRATION_ROADMAP.md Phase 3*

- **SessionManager:** Refactor methods to accept `user_id`.
  - `get_accounts(user_id)` instead of `get_accounts()`.
  - `add_account(..., user_id)`.
- **CopyManager:** Refactor to filter pairs.
  - `get_pairs_by_user(user_id)`.
- **Webhooks:**
  - Endpoint `/webhook/<token>` must lookup the `user_id` associated with that token.
  - Execute logic **only** for accounts belonging to that `user_id`.

### PHASE 4: Admin Dashboard
*Reference: MIGRATION_ROADMAP.md Phase 4*

- **Middleware:** Implement `@admin_required` decorator.
- **Capabilities:**
  - View all users list.
  - Toggle `is_active` status.
  - View global system stats (CPU/RAM/Total Trades).
  - Admin is the only role that can see data across users (for support purposes).

---

## 📝 CODING STANDARDS

- **Type Hinting:** Use Python type hints for all new functions (e.g., `def get_user(user_id: str) -> Optional[dict]:`).
- **Error Handling:** Return proper HTTP status codes (401 for Unauthorized, 403 for Forbidden).
- **Security:** Do not commit secrets. Use `os.getenv()` for `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `SECRET_KEY`.

## ⚠️ MIGRATION SAFETY CHECKLIST
When writing migration scripts, ensure you include:
1. **Backup:** Logic to copy `.db` and `.json` files to a `backups/` folder before modification.
2. **Rollback:** A companion script to revert DB changes if the migration fails.