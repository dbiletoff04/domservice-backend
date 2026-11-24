from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field
from app.schemas.common import RequestStatusCode


class NotificationItemOut(BaseModel):
    notification_id: int
    request_id: int
    request_number: str
    status: RequestStatusCode
    status_name: str
    message_text: str
    state: Literal["new", "sent", "error"]
    attempts: int = Field(..., description="Число попыток отправки")
    created_at: datetime
    sent_at: datetime | None = None
    delivery_delay_seconds: float | None = Field(
        default=None,
        description="Задержка от постановки в очередь до отправки (по NFR-04 <= 60 сек)",
    )