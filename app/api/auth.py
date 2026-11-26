from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import CurrentUser, get_current_user
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RequestCodeIn,
    RequestCodeOut,
    UserProfile,
)
from app.schemas.common import UserRoleCode, standard_error_responses
from app.services.auth_service import (
    authenticate_with_sms,
    issue_login_code,
    issue_register_code,
    register_resident,
)

router = APIRouter(prefix="/auth", tags=["Аутентификация и регистрация (F-01)"])


@router.post(
    "/request-code",
    response_model=RequestCodeOut,
    responses=standard_error_responses(404),
    summary="Авторизация: шаг 1 — запросить код для входа",
    description=(
        "**Доступ:** публичный.\n\n"
        "Ищет **существующего** пользователя в БД по номеру телефона (с `+7`, `8` или `7`).\n"
        "Если номера нет в базе — новых записей не создаёт и возвращает `404` («Введённый номер телефона не существует»)."
    ),
)
async def request_login_code(
    payload: RequestCodeIn,
    db: AsyncSession = Depends(get_db),
) -> RequestCodeOut:
    phone, ttl = await issue_login_code(db, payload.phone)
    return RequestCodeOut(phone=phone, expires_in_seconds=ttl)


@router.post(
    "/login",
    response_model=LoginResponse,
    responses=standard_error_responses(400, 404),
    summary="Авторизация: шаг 2 — вход существующего пользователя по коду",
    description=(
        "**Доступ:** публичный.\n\n"
        "Выполняет вход в **существующий** аккаунт по номеру телефона и СМС-коду. "
        "Согласие на ПДн при повторном входе не запрашивается, новых пользователей не создаётся."
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


@router.post(
    "/register/request-code",
    response_model=RequestCodeOut,
    responses=standard_error_responses(409),
    summary="Регистрация: шаг 1 — запросить код для нового жителя",
    description=(
        "**Доступ:** публичный.\n\n"
        "Проверяет корректность номера и то, что пользователь с таким телефоном ещё не зарегистрирован (`409`, если уже есть). "
        "Записывает одноразовый код подтверждения в журнал сервера."
    ),
)
async def request_registration_code(
    payload: RequestCodeIn,
    db: AsyncSession = Depends(get_db),
) -> RequestCodeOut:
    phone, ttl = await issue_register_code(db, payload.phone)
    return RequestCodeOut(phone=phone, expires_in_seconds=ttl)


@router.post(
    "/register",
    response_model=LoginResponse,
    status_code=status.HTTP_201_CREATED,
    responses=standard_error_responses(400, 409),
    summary="Регистрация: шаг 2 — создать аккаунт нового жителя",
    description=(
        "**Доступ:** публичный.\n\n"
        "Регистрирует нового жителя в БД с обязательным заполнением **ФИО** (`full_name`) "
        "и обязательным согласием на обработку ПДн (`consent_accepted=true`, `NFR-08`). "
        "Сразу выдает JWT-токен для работы в системе."
    ),
)
async def register(
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    token, user = await register_resident(
        db=db,
        raw_phone=payload.phone,
        full_name=payload.full_name,
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