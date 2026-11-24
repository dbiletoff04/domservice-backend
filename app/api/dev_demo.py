# TEMPORARY (ЛР6): Временный служебный модуль для демонстрации уведомлений при смене статуса.
# В ЛР7 этот файл должен быть удалён и заменён рабочим местом диспетчера (F-06) и мастера (F-07).

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import CurrentUser, get_current_user
from app.schemas.common import RequestStatusCode, STATUS_NAMES, standard_error_responses
from app.schemas.requests import DemoChangeStatusIn, DemoChangeStatusOut
from app.services.request_service import demo_change_request_status, format_deadline

router = APIRouter(
    prefix="/dev",
    tags=["Служебное [ВРЕМЕННО для ЛР6 — заменится диспетчером в ЛР7]"],
)


@router.patch(
    "/requests/{request_id}/status",
    response_model=DemoChangeStatusOut,
    responses=standard_error_responses(400, 401, 403, 404),
    summary="[ВРЕМЕННО ЛР6] Изменить статус заявки для проверки уведомлений",
    description=(
        "**TEMPORARY (ЛР6):** Временный служебный метод для демонстрации работы очереди уведомлений, "
        "пока рабочее место диспетчера не реализовано (будет заменено в ЛР7).\n\n"
        "Меняет статус заявки, добавляет запись в `request_status_history` и ставит уведомление жителю в очередь."
    ),
)
async def temporary_change_status(
    request_id: int,
    payload: DemoChangeStatusIn,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DemoChangeStatusOut:
    req, old_status, notification_text = await demo_change_request_status(
        db=db,
        request_id=request_id,
        user=user,
        payload=payload,
    )
    new_status_enum = RequestStatusCode(req.status_code)
    return DemoChangeStatusOut(
        request_id=req.request_id,
        request_number=req.request_number,
        old_status=RequestStatusCode(old_status),
        new_status=new_status_enum,
        new_status_name=STATUS_NAMES[new_status_enum],
        deadline_display=format_deadline(req.deadline_at),
        notification_queued=True,
        notification_text=notification_text,
    )