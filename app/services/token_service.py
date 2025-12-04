"""
Token Service for Multi-User SaaS

Handles per-user webhook token management:
- Generate unique webhook tokens
- Lookup user by token
- Rotate/revoke tokens

Reference: MIGRATION_ROADMAP.md Phase 2.3
"""

import os
import sqlite3
import secrets
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class TokenService:
    """Service for managing per-user webhook tokens."""

    def __init__(self):
        self.data_dir = os.path.join(os.getcwd(), "data")
        os.makedirs(self.data_dir, exist_ok=True)
        self.db_path = os.path.join(self.data_dir, "accounts.db")

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        return sqlite3.connect(self.db_path)

    def generate_webhook_token(self, user_id: str) -> str:
        """
        Generate unique webhook token for user.

        Per MIGRATION_ROADMAP.md Phase 2.3

        Args:
            user_id: User ID to generate token for

        Returns:
            str: Generated webhook token
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Check if user already has a token
            cursor.execute(
                "SELECT webhook_token FROM user_tokens WHERE user_id = ?",
                (user_id,)
            )
            existing = cursor.fetchone()

            if existing:
                return existing[0]

            # Generate new unique token
            while True:
                token = f"whk_{secrets.token_urlsafe(32)}"
                cursor.execute(
                    "SELECT 1 FROM user_tokens WHERE webhook_token = ?",
                    (token,)
                )
                if not cursor.fetchone():
                    break

            # Create token record
            token_id = f"tok_{secrets.token_urlsafe(16)}"
            now = datetime.now().isoformat()

            cursor.execute("""
                INSERT INTO user_tokens (token_id, user_id, webhook_token, created_at)
                VALUES (?, ?, ?, ?)
            """, (token_id, user_id, token, now))
            conn.commit()

            logger.info(f"[TOKEN_SERVICE] Generated webhook token for user: {user_id}")
            return token

        except sqlite3.Error as e:
            logger.error(f"[TOKEN_SERVICE] Error generating token: {e}")
            raise
        finally:
            conn.close()

    def get_user_by_webhook_token(self, token: str) -> Optional[str]:
        """
        Lookup user_id by webhook token.

        Per MIGRATION_ROADMAP.md Phase 2.3

        Args:
            token: Webhook token

        Returns:
            str: User ID or None if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "SELECT user_id FROM user_tokens WHERE webhook_token = ?",
                (token,)
            )
            row = cursor.fetchone()
            return row[0] if row else None

        finally:
            conn.close()

    def get_user_webhook_token(self, user_id: str) -> Optional[str]:
        """
        Get user's webhook token.

        Args:
            user_id: User ID

        Returns:
            str: Webhook token or None if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "SELECT webhook_token FROM user_tokens WHERE user_id = ?",
                (user_id,)
            )
            row = cursor.fetchone()
            return row[0] if row else None

        finally:
            conn.close()

    def rotate_token(self, user_id: str) -> str:
        """
        Generate new token, invalidate old.

        Per MIGRATION_ROADMAP.md Phase 2.3

        Args:
            user_id: User ID

        Returns:
            str: New webhook token
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Delete existing token
            cursor.execute(
                "DELETE FROM user_tokens WHERE user_id = ?",
                (user_id,)
            )
            conn.commit()

            logger.info(f"[TOKEN_SERVICE] Rotated token for user: {user_id}")

        finally:
            conn.close()

        # Generate new token
        return self.generate_webhook_token(user_id)

    def revoke_token(self, token: str) -> bool:
        """
        Invalidate token.

        Per MIGRATION_ROADMAP.md Phase 2.3

        Args:
            token: Webhook token to revoke

        Returns:
            bool: True if revoked
        """
        conn = self._get_connection()

        try:
            cursor = conn.execute(
                "DELETE FROM user_tokens WHERE webhook_token = ?",
                (token,)
            )
            conn.commit()

            if cursor.rowcount > 0:
                logger.info(f"[TOKEN_SERVICE] Revoked token: {token[:20]}...")
                return True
            return False

        except sqlite3.Error as e:
            logger.error(f"[TOKEN_SERVICE] Error revoking token: {e}")
            return False
        finally:
            conn.close()

    def get_webhook_url(self, user_id: str) -> Optional[str]:
        """
        Get full webhook URL for user.

        Args:
            user_id: User ID

        Returns:
            str: Full webhook URL or None
        """
        token = self.get_user_webhook_token(user_id)
        if not token:
            # Generate one if doesn't exist
            token = self.generate_webhook_token(user_id)

        base_url = os.getenv('EXTERNAL_BASE_URL', 'http://localhost:5000')
        return f"{base_url}/webhook/{token}"

    def validate_token(self, token: str) -> bool:
        """
        Check if token is valid (exists and not expired).

        Args:
            token: Webhook token

        Returns:
            bool: True if valid
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT user_id, expires_at 
                FROM user_tokens 
                WHERE webhook_token = ?
            """, (token,))

            row = cursor.fetchone()
            if not row:
                return False

            # Check expiration if set
            expires_at = row[1]
            if expires_at:
                try:
                    expiry = datetime.fromisoformat(expires_at)
                    if datetime.now() > expiry:
                        return False
                except:
                    pass

            return True

        finally:
            conn.close()

