from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Identity, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AppUser(Base):
    __tablename__ = "app_user"
    __table_args__ = (
        Index("ix_app_user_role_code", "role_code"),
        Index("ix_app_user_company_id", "company_id"),
    )

    user_id: Mapped[int] = mapped_column(
        Integer, Identity(always=False), primary_key=True
    )
    phone: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    full_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    role_code: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("user_role.role_code", onupdate="CASCADE", ondelete="RESTRICT"),
        nullable=False,
    )
    company_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "management_company.company_id", onupdate="CASCADE", ondelete="SET NULL"
        ),
        nullable=True,
    )
    consent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    role = relationship("UserRole", lazy="joined")
    company = relationship("ManagementCompany", lazy="selectin")