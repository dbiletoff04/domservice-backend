from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field


class UserRoleCode(StrEnum):
    RESIDENT = "resident"
    DISPATCHER = "dispatcher"
    MASTER = "master"
    MANAGER = "manager"


class RequestStatusCode(StrEnum):
    ACCEPTED = "accepted"
    MASTER_ASSIGNED = "master_assigned"
    PENDING_CONFIRMATION = "pending_confirmation"
    CLOSED = "closed"
    RETURNED = "returned"


STATUS_NAMES: dict[RequestStatusCode, str] = {
    RequestStatusCode.ACCEPTED: "Принята",
    RequestStatusCode.MASTER_ASSIGNED: "Мастер назначен",
    RequestStatusCode.PENDING_CONFIRMATION: "Ожидает подтверждения",
    RequestStatusCode.CLOSED: "Закрыта",
    RequestStatusCode.RETURNED: "Возвращена",
}


class ErrorResponse(BaseModel):
    detail: str = Field(..., description="Понятное описание ошибки")

    model_config = ConfigDict(
        json_schema_extra={"example": {"detail": "Заявка с указанным ID не найдена"}}
    )


def standard_error_responses(*codes: int) -> dict[int, dict]:
    examples = {
        400: ("Неверный запрос / нарушение бизнес-правила", {"detail": "Необходимо подтвердить согласие на обработку персональных данных"}),
        401: ("Пользователь не авторизован", {"detail": "Требуется авторизация. Передайте Bearer-токен."}),
        403: ("Доступ запрещён (нет прав или чужая заявка)", {"detail": "Доступ к чужой заявке запрещён (NFR-07)"}),
        404: ("Объект не найден", {"detail": "Заявка не найдена"}),
        409: ("Конфликт статуса заявки", {"detail": "Действие недопустимо для текущего статуса заявки"}),
    }
    return {
        code: {
            "model": ErrorResponse,
            "description": examples[code][0],
            "content": {"application/json": {"example": examples[code][1]}},
        }
        for code in codes
        if code in examples
    }