from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer_scheme = HTTPBearer(
    auto_error=False,
    description=(
        "Вставьте демо-токен, полученный в POST /api/auth/login, например:\n"
        "- `demo-resident-token` (Житель)\n"
        "- `demo-dispatcher-token` (Диспетчер)\n"
        "- `demo-master-token` (Мастер)\n"
        "- `demo-manager-token` (Руководитель УК)"
    ),
)


@dataclass(frozen=True)
class DemoUser:
    user_id: int
    phone: str
    full_name: str
    role: str
    company_id: int | None


DEMO_USERS_BY_TOKEN: dict[str, DemoUser] = {
    "demo-resident-token": DemoUser(
        user_id=1,
        phone="+79001112233",
        full_name="Кузнецова А. Д.",
        role="resident",
        company_id=None,
    ),
    "demo-dispatcher-token": DemoUser(
        user_id=2,
        phone="+79002223344",
        full_name="Смирнова Е. В.",
        role="dispatcher",
        company_id=1,
    ),
    "demo-master-token": DemoUser(
        user_id=5,
        phone="+79003334455",
        full_name="Петров И. С.",
        role="master",
        company_id=1,
    ),
    "demo-manager-token": DemoUser(
        user_id=6,
        phone="+79004445566",
        full_name="Волков А. Н.",
        role="manager",
        company_id=1,
    ),
}


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> DemoUser:
    if credentials is None or credentials.credentials not in DEMO_USERS_BY_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется авторизация. Выполните вход через POST /api/auth/login и передайте Bearer-токен.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return DEMO_USERS_BY_TOKEN[credentials.credentials]


def require_roles(*allowed_roles: str):
    def _checker(user: DemoUser = Depends(get_current_user)) -> DemoUser:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Недостаточно прав. Доступ разрешён только для ролей: {', '.join(allowed_roles)}.",
            )
        return user

    return _checker