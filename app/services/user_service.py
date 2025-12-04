"""
User Service for Multi-User SaaS

Handles user operations including:
- Create/update users from Google OAuth
- Get user by email/id
- User statistics
- Admin management

Reference: MIGRATION_ROADMAP.md Phase 2.2
"""

import os
import sqlite3
import secrets
import logging
from datetime import datetime
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)


class UserService:
    """Service for managing users in multi-tenant system."""
    
    def __init__(self):
        self.data_dir = os.path.join(os.getcwd(), "data")
        os.makedirs(self.data_dir, exist_ok=True)
        self.db_path = os.path.join(self.data_dir, "accounts.db")
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        return sqlite3.connect(self.db_path)
    
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
                
                cursor.execute("""
                    INSERT INTO users (user_id, email, name, picture, created_at, last_login, is_active, is_admin)
                    VALUES (?, ?, ?, ?, ?, ?, 1, ?)
                """, (user_id, email, name, picture, now, now, is_admin))
                conn.commit()
                
                logger.info(f"[USER_SERVICE] Created new user: {email} (admin: {is_admin})")
                
                return {
                    'user_id': user_id,
                    'email': email,
                    'name': name,
                    'picture': picture,
                    'is_active': True,
                    'is_admin': bool(is_admin),
                    'is_new': True
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

