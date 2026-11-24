from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import CurrentUser, require_roles
from app.schemas.common import RequestStatusCode, standard_error_responses
from app.schemas.notifications import NotificationItemOut
from app.services.notification_service import list_resident_notifications

router = APIRouter(prefix="/notifications", tags=["Уведомления жителя (F-05)"])


@router.get(
    "/my",
    response_model=list[NotificationItemOut],
    responses=standard_error_responses(401, 403),
    summary="Список уведомлений для экрана жителя",
    description=(
        "**Доступ:** `resident`. Показывает отправленные уведомления (`state='sent'`) текущего жителя.\n\n"
        "При `include_pending=true` также показывает сообщения, ещё ожидающие в очереди (`new` / `error`)."
    ),
)
async def get_my_notifications(
    request_id: int | None = Query(default=None, description="Фильтр по ID заявки"),
    include_pending: bool = Query(
        default=False,
        description="Включить ещё не отправленные сообщения из очереди",
    ),
    user: CurrentUser = Depends(require_roles("resident")),
    db: AsyncSession = Depends(get_db),
) -> list[NotificationItemOut]:
    rows = await list_resident_notifications(
        db=db,
        resident_id=user.user_id,
        request_id=request_id,
        include_pending=include_pending,
    )

    result: list[NotificationItemOut] = []
    for notif, req_number, status_name in rows:
        delay: float | None = None
        if notif.sent_at is not None:
            delay = round(max((notif.sent_at - notif.created_at).total_seconds(), 0.0), 2)

        result.append(
            NotificationItemOut(
                notification_id=notif.notification_id,
                request_id=notif.request_id,
                request_number=req_number,
                status=RequestStatusCode(notif.status_code),
                status_name=status_name,
                message_text=notif.message_text,
                state=notif.state,
                attempts=notif.attempts,
                created_at=notif.created_at,
                sent_at=notif.sent_at,
                delivery_delay_seconds=delay,
            )
        )
    return result