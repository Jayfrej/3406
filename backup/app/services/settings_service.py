"""
Settings Service
Handles application settings management
"""
from typing import Dict, Optional, List
from datetime import datetime
import logging
import json
import os

logger = logging.getLogger(__name__)

SETTINGS_FILE = 'data/settings.json'


class SettingsService:
    """Service for managing application settings"""

    def __init__(self):
        """Initialize settings service"""
        self.settings_file = SETTINGS_FILE
        os.makedirs('data', exist_ok=True)
        logger.info("[SETTINGS_SERVICE] Initialized")

    def load_settings(self) -> Dict:
        """
        Load settings from file

        Returns:
            dict: Settings dictionary
        """
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                logger.info("[SETTINGS] Settings loaded successfully")
                return settings
            else:
                # Return default settings if file doesn't exist
                return self._get_default_settings()
        except Exception as e:
            logger.error(f"[SETTINGS] Error loading settings: {e}")
            return self._get_default_settings()

    def save_settings(self, settings_data: Dict) -> bool:
        """
        Save settings to file

        Args:
            settings_data: Settings dictionary to save

        Returns:
            bool: True if saved successfully
        """
        try:
            os.makedirs('data', exist_ok=True)
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings_data, f, indent=2, ensure_ascii=False)
            logger.info("[SETTINGS] Settings saved successfully")
            return True
        except Exception as e:
            logger.error(f"[SETTINGS] Error saving settings: {e}")
            return False

    def _get_default_settings(self) -> Dict:
        """
        Get default settings structure

        Returns:
            dict: Default settings
        """
        return {
            'rate_limits': {
                'webhook': '10 per minute',
                'api': '100 per hour',
                'command_api': '10000 per hour',
                'last_updated': None
            },
            'email': {
                'enabled': False,
                'smtp_server': '',
                'smtp_port': 587,
                'smtp_user': '',
                'smtp_pass': '',
                'from_email': '',
                'to_emails': []
            }
        }

    def update_rate_limits(self, webhook: str, api: str, command_api: str) -> bool:
        """
        Update rate limit settings

        Args:
            webhook: Webhook rate limit string
            api: API rate limit string
            command_api: Command API rate limit string

        Returns:
            bool: True if updated successfully
        """
        settings = self.load_settings()
        settings['rate_limits'] = {
            'webhook': webhook,
            'api': api,
            'command_api': command_api,
            'last_updated': datetime.now().isoformat()
        }
        return self.save_settings(settings)

    def update_email_settings(self, enabled: bool, smtp_server: str, smtp_port: int,
                             smtp_user: str, smtp_pass: str, from_email: str,
                             to_emails: List[str]) -> bool:
        """
        Update email settings

        Args:
            enabled: Whether email notifications are enabled
            smtp_server: SMTP server address
            smtp_port: SMTP server port
            smtp_user: SMTP username
            smtp_pass: SMTP password
            from_email: From email address
            to_emails: List of recipient email addresses

        Returns:
            bool: True if updated successfully
        """
        settings = self.load_settings()

        # Preserve existing password if new password is masked or empty
        existing_email = settings.get('email', {})
        if smtp_pass == '********' or not smtp_pass:
            smtp_pass = existing_email.get('smtp_pass', '')

        settings['email'] = {
            'enabled': enabled,
            'smtp_server': smtp_server,
            'smtp_port': smtp_port,
            'smtp_user': smtp_user,
            'smtp_pass': smtp_pass,
            'from_email': from_email,
            'to_emails': to_emails
        }
        return self.save_settings(settings)

    def get_email_settings(self) -> Dict:
        """
        Get email settings (with password masked for security)

        Returns:
            dict: Email settings with masked password
        """
        settings = self.load_settings()
        email_settings = settings.get('email', {}).copy()

        # Mask password for security
        if 'smtp_pass' in email_settings:
            email_settings['smtp_pass'] = '********' if email_settings.get('smtp_pass') else ''

        return email_settings

