from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.core.security import DemoUser, require_roles
from app.schemas.common import RequestStatusCode, STATUS_NAMES, standard_error_responses
from app.schemas.requests import (
    AssignMasterIn,
    DispatcherCreateRequestIn,
    DispatcherRequestItemOut,
    RequestCreatedOut,
    RequestStatusActionOut,
)

router = APIRouter(prefix="/dispatcher", tags=["Диспетчер УК (F-06, F-09)"])

NOW = datetime(2026, 11, 10, 15, 0, tzinfo=timezone.utc)


@router.get(
    "/requests",
    response_model=list[DispatcherRequestItemOut],
    responses=standard_error_responses(401, 403),
    summary="Реестр заявок УК (включая возвращённые)",
    description="**Доступ:** `dispatcher`. Для списка «Возвращённые» передайте `?status=returned`.",
)
async def get_dispatcher_requests(
    status_filter: RequestStatusCode | None = Query(default=None, alias="status"),
    user: DemoUser = Depends(require_roles("dispatcher")),
) -> list[DispatcherRequestItemOut]:
    items = [
        DispatcherRequestItemOut(
            request_id=124,
            request_number="REQ-124",
            category_name="Сантехника",
            address="г. Волжский, ул. Мира, д. 15",
            apartment="10",
            status=RequestStatusCode.ACCEPTED,
            status_name=STATUS_NAMES[RequestStatusCode.ACCEPTED],
            deadline_at=None,
            deadline_display="Уточняется",
            master_name=None,
            last_comment=None,
            created_at=NOW,
        ),
        DispatcherRequestItemOut(
            request_id=122,
            request_number="REQ-122",
            category_name="Электрика",
            address="г. Волжский, ул. Ленина, д. 97",
            apartment="18",
            status=RequestStatusCode.RETURNED,
            status_name=STATUS_NAMES[RequestStatusCode.RETURNED],
            deadline_at=datetime(2026, 11, 10, 14, 0, tzinfo=timezone.utc),
            deadline_display="10.11.2026 14:00",
            master_name="Петров И. С.",
            last_comment="Свет в коридоре снова мигает",
            created_at=datetime(2026, 11, 9, 11, 0, tzinfo=timezone.utc),
        ),
    ]
    if status_filter is not None:
        return [item for item in items if item.status == status_filter]
    return items


@router.post(
    "/requests",
    response_model=RequestCreatedOut,
    status_code=status.HTTP_201_CREATED,
    responses=standard_error_responses(400, 401, 403),
    summary="Создать заявку по телефонному звонку",
    description="**Доступ:** `dispatcher`. Создаёт заявку от имени жителя и ставит СМС с номером в очередь.",
)
async def create_request_by_phone(
    payload: DispatcherCreateRequestIn,
    user: DemoUser = Depends(require_roles("dispatcher")),
) -> RequestCreatedOut:
    return RequestCreatedOut(
        request_id=125,
        request_number="REQ-125",
        status=RequestStatusCode.ACCEPTED,
        status_name=STATUS_NAMES[RequestStatusCode.ACCEPTED],
        deadline_display="Уточняется",
        created_at=NOW,
        message="Заявка зарегистрирована диспетчером",
    )


@router.patch(
    "/requests/{request_id}/assign",
    response_model=RequestStatusActionOut,
    responses=standard_error_responses(400, 401, 403, 404),
    summary="Назначить мастера и срок выполнения",
    description="**Доступ:** `dispatcher`. Переводит заявку (в т.ч. возвращённую) в статус `master_assigned`.",
)
async def assign_master(
    request_id: int,
    payload: AssignMasterIn,
    user: DemoUser = Depends(require_roles("dispatcher")),
) -> RequestStatusActionOut:
    if request_id == 999:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Заявка не найдена")
    if payload.master_id != 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Мастер не найден или пользователь не имеет роль master (для демо: master_id=5)",
        )
    deadline_str = (
        payload.deadline_at.strftime("%d.%m.%Y %H:%M")
        if payload.deadline_at
        else "Уточняется"
    )
    return RequestStatusActionOut(
        request_id=request_id,
        request_number=f"REQ-{request_id}",
        status=RequestStatusCode.MASTER_ASSIGNED,
        status_name=STATUS_NAMES[RequestStatusCode.MASTER_ASSIGNED],
        master_id=payload.master_id,
        deadline_at=payload.deadline_at,
        deadline_display=deadline_str,
    )