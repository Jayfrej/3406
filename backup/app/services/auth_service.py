"""
Authentication Service
Handles user authentication logic
"""
import os
from dotenv import load_dotenv

load_dotenv()


class AuthService:
    """Service for handling authentication operations"""

    def __init__(self):
        self.basic_user = os.getenv('BASIC_USER', 'admin')
        self.basic_pass = os.getenv('BASIC_PASS', 'pass')

    def validate_credentials(self, username: str, password: str) -> bool:
        """
        Validate user credentials

        Args:
            username: Username to validate
            password: Password to validate

        Returns:
            bool: True if credentials are valid, False otherwise
        """
        return (username == self.basic_user and password == self.basic_pass)

