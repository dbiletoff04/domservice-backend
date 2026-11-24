import logging
import secrets

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import CurrentUser
from app.models.references import ManagementCompany, ProblemCategory
from app.models.request import Request, RequestStatusHistory
from app.schemas.requests import CreateRequestIn
from app.services.notification_service import enqueue_notification

logger = logging.getLogger("domservice.requests")


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
        # 1. Записываем заявку в рамках текущей транзакции и получаем request_id
        db.add(new_request)
        await db.flush()

        # 2. Присваиваем уникальный номер вида REQ-<число>
        new_request.request_number = f"REQ-{new_request.request_id}"

        # 3. Записываем первую строку истории статусов
        history_entry = RequestStatusHistory(
            request_id=new_request.request_id,
            from_status_code=None,
            to_status_code="accepted",
            actor_id=user.user_id,
            comment="Заявка создана жителем",
        )
        db.add(history_entry)
        await db.flush()

        # Искусственный сбой для проверки атомарности (только в режиме отладки)
        if simulate_error and settings.app_debug:
            raise RuntimeError(
                "Искусственная ошибка при постановке уведомления в очередь (тест NFR-03)"
            )

        # 4. Ставим сообщение с номером заявки в очередь уведомлений
        enqueue_notification(
            db=db,
            request_id=new_request.request_id,
            recipient_id=user.user_id,
            status_code="accepted",
            message_text=f"Заявка {new_request.request_number} принята в работу.",
        )

        # 5. Фиксируем всё одной операцией
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