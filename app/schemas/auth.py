from pydantic import BaseModel, ConfigDict, Field
from app.schemas.common import UserRoleCode


class RequestCodeIn(BaseModel):
    phone: str = Field(..., min_length=10, max_length=20, description="Номер телефона пользователя")

    model_config = ConfigDict(
        json_schema_extra={"example": {"phone": "+79001112233"}}
    )


class RequestCodeOut(BaseModel):
    phone: str
    expires_in_seconds: int
    message: str = "Одноразовый код сформирован и записан в журнал сервера"


class LoginRequest(BaseModel):
    phone: str = Field(..., min_length=10, max_length=20, description="Номер телефона пользователя")
    code: str = Field(..., min_length=4, max_length=6, description="Одноразовый СМС-код из журнала сервера")
    consent_accepted: bool = Field(
        default=False,
        description="Согласие на обработку ПДн по ФЗ-152 (обязательно true при первом входе — NFR-08)",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "phone": "+79001112233",
                "code": "1234",
                "consent_accepted": True,
            }
        }
    )


class UserProfile(BaseModel):
    user_id: int
    phone: str
    full_name: str | None = None
    role: UserRoleCode
    company_id: int | None = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfile