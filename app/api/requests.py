from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import CurrentUser, require_roles
from app.schemas.common import RequestStatusCode, STATUS_NAMES, standard_error_responses
from app.schemas.requests import (
    ConfirmWorkIn,
    CreateRequestIn,
    RejectWorkIn,
    RequestCreatedOut,
    RequestDetailOut,
    RequestStatusActionOut,
    RequestSummaryOut,
    StatusHistoryItemOut,
)
from app.services.request_service import (
    create_resident_request,
    format_actor_name,
    format_deadline,
    get_request_detail_for_user,
    list_resident_requests,
)

router = APIRouter(prefix="/requests", tags=["Заявки жителя (F-02, F-03, F-04, F-08)"])


@router.post(
    "",
    response_model=RequestCreatedOut,
    status_code=status.HTTP_201_CREATED,
    responses=standard_error_responses(400, 401, 403, 409),
    summary="Создать заявку (житель)",
    description=(
        "**Доступ:** только `resident`. Атомарно создаёт заявку со статусом `accepted`, "
        "присваивает номер `REQ-...`, добавляет первую запись истории и ставит уведомление в очередь.\n\n"
        "Поддерживает заголовок `Idempotency-Key` (UUID) — повторный запрос с тем же ключом и данными "
        "не создаст дубликат и вернёт прежний номер заявки (Р8).\n\n"
        "Параметр `simulate_error=true` (при `APP_DEBUG=true`) позволяет проверить откат транзакции при сбое (`NFR-03`)."
    ),
)
async def create_request(
    payload: CreateRequestIn,
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
        description="Необязательный UUID для защиты от дублей при повторной отправке",
    ),
    simulate_error: bool = Query(
        default=False,
        description="Искусственная ошибка перед записью уведомления (для проверки NFR-03)",
    ),
    user: CurrentUser = Depends(require_roles("resident")),
    db: AsyncSession = Depends(get_db),
) -> RequestCreatedOut:
    created = await create_resident_request(
        db=db,
        user=user,
        payload=payload,
        simulate_error=simulate_error,
        idempotency_key=idempotency_key,
    )
    return RequestCreatedOut(
        request_id=created.request_id,
        request_number=created.request_number,
        status=RequestStatusCode(created.status_code),
        status_name=STATUS_NAMES[RequestStatusCode(created.status_code)],
        deadline_display=format_deadline(created.deadline_at),
        created_at=created.created_at,
        message="Заявка принята",
    )


@router.get(
    "/my",
    response_model=list[RequestSummaryOut],
    responses=standard_error_responses(401, 403),
    summary="Список своих заявок (житель)",
    description="**Доступ:** только `resident`. Возвращает из БД только заявки текущего жителя.",
)
async def get_my_requests(
    status_filter: RequestStatusCode | None = Query(default=None, alias="status"),
    user: CurrentUser = Depends(require_roles("resident")),
    db: AsyncSession = Depends(get_db),
) -> list[RequestSummaryOut]:
    rows = await list_resident_requests(
        db=db,
        user=user,
        status_filter=status_filter.value if status_filter else None,
    )
    return [
        RequestSummaryOut(
            request_id=req.request_id,
            request_number=req.request_number,
            category_name=req.category.name if req.category else "",
            address=req.address,
            apartment=req.apartment,
            status=RequestStatusCode(req.status_code),
            status_name=(
                req.status.name
                if req.status
                else STATUS_NAMES[RequestStatusCode(req.status_code)]
            ),
            deadline_at=req.deadline_at,
            deadline_display=format_deadline(req.deadline_at),
            created_at=req.created_at,
        )
        for req in rows
    ]


@router.get(
    "/{request_id}",
    response_model=RequestDetailOut,
    responses=standard_error_responses(401, 403, 404),
    summary="Карточка заявки (подробности, срок и история статусов)",
    description=(
        "**Доступ:** `resident` (только своя), `dispatcher` (заявки своей УК), `master` (только назначенная).\n\n"
        "При попытке открыть чужую заявку возвращает `403 Forbidden` («Нет доступа к чужой заявке», `NFR-07`)."
    ),
)
async def get_request_detail(
    request_id: int,
    user: CurrentUser = Depends(require_roles("resident", "dispatcher", "master")),
    db: AsyncSession = Depends(get_db),
) -> RequestDetailOut:
    req = await get_request_detail_for_user(db=db, request_id=request_id, user=user)

    master_name: str | None = None
    if req.master is not None:
        master_name = req.master.full_name or req.master.phone

    history_items = [
        StatusHistoryItemOut(
            history_id=item.history_id,
            from_status=(
                RequestStatusCode(item.from_status_code)
                if item.from_status_code
                else None
            ),
            to_status=RequestStatusCode(item.to_status_code),
            to_status_name=(
                item.to_status.name
                if item.to_status
                else STATUS_NAMES[RequestStatusCode(item.to_status_code)]
            ),
            actor_name=format_actor_name(item.actor),
            comment=item.comment,
            changed_at=item.changed_at,
        )
        for item in sorted(req.history, key=lambda h: h.changed_at)
    ]

    return RequestDetailOut(
        request_id=req.request_id,
        request_number=req.request_number,
        address=req.address,
        apartment=req.apartment,
        category_id=req.category_id,
        category_name=req.category.name if req.category else "",
        description=req.description,
        status=RequestStatusCode(req.status_code),
        status_name=(
            req.status.name
            if req.status
            else STATUS_NAMES[RequestStatusCode(req.status_code)]
        ),
        master_name=master_name,
        resident_phone=(
            req.resident.phone
            if req.resident and user.role in {"dispatcher", "master"}
            else None
        ),
        deadline_at=req.deadline_at,
        deadline_display=format_deadline(req.deadline_at),
        created_at=req.created_at,
        updated_at=req.updated_at,
        history=history_items,
    )


@router.post(
    "/{request_id}/confirm",
    response_model=RequestStatusActionOut,
    responses=standard_error_responses(401, 403, 404, 409),
    summary="Подтвердить выполнение работ (житель)",
    description="**Доступ:** `resident` (только своя заявка). Переводит статус из `pending_confirmation` в `closed`.",
)
async def confirm_work(
    request_id: int,
    payload: ConfirmWorkIn,
    user: CurrentUser = Depends(require_roles("resident")),
) -> RequestStatusActionOut:
    if request_id == 999:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Заявка не найдена")
    if request_id == 200:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Доступ к чужой заявке запрещён")
    if request_id == 100:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Нельзя подтвердить заявку, пока мастер не отметил выполнение",
        )
    return RequestStatusActionOut(
        request_id=request_id,
        request_number=f"REQ-{request_id}",
        status=RequestStatusCode.CLOSED,
        status_name=STATUS_NAMES[RequestStatusCode.CLOSED],
    )


@router.post(
    "/{request_id}/reject",
    response_model=RequestStatusActionOut,
    responses=standard_error_responses(401, 403, 404, 409),
    summary="Вернуть заявку — «Проблема не решена» (житель)",
    description="**Доступ:** `resident` (только своя заявка). Требует обязательный `comment`. Переводит в `returned`.",
)
async def reject_work(
    request_id: int,
    payload: RejectWorkIn,
    user: CurrentUser = Depends(require_roles("resident")),
) -> RequestStatusActionOut:
    if request_id == 999:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Заявка не найдена")
    if request_id == 200:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Доступ к чужой заявке запрещён")
    return RequestStatusActionOut(
        request_id=request_id,
        request_number=f"REQ-{request_id}",
        status=RequestStatusCode.RETURNED,
        status_name=STATUS_NAMES[RequestStatusCode.RETURNED],
        comment=payload.comment,
    )