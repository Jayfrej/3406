"""
Account Allowlist Service
Manages webhook account allowlist (whitelist) for webhook access control

Updated for Multi-User SaaS: All operations now filter by user_id
"""
import os
import json
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class AccountAllowlistService:
    """Service for managing webhook account allowlist with multi-user support"""

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

    def get_webhook_allowlist(self, user_id: Optional[str] = None) -> List[Dict]:
        """
        Get webhook account allowlist filtered by user_id

        Args:
            user_id: User ID to filter by (None returns all for admin/legacy)

        Returns:
            list: List of allowed accounts [{"account":"111", "nickname":"A", "enabled": true, "user_id": "..."}, ...]
        """
        lst = self._load_json(self.webhook_accounts_file, [])
        out = []
        for it in lst:
            acc = str(it.get("account") or it.get("id") or "").strip()
            if acc:
                item_user_id = it.get("user_id")

                # Filter by user_id if provided
                if user_id and item_user_id and item_user_id != user_id:
                    continue

                out.append({
                    "account": acc,
                    "nickname": it.get("nickname", ""),
                    "enabled": bool(it.get("enabled", True)),
                    "user_id": item_user_id
                })
        return out

    def get_webhook_allowlist_by_user(self, user_id: str) -> List[Dict]:
        """
        Get webhook account allowlist for specific user only

        Args:
            user_id: User ID to filter by

        Returns:
            list: List of allowed accounts belonging to the user
        """
        return self.get_webhook_allowlist(user_id=user_id)

    def is_account_allowed_for_webhook(self, account: str, user_id: Optional[str] = None) -> bool:
        """
        Check if account is allowed to receive webhook signals

        Args:
            account: Account number to check
            user_id: Optional user ID to verify ownership

        Returns:
            bool: True if account is in allowlist and enabled
        """
        account = str(account).strip()
        for it in self.get_webhook_allowlist():
            if it["account"] == account and it.get("enabled", True):
                # If user_id is provided, also check ownership
                if user_id and it.get("user_id") and it.get("user_id") != user_id:
                    continue
                return True
        return False

    def add_webhook_account(self, account: str, nickname: str = "", enabled: bool = True, user_id: Optional[str] = None) -> bool:
        """
        Add or update account in webhook allowlist

        Args:
            account: Account number
            nickname: Account nickname
            enabled: Whether account is enabled
            user_id: User ID who owns this account

        Returns:
            bool: True if added/updated successfully
        """
        lst = self._load_json(self.webhook_accounts_file, [])
        found = False

        for it in lst:
            if it.get("account") == account:
                # Only update if same user or no user set
                if user_id and it.get("user_id") and it.get("user_id") != user_id:
                    logger.warning(f"[ALLOWLIST] User {user_id} attempted to modify account {account} owned by {it.get('user_id')}")
                    return False
                it["nickname"] = nickname or it.get("nickname", "")
                it["enabled"] = enabled
                if user_id:
                    it["user_id"] = user_id
                found = True
                break

        if not found:
            lst.append({
                "account": account,
                "nickname": nickname,
                "enabled": enabled,
                "user_id": user_id
            })

        return self._save_json(self.webhook_accounts_file, lst)

    def delete_webhook_account(self, account: str, user_id: Optional[str] = None) -> bool:
        """
        Remove account from webhook allowlist

        Args:
            account: Account number to remove
            user_id: User ID requesting deletion (for ownership check)

        Returns:
            bool: True if removed successfully
        """
        lst = self._load_json(self.webhook_accounts_file, [])
        new_lst = []

        for it in lst:
            if it.get("account") == str(account):
                # Check ownership before deletion
                if user_id and it.get("user_id") and it.get("user_id") != user_id:
                    logger.warning(f"[ALLOWLIST] User {user_id} attempted to delete account {account} owned by {it.get('user_id')}")
                    new_lst.append(it)  # Keep it - not allowed to delete
                # else: skip (delete)
            else:
                new_lst.append(it)

        return self._save_json(self.webhook_accounts_file, new_lst)

