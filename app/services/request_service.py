import logging
import secrets
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.security import CurrentUser
from app.models.references import ManagementCompany, ProblemCategory
from app.models.request import Request, RequestStatusHistory
from app.models.user import AppUser
from app.schemas.requests import CreateRequestIn
from app.services.notification_service import enqueue_notification

logger = logging.getLogger("domservice.requests")

ROLE_TITLES = {
    "resident": "Житель",
    "dispatcher": "Диспетчер УК",
    "master": "Мастер",
    "manager": "Руководитель УК",
}


def format_deadline(deadline_at: datetime | None) -> str:
    if deadline_at is None:
        return "Уточняется"
    return deadline_at.strftime("%d.%m.%Y %H:%M")


def format_actor_name(actor: AppUser | None) -> str:
    if actor is None:
        return "Система"
    if actor.full_name:
        return actor.full_name
    return ROLE_TITLES.get(actor.role_code, actor.phone)


async def create_resident_request(
    db: AsyncSession,
    user: CurrentUser,
    payload: CreateRequestIn,
    simulate_error: bool = False,
) -> Request:
    """
    Атомарно (в одной транзакции) сохраняет:
    1) заявку с уникальным номером REQ-<id>,
    2) первую запись истории статусов,
    3) уведомление жителю в очередь (state='new').
    При любом сбое выполняется rollback — в БД не остаётся неполных данных (NFR-03).
    """
    category = await db.scalar(
        select(ProblemCategory).where(
            ProblemCategory.category_id == payload.category_id,
            ProblemCategory.is_active.is_(True),
        )
    )
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Указанная категория проблемы не найдена или неактивна",
        )

    company = await db.scalar(
        select(ManagementCompany).order_by(ManagementCompany.company_id.asc())
    )
    if company is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="В системе не настроена управляющая компания",
        )

    temp_number = f"TMP-{secrets.token_hex(5)}"
    new_request = Request(
        request_number=temp_number,
        resident_id=user.user_id,
        company_id=company.company_id,
        category_id=category.category_id,
        address=payload.address,
        apartment=payload.apartment,
        description=payload.description,
        status_code="accepted",
    )

    try:
        db.add(new_request)
        await db.flush()

        new_request.request_number = f"REQ-{new_request.request_id}"

        history_entry = RequestStatusHistory(
            request_id=new_request.request_id,
            from_status_code=None,
            to_status_code="accepted",
            actor_id=user.user_id,
            comment="Заявка создана жителем",
        )
        db.add(history_entry)
        await db.flush()

        if simulate_error and settings.app_debug:
            raise RuntimeError(
                "Искусственная ошибка при постановке уведомления в очередь (тест NFR-03)"
            )

        enqueue_notification(
            db=db,
            request_id=new_request.request_id,
            recipient_id=user.user_id,
            status_code="accepted",
            message_text=f"Заявка {new_request.request_number} принята в работу.",
        )

        await db.commit()
        await db.refresh(new_request)
    except HTTPException:
        await db.rollback()
        raise
    except Exception as exc:
        await db.rollback()
        logger.error(
            "[NFR-03 ROLLBACK] Откат транзакции при создании заявки (user_id=%s): %s",
            user.user_id,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Заявка не отправлена из-за сбоя сохранения. Повторите попытку.",
        ) from exc

    logger.info(
        "[REQUEST] Создана заявка %s (id=%s), записана история и поставлено уведомление в очередь",
        new_request.request_number,
        new_request.request_id,
    )
    return new_request


async def list_resident_requests(
    db: AsyncSession,
    user: CurrentUser,
    status_filter: str | None = None,
) -> list[Request]:
    """Возвращает только заявки текущего жителя (от новых к старым)."""
    stmt = (
        select(Request)
        .options(
            selectinload(Request.category),
            selectinload(Request.status),
        )
        .where(Request.resident_id == user.user_id)
    )
    if status_filter is not None:
        stmt = stmt.where(Request.status_code == status_filter)

    stmt = stmt.order_by(Request.created_at.desc())
    return list((await db.scalars(stmt)).all())


async def get_request_detail_for_user(
    db: AsyncSession,
    request_id: int,
    user: CurrentUser,
) -> Request:
    """
    Возвращает полную карточку заявки с историей статусов.
    Проверяет права доступа по ролям (NFR-07):
    - resident видит только свои заявки;
    - dispatcher видит заявки своей УК;
    - master видит только назначенные ему заявки.
    """
    stmt = (
        select(Request)
        .options(
            selectinload(Request.category),
            selectinload(Request.status),
            selectinload(Request.master),
            selectinload(Request.resident),
            selectinload(Request.history).selectinload(RequestStatusHistory.actor),
            selectinload(Request.history).selectinload(RequestStatusHistory.to_status),
        )
        .where(Request.request_id == request_id)
    )
    req = await db.scalar(stmt)
    if req is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Заявка не найдена",
        )

    if user.role == "resident" and req.resident_id != user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет доступа к чужой заявке",
        )
    if user.role == "dispatcher" and req.company_id != user.company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет доступа к заявке другой управляющей компании",
        )
    if user.role == "master" and req.master_id != user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет доступа: заявка не назначена этому мастеру",
        )

    return req