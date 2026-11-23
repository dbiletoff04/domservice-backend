from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.core.security import DemoUser, get_current_user, require_roles
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

router = APIRouter(prefix="/requests", tags=["Заявки жителя (F-02, F-03, F-04, F-08)"])

NOW = datetime(2026, 11, 10, 15, 0, tzinfo=timezone.utc)


@router.post(
    "",
    response_model=RequestCreatedOut,
    status_code=status.HTTP_201_CREATED,
    responses=standard_error_responses(400, 401, 403),
    summary="Создать заявку (житель)",
    description="**Доступ:** только `resident`. Создаёт заявку со статусом `accepted` и возвращает номер `REQ-...`.",
)
async def create_request(
    payload: CreateRequestIn,
    user: DemoUser = Depends(require_roles("resident")),
) -> RequestCreatedOut:
    if payload.category_id > 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Указанная категория проблемы не найдена или неактивна",
        )
    return RequestCreatedOut(
        request_id=123,
        request_number="REQ-123",
        status=RequestStatusCode.ACCEPTED,
        status_name=STATUS_NAMES[RequestStatusCode.ACCEPTED],
        deadline_display="Уточняется",
        created_at=NOW,
        message="Заявка принята",
    )


@router.get(
    "/my",
    response_model=list[RequestSummaryOut],
    responses=standard_error_responses(401, 403),
    summary="Список своих заявок (житель)",
    description="**Доступ:** только `resident`. Возвращает только заявки текущего жителя.",
)
async def get_my_requests(
    status_filter: RequestStatusCode | None = Query(default=None, alias="status"),
    user: DemoUser = Depends(require_roles("resident")),
) -> list[RequestSummaryOut]:
    items = [
        RequestSummaryOut(
            request_id=123,
            request_number="REQ-123",
            category_name="Сантехника",
            address="г. Волжский, ул. Ленина, д. 97",
            apartment="42",
            status=RequestStatusCode.MASTER_ASSIGNED,
            status_name=STATUS_NAMES[RequestStatusCode.MASTER_ASSIGNED],
            deadline_at=datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc),
            deadline_display="11.11.2026 12:00",
            created_at=NOW,
        ),
        RequestSummaryOut(
            request_id=120,
            request_number="REQ-120",
            category_name="Отопление",
            address="г. Волжский, ул. Ленина, д. 97",
            apartment="42",
            status=RequestStatusCode.CLOSED,
            status_name=STATUS_NAMES[RequestStatusCode.CLOSED],
            deadline_at=datetime(2026, 11, 5, 16, 0, tzinfo=timezone.utc),
            deadline_display="05.11.2026 16:00",
            created_at=datetime(2026, 11, 4, 10, 0, tzinfo=timezone.utc),
        ),
    ]
    if status_filter is not None:
        return [item for item in items if item.status == status_filter]
    return items


@router.get(
    "/{request_id}",
    response_model=RequestDetailOut,
    responses=standard_error_responses(401, 403, 404),
    summary="Карточка заявки (подробности и история статусов)",
    description=(
        "**Доступ:** `resident` (только своя), `dispatcher` (заявки УК), `master` (только назначенная).\n\n"
        "**Для проверки ошибок на тестовых данных:**\n"
        "- `request_id = 123` → успешный ответ;\n"
        "- `request_id = 200` (под ролью `resident`/`master`) → `403` (чужая заявка);\n"
        "- `request_id = 999` → `404` (не найдена)."
    ),
)
async def get_request_detail(
    request_id: int,
    user: DemoUser = Depends(require_roles("resident", "dispatcher", "master")),
) -> RequestDetailOut:
    if request_id == 999:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Заявка не найдена")
    if request_id == 200 and user.role in {"resident", "master"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ к чужой заявке запрещён (NFR-07)",
        )

    return RequestDetailOut(
        request_id=request_id,
        request_number=f"REQ-{request_id}",
        address="г. Волжский, ул. Ленина, д. 97",
        apartment="42",
        category_id=1,
        category_name="Сантехника",
        description="Протекает кран на кухне под раковиной",
        status=RequestStatusCode.MASTER_ASSIGNED,
        status_name=STATUS_NAMES[RequestStatusCode.MASTER_ASSIGNED],
        master_name="Петров И. С.",
        resident_phone="+79001112233" if user.role in {"dispatcher", "master"} else None,
        deadline_at=datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc),
        deadline_display="11.11.2026 12:00",
        created_at=NOW,
        updated_at=datetime(2026, 11, 10, 15, 10, tzinfo=timezone.utc),
        history=[
            StatusHistoryItemOut(
                history_id=1,
                from_status=None,
                to_status=RequestStatusCode.ACCEPTED,
                to_status_name=STATUS_NAMES[RequestStatusCode.ACCEPTED],
                actor_name="Кузнецова А. Д.",
                comment=None,
                changed_at=NOW,
            ),
            StatusHistoryItemOut(
                history_id=2,
                from_status=RequestStatusCode.ACCEPTED,
                to_status=RequestStatusCode.MASTER_ASSIGNED,
                to_status_name=STATUS_NAMES[RequestStatusCode.MASTER_ASSIGNED],
                actor_name="Смирнова Е. В.",
                comment="Назначен мастер Петров И. С.",
                changed_at=datetime(2026, 11, 10, 15, 10, tzinfo=timezone.utc),
            ),
        ],
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
    user: DemoUser = Depends(require_roles("resident")),
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
    user: DemoUser = Depends(require_roles("resident")),
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