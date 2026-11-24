from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.user import AppUser

bearer_scheme = HTTPBearer(
    auto_error=False,
    description="Передайте JWT-токен («пропуск»), полученный в POST /api/auth/login.",
)


@dataclass(frozen=True)
class CurrentUser:
    user_id: int
    phone: str
    full_name: str | None
    role: str
    company_id: int | None
    consent_at: datetime | None = None


def create_access_token(user: AppUser) -> str:
    now = datetime.now(timezone.utc)
    expire_at = now + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": str(user.user_id),
        "phone": user.phone,
        "role": user.role_code,
        "company_id": user.company_id,
        "iat": now,
        "exp": expire_at,
    }
    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Срок действия пропуска (JWT) истёк. Войдите в систему заново.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный пропуск (JWT-токен).",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется авторизация. Получите JWT-токен через POST /api/auth/login.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials)
    sub = payload.get("sub")
    if sub is None or not str(sub).isdigit():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Некорректный идентификатор пользователя в токене.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await db.scalar(select(AppUser).where(AppUser.user_id == int(sub)))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь из токена не найден в системе.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return CurrentUser(
        user_id=user.user_id,
        phone=user.phone,
        full_name=user.full_name,
        role=user.role_code,
        company_id=user.company_id,
        consent_at=user.consent_at,
    )


def require_roles(*allowed_roles: str):
    async def _checker(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Недостаточно прав для роли «{user.role}». "
                    f"Доступ разрешён только для: {', '.join(allowed_roles)}."
                ),
            )
        return user

    return _checker