import asyncio
import logging

logger = logging.getLogger(__name__)


async def run_notification_worker(poll_interval_sec: int = 5) -> None:
    """Каркас фонового воркера очереди уведомлений (логика отправки — в следующих задачах)."""
    logger.info("Notification worker started (interval=%ss)", poll_interval_sec)
    try:
        while True:
            await asyncio.sleep(poll_interval_sec)
    except asyncio.CancelledError:
        logger.info("Notification worker stopped")
        raise