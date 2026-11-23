from datetime import datetime

from sqlalchemy import Boolean, DateTime, Identity, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserRole(Base):
    __tablename__ = "user_role"

    role_code: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)


class RequestStatus(Base):
    __tablename__ = "request_status"

    status_code: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)


class ManagementCompany(Base):
    __tablename__ = "management_company"

    company_id: Mapped[int] = mapped_column(
        Integer, Identity(always=False), primary_key=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    contact_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ProblemCategory(Base):
    __tablename__ = "problem_category"

    category_id: Mapped[int] = mapped_column(
        Integer, Identity(always=False), primary_key=True
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )