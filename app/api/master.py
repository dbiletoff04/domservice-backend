from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.core.security import CurrentUser, require_roles
from app.schemas.common import RequestStatusCode, STATUS_NAMES, standard_error_responses
from app.schemas.requests import (
    CompleteTaskIn,
    MasterTaskItemOut,
    RequestStatusActionOut,
)

router = APIRouter(prefix="/master", tags=["Мастер (F-07, F-09)"])


@router.get(
    "/tasks",
    response_model=list[MasterTaskItemOut],
    responses=standard_error_responses(401, 403),
    summary="Список задач, назначенных текущему мастеру",
    description="**Доступ:** `master`. Включает контакт жителя, признак возврата и комментарий жителя.",
)
async def get_master_tasks(
    status_filter: RequestStatusCode | None = Query(default=None, alias="status"),
    user: CurrentUser = Depends(require_roles("master")),
) -> list[MasterTaskItemOut]:
    items = [
        MasterTaskItemOut(
            request_id=123,
            request_number="REQ-123",
            address="г. Волжский, ул. Ленина, д. 97",
            apartment="42",
            description="Протекает кран на кухне под раковиной",
            resident_phone="+79001112233",
            status=RequestStatusCode.MASTER_ASSIGNED,
            status_name=STATUS_NAMES[RequestStatusCode.MASTER_ASSIGNED],
            is_returned=False,
            return_comment=None,
            deadline_display="11.11.2026 12:00",
        ),
        MasterTaskItemOut(
            request_id=122,
            request_number="REQ-122",
            address="г. Волжский, ул. Ленина, д. 97",
            apartment="18",
            description="Не работает выключатель в прихожей",
            resident_phone="+79005556677",
            status=RequestStatusCode.MASTER_ASSIGNED,
            status_name=STATUS_NAMES[RequestStatusCode.MASTER_ASSIGNED],
            is_returned=True,
            return_comment="Свет в коридоре снова мигает",
            deadline_display="11.11.2026 15:00",
        ),
    ]
    if status_filter is not None:
        return [item for item in items if item.status == status_filter]
    return items


@router.patch(
    "/tasks/{request_id}/complete",
    response_model=RequestStatusActionOut,
    responses=standard_error_responses(401, 403, 404, 409),
    summary="Отметить заявку выполненной",
    description="**Доступ:** `master` (только назначенная ему заявка). Переводит статус в `pending_confirmation`.",
)
async def complete_task(
    request_id: int,
    payload: CompleteTaskIn,
    user: CurrentUser = Depends(require_roles("master")),
) -> RequestStatusActionOut:
    if request_id == 999:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Заявка не найдена")
    if request_id == 200:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Заявка назначена другому мастеру (NFR-07)",
        )
    if request_id == 100:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Заявка должна находиться в статусе «Мастер назначен»",
        )
    return RequestStatusActionOut(
        request_id=request_id,
        request_number=f"REQ-{request_id}",
        status=RequestStatusCode.PENDING_CONFIRMATION,
        status_name=STATUS_NAMES[RequestStatusCode.PENDING_CONFIRMATION],
    )