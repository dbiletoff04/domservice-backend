from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.database import Base, async_session_factory, engine
from app.models import (  # noqa: F401
    AppUser,
    ManagementCompany,
    Notification,
    ProblemCategory,
    Request,
    RequestStatus,
    RequestStatusHistory,
    UserRole,
)


SEED_ROLES = [
    {
        "role_code": "resident",
        "name": "Житель",
        "description": "Подаёт заявки, смотрит статусы, получает уведомления, подтверждает или возвращает работу",
    },
    {
        "role_code": "dispatcher",
        "name": "Диспетчер",
        "description": "Регистрирует заявки по звонку, назначает мастера и срок, обрабатывает возвраты",
    },
    {
        "role_code": "master",
        "name": "Мастер",
        "description": "Видит назначенные заявки, отмечает выполнение",
    },
    {
        "role_code": "manager",
        "name": "Руководитель УК",
        "description": "Формирует отчёт для ГИС ЖКХ",
    },
]

SEED_STATUSES = [
    {
        "status_code": "accepted",
        "name": "Принята",
        "description": "Заявка создана жителем или диспетчером",
    },
    {
        "status_code": "master_assigned",
        "name": "Мастер назначен",
        "description": "Назначены мастер и ориентировочный срок; после возврата выполняется заново",
    },
    {
        "status_code": "pending_confirmation",
        "name": "Ожидает подтверждения",
        "description": "Мастер отметил работу выполненной, ожидается ответ жителя",
    },
    {
        "status_code": "closed",
        "name": "Закрыта",
        "description": "Житель подтвердил выполнение работ",
    },
    {
        "status_code": "returned",
        "name": "Возвращена",
        "description": "Житель сообщил, что проблема не решена; комментарий сохранён в истории",
    },
]

SEED_COMPANIES = [
    {
        "name": "УК «Домсервис» (пилот)",
        "contact_phone": "+78443000000",
    }
]

SEED_CATEGORIES = [
    {"name": "Сантехника", "is_active": True},
    {"name": "Электрика", "is_active": True},
    {"name": "Отопление", "is_active": True},
    {"name": "Водоснабжение", "is_active": True},
    {"name": "Лифт", "is_active": True},
    {"name": "Другое", "is_active": True},
]


async def init_db() -> None:
    """Создаёт отсутствующие таблицы в пустой БД и наполняет справочники + тестовых пользователей 4 ролей."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        await session.execute(
            pg_insert(UserRole)
            .values(SEED_ROLES)
            .on_conflict_do_nothing(index_elements=["role_code"])
        )
        await session.execute(
            pg_insert(RequestStatus)
            .values(SEED_STATUSES)
            .on_conflict_do_nothing(index_elements=["status_code"])
        )
        await session.execute(
            pg_insert(ManagementCompany)
            .values(SEED_COMPANIES)
            .on_conflict_do_nothing(index_elements=["name"])
        )
        await session.execute(
            pg_insert(ProblemCategory)
            .values(SEED_CATEGORIES)
            .on_conflict_do_nothing(index_elements=["name"])
        )
        await session.flush()

        company = await session.scalar(
            select(ManagementCompany).where(
                ManagementCompany.name == "УК «Домсервис» (пилот)"
            )
        )
        pilot_company_id = company.company_id if company else 1

        seed_users = [
            {
                "phone": "+79001112233",
                "full_name": "Кузнецова А. Д.",
                "role_code": "resident",
                "company_id": None,
            },
            {
                "phone": "+79002223344",
                "full_name": "Смирнова Е. В.",
                "role_code": "dispatcher",
                "company_id": pilot_company_id,
            },
            {
                "phone": "+79003334455",
                "full_name": "Петров И. С.",
                "role_code": "master",
                "company_id": pilot_company_id,
            },
            {
                "phone": "+79004445566",
                "full_name": "Волков А. Н.",
                "role_code": "manager",
                "company_id": pilot_company_id,
            },
        ]

        await session.execute(
            pg_insert(AppUser)
            .values(seed_users)
            .on_conflict_do_nothing(index_elements=["phone"])
        )
        await session.commit()