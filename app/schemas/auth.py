from pydantic import BaseModel, ConfigDict, Field
from app.schemas.common import UserRoleCode


class LoginRequest(BaseModel):
    phone: str = Field(..., min_length=10, max_length=20, description="Номер телефона пользователя")
    code: str = Field(..., min_length=4, max_length=6, description="Одноразовый СМС-код (для демо: 1234)")
    consent_accepted: bool = Field(
        ...,
        description="Согласие на обработку ПДн по ФЗ-152 (NFR-08; без true первый вход запрещён)",
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

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "demo-resident-token",
                "token_type": "bearer",
                "user": {
                    "user_id": 1,
                    "phone": "+79001112233",
                    "full_name": "Кузнецова А. Д.",
                    "role": "resident",
                    "company_id": None,
                },
            }
        }
    )