"""
Command Queue Manager - สำหรับเก็บคำสั่งการเทรดที่รอ EA มา poll

เปลี่ยนจากการเขียนไฟล์เป็นการเก็บใน memory queue
EA จะ poll คำสั่งผ่าน REST API แทน
"""

import logging
import time
import threading
from typing import Dict, List, Optional
from datetime import datetime
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


class CommandQueue:
    """
    จัดการ Queue ของคำสั่งการเทรดสำหรับแต่ละ Account

    Features:
    - Thread-safe operations
    - Auto-cleanup คำสั่งเก่า
    - Support acknowledgment
    - Statistics tracking
    """

    def __init__(self, max_queue_size: int = 1000, max_age_seconds: int = 300):
        """
        Args:
            max_queue_size: จำนวนคำสั่งสูงสุดต่อ account
            max_age_seconds: อายุคำสั่งสูงสุด (วินาที) ก่อนจะถูกลบ
        """
        self.max_queue_size = max_queue_size
        self.max_age_seconds = max_age_seconds

        # Queue สำหรับแต่ละ account: {account: deque([command, ...])}
        self._queues: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_queue_size))

        # Lock สำหรับ thread safety
        self._locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)

        # Statistics
        self._stats = {
            'total_commands_added': 0,
            'total_commands_retrieved': 0,
            'total_commands_expired': 0,
            'total_commands_acknowledged': 0
        }

        # Start cleanup thread
        self._cleanup_thread = threading.Thread(target=self._cleanup_worker, daemon=True)
        self._cleanup_thread.start()

        logger.info(f"[COMMAND_QUEUE] Initialized (max_queue_size={max_queue_size}, max_age={max_age_seconds}s)")

    def add_command(self, account: str, command: Dict) -> bool:
        """
        เพิ่มคำสั่งใหม่เข้า queue

        Args:
            account: หมายเลขบัญชี
            command: คำสั่งการเทรด (dict)

        Returns:
            bool: True ถ้าสำเร็จ
        """
        try:
            account = str(account).strip()

            # เพิ่ม metadata
            enriched_command = {
                **command,
                'queue_id': f"{account}_{int(time.time() * 1000)}_{id(command)}",
                'queue_timestamp': datetime.now().isoformat(),
                'queue_added_at': time.time(),
                'acknowledged': False
            }

            with self._locks[account]:
                self._queues[account].append(enriched_command)
                self._stats['total_commands_added'] += 1

            logger.info(
                f"[COMMAND_QUEUE] ✅ Added command for {account}: "
                f"{command.get('action')} {command.get('symbol')} "
                f"(queue_id={enriched_command['queue_id']})"
            )

            return True

        except Exception as e:
            logger.error(f"[COMMAND_QUEUE] ❌ Failed to add command for {account}: {e}", exc_info=True)
            return False

    def get_pending_commands(self, account: str, limit: int = 10) -> List[Dict]:
        """
        ดึงคำสั่งที่รออยู่สำหรับ account นี้

        Args:
            account: หมายเลขบัญชี
            limit: จำนวนคำสั่งสูงสุดที่จะดึง

        Returns:
            List[Dict]: รายการคำสั่งที่รออยู่
        """
        try:
            account = str(account).strip()

            with self._locks[account]:
                # ดึงคำสั่งที่ยังไม่ acknowledged
                pending = [
                    cmd for cmd in self._queues[account]
                    if not cmd.get('acknowledged', False)
                ]

                # จำกัดจำนวน
                result = pending[:limit]

                # Update stats
                if result:
                    self._stats['total_commands_retrieved'] += len(result)
                    logger.info(f"[COMMAND_QUEUE] 📤 Retrieved {len(result)} command(s) for {account}")

                return result

        except Exception as e:
            logger.error(f"[COMMAND_QUEUE] ❌ Failed to get commands for {account}: {e}")
            return []

    def acknowledge_command(self, account: str, queue_id: str) -> bool:
        """
        แจ้งว่าประมวลผลคำสั่งเสร็จแล้ว

        Args:
            account: หมายเลขบัญชี
            queue_id: ID ของคำสั่ง

        Returns:
            bool: True ถ้าพบและ acknowledge สำเร็จ
        """
        try:
            account = str(account).strip()

            with self._locks[account]:
                for cmd in self._queues[account]:
                    if cmd.get('queue_id') == queue_id:
                        cmd['acknowledged'] = True
                        cmd['acknowledged_at'] = time.time()
                        self._stats['total_commands_acknowledged'] += 1

                        logger.info(f"[COMMAND_QUEUE] ✅ Acknowledged: {queue_id}")
                        return True

                logger.warning(f"[COMMAND_QUEUE] ⚠️ Command not found: {queue_id}")
                return False

        except Exception as e:
            logger.error(f"[COMMAND_QUEUE] ❌ Failed to acknowledge {queue_id}: {e}")
            return False

    def get_queue_size(self, account: str) -> int:
        """
        ดึงจำนวนคำสั่งที่รออยู่

        Args:
            account: หมายเลขบัญชี

        Returns:
            int: จำนวนคำสั่ง
        """
        try:
            account = str(account).strip()

            with self._locks[account]:
                pending = sum(1 for cmd in self._queues[account] if not cmd.get('acknowledged', False))
                return pending

        except Exception as e:
            logger.error(f"[COMMAND_QUEUE] Error getting queue size for {account}: {e}")
            return 0

    def clear_queue(self, account: str) -> int:
        """
        ล้างคำสั่งทั้งหมดของ account

        Args:
            account: หมายเลขบัญชี

        Returns:
            int: จำนวนคำสั่งที่ลบ
        """
        try:
            account = str(account).strip()

            with self._locks[account]:
                count = len(self._queues[account])
                self._queues[account].clear()

                logger.info(f"[COMMAND_QUEUE] 🗑️ Cleared {count} command(s) for {account}")
                return count

        except Exception as e:
            logger.error(f"[COMMAND_QUEUE] Error clearing queue for {account}: {e}")
            return 0

    def get_all_queues_status(self) -> Dict:
        """
        ดึงสถานะของ queue ทั้งหมด

        Returns:
            Dict: สถานะ queue แต่ละ account
        """
        try:
            status = {
                'accounts': {},
                'total_accounts': 0,
                'total_pending': 0,
                'stats': self._stats.copy()
            }

            for account in list(self._queues.keys()):
                with self._locks[account]:
                    total = len(self._queues[account])
                    pending = sum(1 for cmd in self._queues[account] if not cmd.get('acknowledged', False))
                    acknowledged = total - pending

                    status['accounts'][account] = {
                        'total': total,
                        'pending': pending,
                        'acknowledged': acknowledged
                    }

                    status['total_pending'] += pending

            status['total_accounts'] = len(status['accounts'])

            return status

        except Exception as e:
            logger.error(f"[COMMAND_QUEUE] Error getting status: {e}")
            return {'error': str(e)}

    def _cleanup_worker(self):
        """
        Background worker สำหรับลบคำสั่งเก่า
        """
        while True:
            try:
                time.sleep(60)  # ทำงานทุก 1 นาที
                self._cleanup_old_commands()

            except Exception as e:
                logger.error(f"[COMMAND_QUEUE] Cleanup worker error: {e}")

    def _cleanup_old_commands(self):
        """
        ลบคำสั่งที่เก่าเกินกำหนด
        """
        try:
            current_time = time.time()
            total_cleaned = 0

            for account in list(self._queues.keys()):
                with self._locks[account]:
                    original_size = len(self._queues[account])

                    # กรองเฉพาะคำสั่งที่ยังไม่หมดอายุ
                    self._queues[account] = deque(
                        (cmd for cmd in self._queues[account]
                         if (current_time - cmd.get('queue_added_at', 0)) < self.max_age_seconds),
                        maxlen=self.max_queue_size
                    )

                    cleaned = original_size - len(self._queues[account])
                    if cleaned > 0:
                        total_cleaned += cleaned
                        logger.info(f"[COMMAND_QUEUE] 🗑️ Cleaned {cleaned} old command(s) for {account}")

            if total_cleaned > 0:
                self._stats['total_commands_expired'] += total_cleaned
                logger.info(f"[COMMAND_QUEUE] 🗑️ Total cleanup: {total_cleaned} command(s)")

        except Exception as e:
            logger.error(f"[COMMAND_QUEUE] Cleanup error: {e}")


# Global instance
command_queue = CommandQueue()


# =================== Testing Functions ===================

def test_command_queue():
    """ทดสอบ CommandQueue"""
    print("\n" + "="*60)
    print("Testing CommandQueue")
    print("="*60)

    queue = CommandQueue(max_queue_size=100, max_age_seconds=300)

    # Test 1: Add commands
    print("\n1. Testing add_command...")
    test_account = "123456"

    for i in range(5):
        cmd = {
            'action': 'BUY',
            'symbol': 'BTCUSD',
            'volume': 0.01 * (i + 1),
            'order_type': 'market'
        }
        success = queue.add_command(test_account, cmd)
        print(f"  Added command {i+1}: {success}")

    # Test 2: Get pending commands
    print("\n2. Testing get_pending_commands...")
    pending = queue.get_pending_commands(test_account)
    print(f"  Pending commands: {len(pending)}")
    for cmd in pending:
        print(f"    - {cmd['action']} {cmd['symbol']} {cmd['volume']} (ID: {cmd['queue_id']})")

    # Test 3: Acknowledge command
    print("\n3. Testing acknowledge_command...")
    if pending:
        first_id = pending[0]['queue_id']
        success = queue.acknowledge_command(test_account, first_id)
        print(f"  Acknowledged {first_id}: {success}")

    # Test 4: Get queue size
    print("\n4. Testing get_queue_size...")
    size = queue.get_queue_size(test_account)
    print(f"  Queue size: {size}")

    # Test 5: Get status
    print("\n5. Testing get_all_queues_status...")
    status = queue.get_all_queues_status()
    print(f"  Total accounts: {status['total_accounts']}")
    print(f"  Total pending: {status['total_pending']}")
    print(f"  Stats: {status['stats']}")

    # Test 6: Clear queue
    print("\n6. Testing clear_queue...")
    cleared = queue.clear_queue(test_account)
    print(f"  Cleared: {cleared} commands")

    print("\n" + "="*60)
    print("Testing completed!")
    print("="*60 + "\n")


if __name__ == '__main__':
    # ตั้งค่า logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )

    # รันการทดสอบ
    test_command_queue()
