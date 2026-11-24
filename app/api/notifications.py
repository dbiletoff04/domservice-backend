from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import CurrentUser, require_roles
from app.models.references import RequestStatus
from app.models.request import Notification, Request
from app.schemas.common import RequestStatusCode, standard_error_responses
from app.schemas.notifications import NotificationItemOut

router = APIRouter(prefix="/notifications", tags=["Уведомления жителя (F-05)"])


@router.get(
    "/my",
    response_model=list[NotificationItemOut],
    responses=standard_error_responses(401, 403),
    summary="Список уведомлений жителя (из БД / очереди)",
    description="**Доступ:** `resident`. Показывает уведомления по заявкам текущего жителя.",
)
async def get_my_notifications(
    request_id: int | None = Query(default=None),
    user: CurrentUser = Depends(require_roles("resident")),
    db: AsyncSession = Depends(get_db),
) -> list[NotificationItemOut]:
    stmt = (
        select(Notification, Request.request_number, RequestStatus.name)
        .join(Request, Notification.request_id == Request.request_id)
        .join(RequestStatus, Notification.status_code == RequestStatus.status_code)
        .where(Notification.recipient_id == user.user_id)
    )
    if request_id is not None:
        stmt = stmt.where(Notification.request_id == request_id)
    stmt = stmt.order_by(Notification.created_at.desc())

    rows = (await db.execute(stmt)).all()
    return [
        NotificationItemOut(
            notification_id=notif.notification_id,
            request_id=notif.request_id,
            request_number=req_number,
            status=RequestStatusCode(notif.status_code),
            status_name=status_name,
            message_text=notif.message_text,
            state=notif.state,
            created_at=notif.created_at,
            sent_at=notif.sent_at,
        )
        for notif, req_number, status_name in rows
    ]