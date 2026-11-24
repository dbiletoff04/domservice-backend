import logging
import secrets

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser
from app.models.references import ManagementCompany, ProblemCategory
from app.models.request import Request, RequestStatusHistory
from app.schemas.requests import CreateRequestIn

logger = logging.getLogger("domservice.requests")


async def create_resident_request(
    db: AsyncSession,
    user: CurrentUser,
    payload: CreateRequestIn,
) -> Request:
    """Проверяет категорию и сохраняет новую заявку жителя и первую запись истории в одной транзакции."""
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
        await db.flush()  # Получаем сгенерированный request_id

        new_request.request_number = f"REQ-{new_request.request_id}"

        history_entry = RequestStatusHistory(
            request_id=new_request.request_id,
            from_status_code=None,
            to_status_code="accepted",
            actor_id=user.user_id,
            comment="Заявка создана жителем",
        )
        db.add(history_entry)

        await db.commit()
        await db.refresh(new_request)
    except Exception:
        await db.rollback()
        raise

    logger.info(
        "[REQUEST] Создана заявка %s (id=%s) жителем user_id=%s, категория=%s",
        new_request.request_number,
        new_request.request_id,
        user.user_id,
        category.name,
    )
    return new_request