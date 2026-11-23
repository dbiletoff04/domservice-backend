from datetime import datetime
from typing import Literal
from pydantic import BaseModel
from app.schemas.common import RequestStatusCode


class NotificationItemOut(BaseModel):
    notification_id: int
    request_id: int
    request_number: str
    status: RequestStatusCode
    status_name: str
    message_text: str
    state: Literal["new", "sent", "error"]
    created_at: datetime
    sent_at: datetime | None = None