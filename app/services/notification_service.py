import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.references import RequestStatus
from app.models.request import Notification, Request

logger = logging.getLogger("domservice.notifications")


def build_notification(
    request_id: int,
    recipient_id: int,
    status_code: str,
    message_text: str,
) -> Notification:
    """Создаёт объект уведомления для постановки в очередь (state='new')."""
    return Notification(
        request_id=request_id,
        recipient_id=recipient_id,
        status_code=status_code,
        message_text=message_text,
        state="new",
        attempts=0,
    )


def enqueue_notification(
    db: AsyncSession,
    request_id: int,
    recipient_id: int,
    status_code: str,
    message_text: str,
) -> Notification:
    """Добавляет уведомление в текущую транзакцию БД без преждевременного commit."""
    notification = build_notification(
        request_id=request_id,
        recipient_id=recipient_id,
        status_code=status_code,
        message_text=message_text,
    )
    db.add(notification)
    return notification


def send_notification_mock(
    notification: Notification,
    recipient_phone: str,
    request_number: str,
) -> None:
    """
    Заглушка отправки СМС/push: записывает сообщение в журнал программы.
    Для проверки повторных попыток при ошибке: номер +79000000000 в режиме отладки
    имитирует временный сбой шлюза на первых 2 попытках.
    """
    if (
        settings.app_debug
        and recipient_phone == "+79000000000"
        and notification.attempts < 2
    ):
        raise ConnectionError("Временная недоступность СМС-шлюза (тестовый сбой)")

    now = datetime.now(timezone.utc)
    delay_sec = max((now - notification.created_at).total_seconds(), 0.0)
    logger.info(
        "[УВЕДОМЛЕНИЕ ОТПРАВЛЕНО] Кому: %s | Заявка: %s | Текст: «%s» | Задержка: %.2f сек.",
        recipient_phone,
        request_number,
        notification.message_text,
        delay_sec,
    )
    if delay_sec > 60:
        logger.warning(
            "[NFR-04 НАРУШЕНИЕ] Задержка отправки notification_id=%s составила %.2f сек. (> 60 сек.)",
            notification.notification_id,
            delay_sec,
        )


async def process_notification_queue(db: AsyncSession) -> int:
    """
    Берёт из очереди уведомления в состоянии 'new' или 'error' (пока attempts < max),
    пытается отправить, обновляет state ('sent'/'error'), attempts и sent_at.
    """
    stmt = (
        select(Notification)
        .options(
            selectinload(Notification.request),
            selectinload(Notification.recipient),
        )
        .where(
            Notification.state.in_(("new", "error")),
            Notification.attempts < settings.notification_max_attempts,
        )
        .order_by(Notification.created_at.asc())
        .limit(20)
        .with_for_update(skip_locked=True)
    )

    items = list((await db.scalars(stmt)).all())
    if not items:
        return 0

    sent_count = 0
    for notif in items:
        recipient_phone = notif.recipient.phone if notif.recipient else "неизвестно"
        request_number = notif.request.request_number if notif.request else f"#{notif.request_id}"

        try:
            send_notification_mock(
                notification=notif,
                recipient_phone=recipient_phone,
                request_number=request_number,
            )
            notif.attempts += 1
            notif.state = "sent"
            notif.sent_at = datetime.now(timezone.utc)
            sent_count += 1
        except Exception as exc:
            notif.attempts += 1
            notif.state = "error"
            logger.warning(
                "[УВЕДОМЛЕНИЕ ОШИБКА] notification_id=%s (%s), попытка %s/%s: %s",
                notif.notification_id,
                recipient_phone,
                notif.attempts,
                settings.notification_max_attempts,
                exc,
            )

        await db.commit()

    return sent_count


async def list_resident_notifications(
    db: AsyncSession,
    resident_id: int,
    request_id: int | None = None,
    include_pending: bool = False,
) -> list[tuple[Notification, str, str]]:
    """Возвращает уведомления жителя (по умолчанию только отправленные state='sent')."""
    stmt = (
        select(Notification, Request.request_number, RequestStatus.name)
        .join(Request, Notification.request_id == Request.request_id)
        .join(RequestStatus, Notification.status_code == RequestStatus.status_code)
        .where(Notification.recipient_id == resident_id)
    )
    if not include_pending:
        stmt = stmt.where(Notification.state == "sent")
    if request_id is not None:
        stmt = stmt.where(Notification.request_id == request_id)

    stmt = stmt.order_by(Notification.created_at.desc())
    return list((await db.execute(stmt)).all())