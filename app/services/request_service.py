import logging
import secrets
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.messages import (
    UI_ERROR_CATEGORY_REQUIRED,
    UI_ERROR_SEND_FAILED,
    format_status_notification,
)
from app.core.security import CurrentUser
from app.models.references import ManagementCompany, ProblemCategory
from app.models.request import Request, RequestStatusHistory
from app.models.user import AppUser
from app.schemas.requests import CreateRequestIn, DemoChangeStatusIn
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
            detail=UI_ERROR_CATEGORY_REQUIRED,
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
            message_text=format_status_notification(
                status_code="accepted",
                request_number=new_request.request_number,
            ),
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
            detail=UI_ERROR_SEND_FAILED,
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
    Проверяет права доступа по ролям (NFR-07).
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


# TEMPORARY (ЛР6): служебная смена статуса для демонстрации работы уведомлений.
# В ЛР7 заменяется рабочим местом диспетчера (F-06) и мастера (F-07).
async def demo_change_request_status(
    db: AsyncSession,
    request_id: int,
    user: CurrentUser,
    payload: DemoChangeStatusIn,
) -> tuple[Request, str, str]:
    """
    ВРЕМЕННАЯ ФУНКЦИЯ (ЛР6): меняет статус заявки, пишет строку в историю
    и ставит уведомление жителю в очередь. В ЛР7 заменяется логикой диспетчера и мастера.
    """
    if not settings.app_debug:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Служебное изменение статуса доступно только в режиме отладки",
        )

    req = await db.scalar(
        select(Request)
        .options(selectinload(Request.master))
        .where(Request.request_id == request_id)
    )
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
    if user.role in {"dispatcher", "master", "manager"} and req.company_id != user.company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет доступа к заявке другой управляющей компании",
        )

    old_status = req.status_code
    new_status = payload.status.value
    if old_status == new_status:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Заявка уже находится в этом статусе",
        )

    master_name: str | None = req.master.full_name if req.master else None
    if new_status == "master_assigned" and req.master_id is None:
        demo_master = await db.scalar(
            select(AppUser)
            .where(AppUser.role_code == "master")
            .order_by(AppUser.user_id.asc())
        )
        if demo_master is not None:
            req.master_id = demo_master.user_id
            master_name = demo_master.full_name or demo_master.phone

    if payload.deadline_at is not None:
        req.deadline_at = payload.deadline_at

    req.status_code = new_status
    deadline_str = format_deadline(req.deadline_at)
    notification_text = format_status_notification(
        status_code=new_status,
        request_number=req.request_number,
        master_name=master_name,
        deadline_display=deadline_str,
    )

    try:
        history_entry = RequestStatusHistory(
            request_id=req.request_id,
            from_status_code=old_status,
            to_status_code=new_status,
            actor_id=user.user_id,
            comment=payload.comment or f"[Временно ЛР6] Демо-перевод статуса в «{new_status}»",
        )
        db.add(history_entry)

        enqueue_notification(
            db=db,
            request_id=req.request_id,
            recipient_id=req.resident_id,
            status_code=new_status,
            message_text=notification_text,
        )

        await db.commit()
        await db.refresh(req)
    except Exception:
        await db.rollback()
        raise

    logger.info(
        "[TEMPORARY ЛР6] Статус заявки %s изменён: %s -> %s; уведомление поставлено в очередь",
        req.request_number,
        old_status,
        new_status,
    )
    return req, old_status, notification_text