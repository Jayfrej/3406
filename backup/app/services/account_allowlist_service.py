"""
Account Allowlist Service
Manages webhook account allowlist (whitelist) for webhook access control
"""
import os
import json
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class AccountAllowlistService:
    """Service for managing webhook account allowlist"""

    def __init__(self, data_dir: str = 'data'):
        """
        Initialize Account Allowlist Service

        Args:
            data_dir: Directory for data storage
        """
        self.data_dir = data_dir
        self.webhook_accounts_file = os.path.join(data_dir, 'webhook_accounts.json')
        os.makedirs(data_dir, exist_ok=True)

    def _load_json(self, path: str, default: any) -> any:
        """
        Load JSON file safely

        Args:
            path: File path
            default: Default value if file doesn't exist or error occurs

        Returns:
            Loaded data or default
        """
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default

    def _save_json(self, path: str, obj: any) -> bool:
        """
        Save JSON file atomically

        Args:
            path: File path
            obj: Object to save

        Returns:
            bool: True if saved successfully
        """
        try:
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(obj, f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
            return True
        except Exception as e:
            logger.error(f"[ALLOWLIST] Error saving: {e}")
            return False

    def get_webhook_allowlist(self) -> List[Dict]:
        """
        Get webhook account allowlist

        Returns:
            list: List of allowed accounts [{"account":"111", "nickname":"A", "enabled": true}, ...]
        """
        lst = self._load_json(self.webhook_accounts_file, [])
        out = []
        for it in lst:
            acc = str(it.get("account") or it.get("id") or "").strip()
            if acc:
                out.append({
                    "account": acc,
                    "nickname": it.get("nickname", ""),
                    "enabled": bool(it.get("enabled", True)),
                })
        return out

    def is_account_allowed_for_webhook(self, account: str) -> bool:
        """
        Check if account is allowed to receive webhook signals

        Args:
            account: Account number to check

        Returns:
            bool: True if account is in allowlist and enabled
        """
        account = str(account).strip()
        for it in self.get_webhook_allowlist():
            if it["account"] == account and it.get("enabled", True):
                return True
        return False

    def add_webhook_account(self, account: str, nickname: str = "", enabled: bool = True) -> bool:
        """
        Add or update account in webhook allowlist

        Args:
            account: Account number
            nickname: Account nickname
            enabled: Whether account is enabled

        Returns:
            bool: True if added/updated successfully
        """
        lst = self.get_webhook_allowlist()
        found = False

        for it in lst:
            if it["account"] == account:
                it["nickname"] = nickname or it.get("nickname", "")
                it["enabled"] = enabled
                found = True
                break

        if not found:
            lst.append({"account": account, "nickname": nickname, "enabled": enabled})

        return self._save_json(self.webhook_accounts_file, lst)

    def delete_webhook_account(self, account: str) -> bool:
        """
        Remove account from webhook allowlist

        Args:
            account: Account number to remove

        Returns:
            bool: True if removed successfully
        """
        lst = [it for it in self.get_webhook_allowlist() if it["account"] != str(account)]
        return self._save_json(self.webhook_accounts_file, lst)

