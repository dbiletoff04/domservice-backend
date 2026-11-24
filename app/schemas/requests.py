from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.core.messages import UI_ERROR_PLACE_REQUIRED
from app.schemas.common import RequestStatusCode


class CreateRequestIn(BaseModel):
    address: str = Field(..., description="Адрес дома (не пустой, до 255 символов)")
    apartment: str = Field(..., description="Номер квартиры (не пустой, до 16 символов)")
    category_id: int = Field(..., ge=1, description="ID категории проблемы")
    description: str = Field(..., description="Описание проблемы (не пустое, до 1000 символов)")

    @field_validator("address")
    @classmethod
    def validate_address(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError(UI_ERROR_PLACE_REQUIRED)
        if len(cleaned) < 3:
            raise ValueError("Адрес слишком короткий (минимум 3 символа)")
        if len(cleaned) > 255:
            raise ValueError("Адрес слишком длинный (максимум 255 символов)")
        return cleaned

    @field_validator("apartment")
    @classmethod
    def validate_apartment(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError(UI_ERROR_PLACE_REQUIRED)
        if len(cleaned) > 16:
            raise ValueError("Номер квартиры слишком длинный (максимум 16 символов)")
        return cleaned

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Опишите проблему")
        if len(cleaned) < 3:
            raise ValueError("Описание проблемы слишком короткое (минимум 3 символа)")
        if len(cleaned) > 1000:
            raise ValueError("Описание проблемы слишком длинное (максимум 1000 символов)")
        return cleaned

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "address": "г. Волжский, ул. Ленина, д. 97",
                "apartment": "42",
                "category_id": 1,
                "description": "Протекает кран на кухне под раковиной",
            }
        }
    )


class DispatcherCreateRequestIn(CreateRequestIn):
    phone: str = Field(..., min_length=10, max_length=20, description="Телефон звонящего жителя")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "phone": "+79001112233",
                "address": "г. Волжский, ул. Ленина, д. 97",
                "apartment": "42",
                "category_id": 1,
                "description": "Заявка принята по телефону: свищ на трубе",
            }
        }
    )


class RequestCreatedOut(BaseModel):
    request_id: int
    request_number: str
    status: RequestStatusCode
    status_name: str
    deadline_display: str = "Уточняется"
    created_at: datetime
    message: str = "Заявка принята"


class RequestSummaryOut(BaseModel):
    request_id: int
    request_number: str
    category_name: str
    address: str
    apartment: str
    status: RequestStatusCode
    status_name: str
    deadline_at: datetime | None = None
    deadline_display: str
    created_at: datetime


class StatusHistoryItemOut(BaseModel):
    history_id: int
    from_status: RequestStatusCode | None = None
    to_status: RequestStatusCode
    to_status_name: str
    actor_name: str
    comment: str | None = None
    changed_at: datetime


class RequestDetailOut(BaseModel):
    request_id: int
    request_number: str
    address: str
    apartment: str
    category_id: int
    category_name: str
    description: str
    status: RequestStatusCode
    status_name: str
    master_name: str | None = None
    resident_phone: str | None = Field(
        default=None, description="Телефон жителя (передаётся мастеру и диспетчеру)"
    )
    deadline_at: datetime | None = None
    deadline_display: str
    created_at: datetime
    updated_at: datetime
    history: list[StatusHistoryItemOut]


class ConfirmWorkIn(BaseModel):
    resolution: Literal["accepted"] = "accepted"


class RejectWorkIn(BaseModel):
    comment: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="Обязательный комментарий: что именно не решено",
    )

    model_config = ConfigDict(
        json_schema_extra={"example": {"comment": "Кран всё ещё подтекает после ухода мастера"}}
    )


class AssignMasterIn(BaseModel):
    master_id: int = Field(..., ge=1, description="ID мастера")
    deadline_at: datetime | None = Field(
        default=None, description="Плановый срок выполнения (если не задан — «Уточняется»)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "master_id": 5,
                "deadline_at": "2026-11-12T12:00:00+03:00",
            }
        }
    )


class CompleteTaskIn(BaseModel):
    status: Literal["completed"] = "completed"


class RequestStatusActionOut(BaseModel):
    request_id: int
    request_number: str
    status: RequestStatusCode
    status_name: str
    master_id: int | None = None
    deadline_at: datetime | None = None
    deadline_display: str | None = None
    comment: str | None = None


class DispatcherRequestItemOut(RequestSummaryOut):
    master_name: str | None = None
    last_comment: str | None = None


class MasterTaskItemOut(BaseModel):
    request_id: int
    request_number: str
    address: str
    apartment: str
    description: str
    resident_phone: str
    status: RequestStatusCode
    status_name: str
    is_returned: bool = False
    return_comment: str | None = None
    deadline_display: str