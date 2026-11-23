from pydantic import BaseModel
from app.schemas.common import RequestStatusCode


class StatusReferenceItem(BaseModel):
    status_code: RequestStatusCode
    name: str
    description: str


class CategoryReferenceItem(BaseModel):
    category_id: int
    name: str
    is_active: bool = True