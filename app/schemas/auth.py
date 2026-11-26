from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.schemas.common import UserRoleCode


class RequestCodeIn(BaseModel):
    phone: str = Field(..., min_length=1, max_length=20, description="Номер телефона пользователя")

    model_config = ConfigDict(
        json_schema_extra={"example": {"phone": "79001112233"}}
    )


class RequestCodeOut(BaseModel):
    phone: str
    expires_in_seconds: int
    message: str = "Одноразовый код сформирован и записан в журнал сервера"


class LoginRequest(BaseModel):
    phone: str = Field(..., min_length=1, max_length=20, description="Номер телефона существующего пользователя")
    code: str = Field(..., min_length=4, max_length=6, description="Одноразовый СМС-код из журнала сервера")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "phone": "79001112233",
                "code": "1234",
            }
        }
    )


class RegisterRequest(BaseModel):
    phone: str = Field(..., min_length=1, max_length=20, description="Номер телефона нового жителя")
    full_name: str = Field(..., description="ФИО жителя (обязательно, 2–128 символов)")
    code: str = Field(..., min_length=4, max_length=6, description="Одноразовый СМС-код из журнала сервера")
    consent_accepted: bool = Field(
        ...,
        description="Согласие на обработку ПДн по ФЗ-152 (без true регистрация невозможна)",
    )

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str) -> str:
        cleaned = " ".join(value.strip().split())
        if not cleaned:
            raise ValueError("Укажите ФИО")
        if len(cleaned) < 2:
            raise ValueError("ФИО слишком короткое (минимум 2 символа)")
        if len(cleaned) > 128:
            raise ValueError("ФИО слишком длинное (максимум 128 символов)")
        return cleaned

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "phone": "89093914793",
                "full_name": "Соколова Мария Сергеевна",
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
    consent_at: datetime | None = Field(
        default=None,
        description="Дата и время согласия пользователя на обработку персональных данных",
    )


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfile