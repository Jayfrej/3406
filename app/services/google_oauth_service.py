"""
Google OAuth Service for Multi-User SaaS

Handles Google OAuth 2.0 flow:
- Generate authorization URL
- Exchange code for token
- Get user info from Google

Reference: MIGRATION_ROADMAP.md Phase 2.1
"""

import os
import logging
import secrets
from typing import Optional
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

# Optional: Try to import requests for HTTP calls
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    logger.warning("[GOOGLE_OAUTH] requests library not installed, OAuth will not work")


class GoogleOAuthService:
    """Service for Google OAuth 2.0 authentication."""

    # Google OAuth endpoints
    GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
    GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

    def __init__(self):
        self.client_id = os.getenv('GOOGLE_CLIENT_ID', '')
        self.client_secret = os.getenv('GOOGLE_CLIENT_SECRET', '')
        self.redirect_uri = os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:5000/auth/google/callback')

        if not self.client_id or not self.client_secret:
            logger.warning("[GOOGLE_OAUTH] Missing GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET")

    def is_configured(self) -> bool:
        """Check if OAuth is properly configured."""
        return bool(self.client_id and self.client_secret)

    def get_authorization_url(self, state: str = None) -> tuple:
        """
        Generate Google OAuth URL with CSRF protection.

        Per MIGRATION_ROADMAP.md Phase 2.1

        Args:
            state: CSRF state token (generated if not provided)

        Returns:
            tuple: (Authorization URL, state token)
        """
        if not state:
            state = secrets.token_urlsafe(32)

        params = {
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'response_type': 'code',
            'scope': 'openid email profile',
            'state': state,
            'access_type': 'offline',
            'prompt': 'select_account'
        }

        url = f"{self.GOOGLE_AUTH_URL}?{urlencode(params)}"
        logger.debug(f"[GOOGLE_OAUTH] Generated auth URL with state: {state[:10]}...")

        return url, state

    def exchange_code_for_token(self, code: str) -> dict:
        """
        Exchange auth code for access token.

        Per MIGRATION_ROADMAP.md Phase 2.1

        Args:
            code: Authorization code from Google callback

        Returns:
            dict: Token response with access_token, refresh_token, etc.
        """
        if not HAS_REQUESTS:
            raise RuntimeError("requests library required for OAuth")

        data = {
            'code': code,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'redirect_uri': self.redirect_uri,
            'grant_type': 'authorization_code'
        }

        try:
            response = requests.post(self.GOOGLE_TOKEN_URL, data=data, timeout=10)
            response.raise_for_status()

            token_data = response.json()
            logger.info("[GOOGLE_OAUTH] Successfully exchanged code for token")

            return token_data

        except requests.RequestException as e:
            logger.error(f"[GOOGLE_OAUTH] Token exchange failed: {e}")
            raise

    def get_user_info(self, access_token: str) -> dict:
        """
        Get user profile from Google.

        Per MIGRATION_ROADMAP.md Phase 2.1

        Args:
            access_token: OAuth access token

        Returns:
            dict: User info with email, name, picture
        """
        if not HAS_REQUESTS:
            raise RuntimeError("requests library required for OAuth")

        headers = {
            'Authorization': f'Bearer {access_token}'
        }

        try:
            response = requests.get(self.GOOGLE_USERINFO_URL, headers=headers, timeout=10)
            response.raise_for_status()

            user_info = response.json()
            logger.info(f"[GOOGLE_OAUTH] Got user info for: {user_info.get('email', 'unknown')}")

            return {
                'email': user_info.get('email', ''),
                'name': user_info.get('name', ''),
                'picture': user_info.get('picture', ''),
                'verified_email': user_info.get('verified_email', False),
                'id': user_info.get('id', '')
            }

        except requests.RequestException as e:
            logger.error(f"[GOOGLE_OAUTH] Failed to get user info: {e}")
            raise

    def refresh_access_token(self, refresh_token: str) -> dict:
        """
        Refresh expired token.

        Per MIGRATION_ROADMAP.md Phase 2.1

        Args:
            refresh_token: OAuth refresh token

        Returns:
            dict: New token response
        """
        if not HAS_REQUESTS:
            raise RuntimeError("requests library required for OAuth")

        data = {
            'refresh_token': refresh_token,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'refresh_token'
        }

        try:
            response = requests.post(self.GOOGLE_TOKEN_URL, data=data, timeout=10)
            response.raise_for_status()

            logger.info("[GOOGLE_OAUTH] Successfully refreshed access token")
            return response.json()

        except requests.RequestException as e:
            logger.error(f"[GOOGLE_OAUTH] Token refresh failed: {e}")
            raise

    def verify_state(self, state: str, stored_state: str) -> bool:
        """
        Verify CSRF state token.

        Args:
            state: State from callback
            stored_state: State stored in session

        Returns:
            bool: True if valid
        """
        return state == stored_state and bool(state)

