from datetime import date, datetime
from pydantic import BaseModel
from app.schemas.common import RequestStatusCode


class GisReportRowOut(BaseModel):
    request_number: str
    address: str
    apartment: str
    category_name: str
    status: RequestStatusCode
    created_at: datetime
    closed_at: datetime | None = None


class GisReportPreviewOut(BaseModel):
    period_label: str
    start_date: date
    end_date: date
    total_requests: int
    unclosed_requests: int
    requires_review: bool
    warning: str | None = None
    rows: list[GisReportRowOut]