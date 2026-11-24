from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import CurrentUser, get_current_user
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RequestCodeIn,
    RequestCodeOut,
    UserProfile,
)
from app.schemas.common import UserRoleCode, standard_error_responses
from app.services.auth_service import authenticate_with_sms, issue_sms_code

router = APIRouter(prefix="/auth", tags=["Аутентификация (F-01)"])


@router.post(
    "/request-code",
    response_model=RequestCodeOut,
    summary="Запросить одноразовый СМС-код для входа",
    description=(
        "**Доступ:** публичный.\n\n"
        "Генерирует 4-значный одноразовый код и **записывает его в журнал программы** (вместо реальной отправки СМС).\n\n"
        "**Тестовые номера по ролям:**\n"
        "- `+79001112233` — Житель (`resident`)\n"
        "- `+79002223344` — Диспетчер (`dispatcher`)\n"
        "- `+79003334455` — Мастер (`master`)\n"
        "- `+79004445566` — Руководитель УК (`manager`)\n"
        "- Любой новый номер → автоматически регистрируется как `resident`."
    ),
)
async def request_sms_code(payload: RequestCodeIn) -> RequestCodeOut:
    phone, ttl = issue_sms_code(payload.phone)
    return RequestCodeOut(phone=phone, expires_in_seconds=ttl)


@router.post(
    "/login",
    response_model=LoginResponse,
    responses=standard_error_responses(400),
    summary="Вход по номеру телефона и СМС-коду с выдачей JWT",
    description=(
        "**Доступ:** публичный.\n\n"
        "Проверяет одноразовый код из журнала, проверяет согласие ФЗ-152 при первом входе (`NFR-08`) "
        "и возвращает JWT-токен («пропуск») с ролью пользователя."
    ),
)
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    token, user = await authenticate_with_sms(
        db=db,
        raw_phone=payload.phone,
        code=payload.code,
        consent_accepted=payload.consent_accepted,
    )
    return LoginResponse(
        access_token=token,
        user=UserProfile(
            user_id=user.user_id,
            phone=user.phone,
            full_name=user.full_name,
            role=UserRoleCode(user.role_code),
            company_id=user.company_id,
        ),
    )


@router.get(
    "/me",
    response_model=UserProfile,
    responses=standard_error_responses(401),
    summary="Получить профиль текущего пользователя по JWT",
    description="**Доступ:** `resident`, `dispatcher`, `master`, `manager`.",
)
async def get_me(user: CurrentUser = Depends(get_current_user)) -> UserProfile:
    return UserProfile(
        user_id=user.user_id,
        phone=user.phone,
        full_name=user.full_name,
        role=UserRoleCode(user.role),
        company_id=user.company_id,
    )