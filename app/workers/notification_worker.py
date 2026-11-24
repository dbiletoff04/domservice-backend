import asyncio
import logging

from app.core.config import settings
from app.core.database import async_session_factory
from app.services.notification_service import process_notification_queue

logger = logging.getLogger("domservice.worker")


async def run_notification_worker(
    poll_interval_sec: int | None = None,
) -> None:
    """Фоновый обработчик очереди уведомлений (опрос каждые 5 секунд по NFR-04)."""
    interval = poll_interval_sec or settings.notification_poll_interval_seconds
    logger.info("Фоновый обработчик уведомлений запущен (интервал=%s сек.)", interval)
    try:
        while True:
            try:
                async with async_session_factory() as db:
                    await process_notification_queue(db)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error("Ошибка в цикле обработчика уведомлений: %s", exc)

            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        logger.info("Фоновый обработчик уведомлений остановлен")
        raise