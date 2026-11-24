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
        "Генерирует 4-значный одноразовый код в журнал программы и сообщает флаг `requires_consent` — "
        "нужно ли запрашивать согласие на обработку ПДн (при первом входе)."
    ),
)
async def request_sms_code(
    payload: RequestCodeIn,
    db: AsyncSession = Depends(get_db),
) -> RequestCodeOut:
    phone, ttl, requires_consent = await issue_sms_code(db, payload.phone)
    return RequestCodeOut(
        phone=phone,
        expires_in_seconds=ttl,
        requires_consent=requires_consent,
    )


@router.post(
    "/login",
    response_model=LoginResponse,
    responses=standard_error_responses(400),
    summary="Вход по номеру телефона и СМС-коду с проверкой согласия на ПДн",
    description=(
        "**Доступ:** публичный.\n\n"
        "При первом входе требует `consent_accepted=true` (ФЗ-152, NFR-08), записывает дату согласия "
        "`consent_at` в базу данных и выдаёт JWT-токен с ролью пользователя."
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
            consent_at=user.consent_at,
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
        consent_at=user.consent_at,
    )