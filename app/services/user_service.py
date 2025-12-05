"""
User Service for Multi-User SaaS

Handles user operations including:
- Create/update users from Google OAuth
- Get user by email/id/license_key
- License key management for unified webhook endpoint
- User statistics
- Admin management

Reference: MIGRATION_ROADMAP.md Phase 2.2
Updated: Domain + License Key unified endpoint system
"""

import os
import sqlite3
import secrets
import logging
from datetime import datetime
from typing import Optional, List

logger = logging.getLogger(__name__)


class UserService:
    """Service for managing users in multi-tenant system."""
    
    def __init__(self):
        self.data_dir = os.path.join(os.getcwd(), "data")
        os.makedirs(self.data_dir, exist_ok=True)
        self.db_path = os.path.join(self.data_dir, "accounts.db")
        self._ensure_columns()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        return sqlite3.connect(self.db_path)
    
    def _ensure_columns(self):
        """Ensure license_key and webhook_secret columns exist in users table."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Check if users table exists first
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            if not cursor.fetchone():
                # Table doesn't exist yet - will be created by database_init
                conn.close()
                return

            # Check existing columns
            cursor.execute("PRAGMA table_info(users)")
            columns = [col[1] for col in cursor.fetchall()]

            # Add license_key column if missing
            # Note: SQLite cannot add UNIQUE column to table with existing data
            # So we add without UNIQUE constraint, uniqueness enforced at insert time
            if 'license_key' not in columns:
                try:
                    cursor.execute('ALTER TABLE users ADD COLUMN license_key TEXT')
                    conn.commit()
                    logger.info("[USER_SERVICE] Added 'license_key' column to users table")
                except sqlite3.OperationalError as e:
                    if 'duplicate column name' not in str(e).lower():
                        logger.warning(f"[USER_SERVICE] Could not add license_key column: {e}")

            # Add webhook_secret column if missing
            if 'webhook_secret' not in columns:
                try:
                    cursor.execute('ALTER TABLE users ADD COLUMN webhook_secret TEXT')
                    conn.commit()
                    logger.info("[USER_SERVICE] Added 'webhook_secret' column to users table")
                except sqlite3.OperationalError as e:
                    if 'duplicate column name' not in str(e).lower():
                        logger.warning(f"[USER_SERVICE] Could not add webhook_secret column: {e}")

            # Generate license keys and secrets for existing users
            cursor.execute("SELECT user_id FROM users WHERE license_key IS NULL OR webhook_secret IS NULL")
            users = cursor.fetchall()
            for (user_id,) in users:
                # Check what's missing for this user
                cursor.execute("SELECT license_key, webhook_secret FROM users WHERE user_id = ?", (user_id,))
                row = cursor.fetchone()

                updates = []
                params = []

                if not row[0]:  # license_key is NULL
                    updates.append("license_key = ?")
                    params.append(self.generate_license_key())

                if not row[1]:  # webhook_secret is NULL
                    updates.append("webhook_secret = ?")
                    params.append(self.generate_webhook_secret())

                if updates:
                    params.append(user_id)
                    cursor.execute(f"UPDATE users SET {', '.join(updates)} WHERE user_id = ?", params)

            conn.commit()
            if users:
                logger.info(f"[USER_SERVICE] Generated license keys/secrets for {len(users)} existing users")

            conn.close()
        except Exception as e:
            logger.error(f"[USER_SERVICE] Error ensuring columns: {e}")

    def generate_license_key(self) -> str:
        """
        Generate unique license key for unified webhook endpoint.

        Format: whk_<24 random URL-safe characters>
        Example: whk_5jK8pQmN3vR2xL9wT4aH6D

        Returns:
            str: Unique license key
        """
        prefix = "whk_"
        random_part = secrets.token_urlsafe(18)[:24]
        return f"{prefix}{random_part}"

    def generate_webhook_secret(self) -> str:
        """
        Generate unique per-user webhook secret for request validation.

        Format: whs_<32 random URL-safe characters>
        Example: whs_5jK8pQmN3vR2xL9wT4aH6D7bY1cZ0

        Returns:
            str: Unique webhook secret
        """
        prefix = "whs_"
        random_part = secrets.token_urlsafe(24)[:32]
        return f"{prefix}{random_part}"

    def generate_user_id(self, email: str) -> str:
        """Generate unique user_id from email."""
        # Use email prefix + random suffix for uniqueness
        prefix = email.split('@')[0][:10]
        suffix = secrets.token_hex(4)
        return f"user_{prefix}_{suffix}"
    
    def create_or_update_user(self, google_data: dict) -> dict:
        """
        Create new user or update existing from Google OAuth data.
        
        Per MIGRATION_ROADMAP.md Phase 2.2
        
        Args:
            google_data: Dict with email, name, picture from Google
            
        Returns:
            dict: User data including user_id, email, name, is_admin, etc.
        """
        email = google_data.get('email', '').lower()
        name = google_data.get('name', '')
        picture = google_data.get('picture', '')
        
        if not email:
            raise ValueError("Email is required")
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Check if user exists
            cursor.execute(
                "SELECT user_id, email, name, picture, is_active, is_admin FROM users WHERE email = ?",
                (email,)
            )
            existing = cursor.fetchone()
            
            if existing:
                # Update existing user
                user_id = existing[0]
                cursor.execute("""
                    UPDATE users 
                    SET name = ?, picture = ?, last_login = ?
                    WHERE user_id = ?
                """, (name, picture, datetime.now().isoformat(), user_id))
                conn.commit()
                
                logger.info(f"[USER_SERVICE] Updated existing user: {email}")
                
                return {
                    'user_id': existing[0],
                    'email': existing[1],
                    'name': name or existing[2],
                    'picture': picture or existing[3],
                    'is_active': bool(existing[4]),
                    'is_admin': bool(existing[5]),
                    'is_new': False
                }
            else:
                # Create new user
                user_id = self.generate_user_id(email)
                now = datetime.now().isoformat()
                
                # Check if this is the admin email
                admin_email = os.getenv('ADMIN_EMAIL', '').lower()
                is_admin = 1 if email == admin_email else 0
                
                # Generate unique license key and webhook secret
                license_key = self.generate_license_key()
                webhook_secret = self.generate_webhook_secret()

                cursor.execute("""
                    INSERT INTO users (user_id, email, name, picture, created_at, last_login, is_active, is_admin, license_key, webhook_secret)
                    VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                """, (user_id, email, name, picture, now, now, is_admin, license_key, webhook_secret))
                conn.commit()
                
                logger.info(f"[USER_SERVICE] Created new user: {email} (admin: {is_admin})")
                logger.info(f"[USER_SERVICE] 🔑 License Key for {email}: {license_key}")
                logger.info(f"[USER_SERVICE] 🔐 Webhook Secret for {email}: {webhook_secret[:10]}...")

                return {
                    'user_id': user_id,
                    'email': email,
                    'name': name,
                    'picture': picture,
                    'is_active': True,
                    'is_admin': bool(is_admin),
                    'is_new': True,
                    'license_key': license_key,
                    'webhook_secret': webhook_secret
                }
                
        except sqlite3.Error as e:
            logger.error(f"[USER_SERVICE] Database error: {e}")
            raise
        finally:
            conn.close()
    
    def get_user_by_email(self, email: str) -> Optional[dict]:
        """
        Lookup user by email.
        
        Per MIGRATION_ROADMAP.md Phase 2.2
        
        Args:
            email: User email
            
        Returns:
            dict: User data or None if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT user_id, email, name, picture, created_at, last_login, is_active, is_admin
                FROM users 
                WHERE email = ?
            """, (email.lower(),))
            
            row = cursor.fetchone()
            if row:
                return {
                    'user_id': row[0],
                    'email': row[1],
                    'name': row[2],
                    'picture': row[3],
                    'created_at': row[4],
                    'last_login': row[5],
                    'is_active': bool(row[6]),
                    'is_admin': bool(row[7])
                }
            return None
            
        finally:
            conn.close()
    
    def get_user_by_id(self, user_id: str) -> Optional[dict]:
        """
        Lookup user by user_id.
        
        Args:
            user_id: User ID
            
        Returns:
            dict: User data or None if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT user_id, email, name, picture, created_at, last_login, is_active, is_admin
                FROM users 
                WHERE user_id = ?
            """, (user_id,))
            
            row = cursor.fetchone()
            if row:
                return {
                    'user_id': row[0],
                    'email': row[1],
                    'name': row[2],
                    'picture': row[3],
                    'created_at': row[4],
                    'last_login': row[5],
                    'is_active': bool(row[6]),
                    'is_admin': bool(row[7])
                }
            return None
            
        finally:
            conn.close()
    
    def update_last_login(self, user_id: str) -> bool:
        """
        Update last login timestamp.
        
        Per MIGRATION_ROADMAP.md Phase 2.2
        
        Args:
            user_id: User ID
            
        Returns:
            bool: True if updated
        """
        conn = self._get_connection()
        
        try:
            conn.execute(
                "UPDATE users SET last_login = ? WHERE user_id = ?",
                (datetime.now().isoformat(), user_id)
            )
            conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error(f"[USER_SERVICE] Error updating last_login: {e}")
            return False
        finally:
            conn.close()
    
    def toggle_user_status(self, user_id: str) -> bool:
        """
        Enable/disable user (admin function).
        
        Per MIGRATION_ROADMAP.md Phase 2.2
        
        Args:
            user_id: User ID to toggle
            
        Returns:
            bool: True if toggled
        """
        conn = self._get_connection()
        
        try:
            conn.execute("""
                UPDATE users 
                SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END
                WHERE user_id = ?
            """, (user_id,))
            conn.commit()
            logger.info(f"[USER_SERVICE] Toggled user status: {user_id}")
            return True
        except sqlite3.Error as e:
            logger.error(f"[USER_SERVICE] Error toggling user: {e}")
            return False
        finally:
            conn.close()
    
    def get_user_stats(self, user_id: str) -> dict:
        """
        Get user's account/pair/trade counts.
        
        Per MIGRATION_ROADMAP.md Phase 2.2
        
        Args:
            user_id: User ID
            
        Returns:
            dict: Statistics
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Count accounts
            cursor.execute(
                "SELECT COUNT(*) FROM accounts WHERE user_id = ?",
                (user_id,)
            )
            accounts_count = cursor.fetchone()[0]
            
            # Count pairs (from JSON, approximate)
            pairs_count = 0
            try:
                import json
                pairs_file = os.path.join(self.data_dir, "copy_pairs.json")
                if os.path.exists(pairs_file):
                    with open(pairs_file, 'r', encoding='utf-8') as f:
                        pairs = json.load(f)
                    pairs_count = len([p for p in pairs if p.get('user_id') == user_id])
            except:
                pass
            
            return {
                'accounts_count': accounts_count,
                'pairs_count': pairs_count,
                'trades_count': 0  # TODO: Implement when trades tracking is added
            }
            
        finally:
            conn.close()
    
    def list_all_users(self) -> List[dict]:
        """
        List all users (admin function).
        
        Returns:
            List of user dictionaries
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT user_id, email, name, picture, created_at, last_login, is_active, is_admin
                FROM users
                ORDER BY created_at DESC
            """)
            
            users = []
            for row in cursor.fetchall():
                users.append({
                    'user_id': row[0],
                    'email': row[1],
                    'name': row[2],
                    'picture': row[3],
                    'created_at': row[4],
                    'last_login': row[5],
                    'is_active': bool(row[6]),
                    'is_admin': bool(row[7])
                })
            
            return users
            
        finally:
            conn.close()
    
    def count_users(self) -> int:
        """Count total users."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT COUNT(*) FROM users")
            return cursor.fetchone()[0]
        finally:
            conn.close()
    
    def count_active_users(self) -> int:
        """Count active users."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT COUNT(*) FROM users WHERE is_active = 1")
            return cursor.fetchone()[0]
        finally:
            conn.close()

    def get_first_admin(self) -> Optional[dict]:
        """
        Get the first admin user from the database.

        Used for legacy session fallback when admin_001 might not exist.

        Returns:
            dict: Admin user data or None if no admin exists
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT user_id, email, name, picture, created_at, last_login, is_active, is_admin
                FROM users 
                WHERE is_admin = 1 AND is_active = 1
                ORDER BY created_at ASC
                LIMIT 1
            """)

            row = cursor.fetchone()
            if row:
                return {
                    'user_id': row[0],
                    'email': row[1],
                    'name': row[2],
                    'picture': row[3],
                    'created_at': row[4],
                    'last_login': row[5],
                    'is_active': bool(row[6]),
                    'is_admin': bool(row[7])
                }
            return None

        finally:
            conn.close()

    # =================== License Key Methods ===================
    # For unified endpoint: https://domain.com/<license_key>

    def get_user_by_license_key(self, license_key: str) -> Optional[dict]:
        """
        Lookup user by license key (for unified webhook endpoint).

        Args:
            license_key: License key from URL path

        Returns:
            dict: User data or None if not found/inactive
        """
        if not license_key or len(license_key) < 10:
            return None

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT user_id, email, name, picture, created_at, last_login, 
                       is_active, is_admin, license_key
                FROM users 
                WHERE license_key = ? AND is_active = 1
            """, (license_key,))

            row = cursor.fetchone()
            if row:
                return {
                    'user_id': row[0],
                    'email': row[1],
                    'name': row[2],
                    'picture': row[3],
                    'created_at': row[4],
                    'last_login': row[5],
                    'is_active': bool(row[6]),
                    'is_admin': bool(row[7]),
                    'license_key': row[8]
                }
            return None

        finally:
            conn.close()

    def get_user_license_key(self, user_id: str) -> Optional[str]:
        """
        Get license key for a user.

        Args:
            user_id: User ID

        Returns:
            str: License key or None if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "SELECT license_key FROM users WHERE user_id = ?",
                (user_id,)
            )
            row = cursor.fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    def regenerate_license_key(self, user_id: str) -> Optional[str]:
        """
        Generate new license key for user (invalidates old key).

        Use when key is compromised or user wants to rotate.

        Args:
            user_id: User ID

        Returns:
            str: New license key or None if failed
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            new_key = self.generate_license_key()

            cursor.execute("""
                UPDATE users 
                SET license_key = ?
                WHERE user_id = ?
            """, (new_key, user_id))
            conn.commit()

            if cursor.rowcount > 0:
                logger.info(f"[USER_SERVICE] Regenerated license key for user: {user_id}")
                return new_key
            return None

        except sqlite3.Error as e:
            logger.error(f"[USER_SERVICE] Error regenerating license key: {e}")
            return None
        finally:
            conn.close()

    def get_user_accounts_list(self, user_id: str) -> List[str]:
        """
        Get list of account numbers belonging to user.

        Args:
            user_id: User ID

        Returns:
            List[str]: List of account numbers
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "SELECT account FROM accounts WHERE user_id = ?",
                (user_id,)
            )
            return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_webhook_url(self, user_id: str) -> Optional[str]:
        """
        Get full webhook URL for user's license key.

        Args:
            user_id: User ID

        Returns:
            str: Full webhook URL or None
        """
        license_key = self.get_user_license_key(user_id)
        if license_key:
            base_url = os.getenv('EXTERNAL_BASE_URL', 'http://localhost:5000')
            return f"{base_url}/{license_key}"
        return None

    # =================== Per-User Webhook Secret Methods ===================
    # For request validation: License Key identifies user, Secret validates authenticity

    def get_user_webhook_secret(self, user_id: str) -> Optional[str]:
        """
        Get webhook secret for a user.

        Args:
            user_id: User ID

        Returns:
            str: Webhook secret or None if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "SELECT webhook_secret FROM users WHERE user_id = ?",
                (user_id,)
            )
            row = cursor.fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    def get_webhook_secret_by_license_key(self, license_key: str) -> Optional[str]:
        """
        Get webhook secret directly from license key (single query).

        Args:
            license_key: User's license key

        Returns:
            str: Webhook secret or None
        """
        if not license_key or len(license_key) < 10:
            return None

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "SELECT webhook_secret FROM users WHERE license_key = ? AND is_active = 1",
                (license_key,)
            )
            row = cursor.fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    def validate_webhook_secret(self, license_key: str, provided_secret: str) -> bool:
        """
        Validate that provided secret matches user's webhook secret.

        Args:
            license_key: User's license key from URL
            provided_secret: Secret provided in request

        Returns:
            bool: True if valid, False otherwise
        """
        if not provided_secret:
            return False

        expected_secret = self.get_webhook_secret_by_license_key(license_key)

        if not expected_secret:
            return False

        # Use constant-time comparison to prevent timing attacks
        return secrets.compare_digest(expected_secret, provided_secret)

    def regenerate_webhook_secret(self, user_id: str) -> Optional[str]:
        """
        Generate new webhook secret for user (invalidates old secret).

        Use when secret is compromised or user wants to rotate.

        Args:
            user_id: User ID

        Returns:
            str: New webhook secret or None if failed
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            new_secret = self.generate_webhook_secret()

            cursor.execute("""
                UPDATE users 
                SET webhook_secret = ?
                WHERE user_id = ?
            """, (new_secret, user_id))
            conn.commit()

            if cursor.rowcount > 0:
                logger.info(f"[USER_SERVICE] Regenerated webhook secret for user: {user_id}")
                return new_secret
            return None

        except sqlite3.Error as e:
            logger.error(f"[USER_SERVICE] Error regenerating webhook secret: {e}")
            return None
        finally:
            conn.close()

    def get_user_credentials(self, user_id: str) -> Optional[dict]:
        """
        Get user's license key and webhook secret together.

        Args:
            user_id: User ID

        Returns:
            dict: {license_key, webhook_secret, webhook_url} or None
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "SELECT license_key, webhook_secret FROM users WHERE user_id = ?",
                (user_id,)
            )
            row = cursor.fetchone()
            if row and row[0] and row[1]:
                base_url = os.getenv('EXTERNAL_BASE_URL', 'http://localhost:5000')
                return {
                    'license_key': row[0],
                    'webhook_secret': row[1],
                    'webhook_url': f"{base_url}/{row[0]}"
                }
            return None
        finally:
            conn.close()
