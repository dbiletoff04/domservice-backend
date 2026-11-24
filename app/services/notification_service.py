from sqlalchemy.ext.asyncio import AsyncSession

from app.models.request import Notification


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