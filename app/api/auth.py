from fastapi import APIRouter, Depends, HTTPException, status
from app.core.security import DEMO_USERS_BY_TOKEN, DemoUser, get_current_user
from app.schemas.auth import LoginRequest, LoginResponse, UserProfile
from app.schemas.common import UserRoleCode, standard_error_responses

router = APIRouter(prefix="/auth", tags=["Аутентификация (F-01)"])

PHONE_TO_TOKEN = {
    "+79001112233": "demo-resident-token",
    "+79002223344": "demo-dispatcher-token",
    "+79003334455": "demo-master-token",
    "+79004445566": "demo-manager-token",
}


@router.post(
    "/login",
    response_model=LoginResponse,
    responses=standard_error_responses(400),
    summary="Вход по номеру телефона и СМС-коду",
    description=(
        "**Доступ:** публичный.\n\n"
        "**Тестовые аккаунты (код `1234`):**\n"
        "- `+79001112233` — Житель (`resident`)\n"
        "- `+79002223344` — Диспетчер (`dispatcher`)\n"
        "- `+79003334455` — Мастер (`master`)\n"
        "- `+79004445566` — Руководитель УК (`manager`)\n\n"
        "Без `consent_accepted=true` вход запрещён (NFR-08, ФЗ-152)."
    ),
)
async def login(payload: LoginRequest) -> LoginResponse:
    if not payload.consent_accepted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Необходимо согласие на обработку персональных данных (ФЗ-152)",
        )
    if payload.code != "1234":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный СМС-код (для тестовых данных используйте 1234)",
        )

    token = PHONE_TO_TOKEN.get(payload.phone, "demo-resident-token")
    demo_user = DEMO_USERS_BY_TOKEN[token]
    return LoginResponse(
        access_token=token,
        user=UserProfile(
            user_id=demo_user.user_id,
            phone=payload.phone if payload.phone not in PHONE_TO_TOKEN else demo_user.phone,
            full_name=demo_user.full_name,
            role=UserRoleCode(demo_user.role),
            company_id=demo_user.company_id,
        ),
    )


@router.get(
    "/me",
    response_model=UserProfile,
    responses=standard_error_responses(401),
    summary="Получить профиль текущего пользователя",
    description="**Доступ:** `resident`, `dispatcher`, `master`, `manager`.",
)
async def get_me(user: DemoUser = Depends(get_current_user)) -> UserProfile:
    return UserProfile(
        user_id=user.user_id,
        phone=user.phone,
        full_name=user.full_name,
        role=UserRoleCode(user.role),
        company_id=user.company_id,
    )