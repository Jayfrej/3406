"""
SSE Service - Server-Sent Events Broadcasting
"""
import logging

logger = logging.getLogger(__name__)


def broadcast_account_deleted(account: str, deleted_pairs_count: int = 0):
    """
    Broadcast account deletion event to all connected SSE clients

    Args:
        account: Account number that was deleted
        deleted_pairs_count: Number of pairs that were deleted
    """
    try:
        # ✅ Import inside function to avoid circular import
        from app.routes.system_routes import broadcast_to_sse_clients

        event_data = {
            'type': 'account_deleted',
            'account': account,
            'deleted_pairs': deleted_pairs_count,
            'timestamp': __import__('datetime').datetime.now().isoformat()
        }

        broadcast_to_sse_clients(event_data, event_type='account_deleted')
        logger.info(f"[SSE_SERVICE] Broadcasted account_deleted event for {account}")

    except ImportError:
        logger.warning("[SSE_SERVICE] Could not import broadcast function")
    except Exception as e:
        logger.error(f"[SSE_SERVICE] Failed to broadcast: {e}")


def broadcast_pair_deleted(pair_id: str, master_account: str = None, slave_account: str = None):
    """
    Broadcast copy pair deletion event

    Args:
        pair_id: Pair ID that was deleted
        master_account: Master account (optional)
        slave_account: Slave account (optional)
    """
    try:
        # ✅ Import inside function to avoid circular import
        from app.routes.system_routes import broadcast_to_sse_clients

        event_data = {
            'type': 'pair_deleted',
            'pair_id': pair_id,
            'master_account': master_account,
            'slave_account': slave_account,
            'timestamp': __import__('datetime').datetime.now().isoformat()
        }

        broadcast_to_sse_clients(event_data, event_type='pair_deleted')
        logger.info(f"[SSE_SERVICE] Broadcasted pair_deleted event for {pair_id}")

    except ImportError:
        logger.warning("[SSE_SERVICE] Could not import broadcast function")
    except Exception as e:
        logger.error(f"[SSE_SERVICE] Failed to broadcast: {e}")

