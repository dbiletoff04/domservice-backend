from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query
from app.core.security import DemoUser, require_roles
from app.schemas.common import RequestStatusCode, STATUS_NAMES, standard_error_responses
from app.schemas.notifications import NotificationItemOut

router = APIRouter(prefix="/notifications", tags=["Уведомления жителя (F-05)"])


@router.get(
    "/my",
    response_model=list[NotificationItemOut],
    responses=standard_error_responses(401, 403),
    summary="Список уведомлений жителя",
    description="**Доступ:** `resident`. Показывает все уведомления по заявкам жителя (резерв при недоставке СМС).",
)
async def get_my_notifications(
    request_id: int | None = Query(default=None),
    user: DemoUser = Depends(require_roles("resident")),
) -> list[NotificationItemOut]:
    items = [
        NotificationItemOut(
            notification_id=2,
            request_id=123,
            request_number="REQ-123",
            status=RequestStatusCode.MASTER_ASSIGNED,
            status_name=STATUS_NAMES[RequestStatusCode.MASTER_ASSIGNED],
            message_text="Заявка REQ-123: назначен мастер Петров И. С., плановый срок 11.11.2026 12:00",
            state="sent",
            created_at=datetime(2026, 11, 10, 15, 10, tzinfo=timezone.utc),
            sent_at=datetime(2026, 11, 10, 15, 10, 12, tzinfo=timezone.utc),
        ),
        NotificationItemOut(
            notification_id=1,
            request_id=123,
            request_number="REQ-123",
            status=RequestStatusCode.ACCEPTED,
            status_name=STATUS_NAMES[RequestStatusCode.ACCEPTED],
            message_text="Заявка REQ-123 принята в работу",
            state="sent",
            created_at=datetime(2026, 11, 10, 15, 0, tzinfo=timezone.utc),
            sent_at=datetime(2026, 11, 10, 15, 0, 8, tzinfo=timezone.utc),
        ),
    ]
    if request_id is not None:
        return [item for item in items if item.request_id == request_id]
    return items