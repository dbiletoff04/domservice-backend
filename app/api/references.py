from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.references import ProblemCategory, RequestStatus
from app.schemas.common import RequestStatusCode
from app.schemas.references import CategoryReferenceItem, StatusReferenceItem

router = APIRouter(prefix="/references", tags=["Справочники"])


@router.get(
    "/statuses",
    response_model=list[StatusReferenceItem],
    summary="Получить перечень всех статусов заявки",
    description="Доступ: все пользователи. Возвращает 5 статусов жизненного цикла заявки из БД.",
)
async def get_statuses(db: AsyncSession = Depends(get_db)) -> list[StatusReferenceItem]:
    rows = (await db.scalars(select(RequestStatus))).all()
    return [
        StatusReferenceItem(
            status_code=RequestStatusCode(row.status_code),
            name=row.name,
            description=row.description,
        )
        for row in rows
    ]


@router.get(
    "/categories",
    response_model=list[CategoryReferenceItem],
    summary="Получить активные категории проблем",
    description="Доступ: все пользователи. Возвращает активные категории из БД.",
)
async def get_categories(db: AsyncSession = Depends(get_db)) -> list[CategoryReferenceItem]:
    rows = (
        await db.scalars(
            select(ProblemCategory)
            .where(ProblemCategory.is_active.is_(True))
            .order_by(ProblemCategory.category_id.asc())
        )
    ).all()
    return [
        CategoryReferenceItem(
            category_id=row.category_id,
            name=row.name,
            is_active=row.is_active,
        )
        for row in rows
    ]