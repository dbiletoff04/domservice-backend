from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    desc,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Request(Base):
    __tablename__ = "request"
    __table_args__ = (
        Index("ix_request_status_code", "status_code"),
        Index("ix_request_resident_id", "resident_id"),
        Index("ix_request_master_id", "master_id"),
        Index("ix_request_company_status", "company_id", "status_code"),
        Index("ix_request_created_at", desc("created_at")),
    )

    request_id: Mapped[int] = mapped_column(
        Integer, Identity(always=False), primary_key=True
    )
    request_number: Mapped[str] = mapped_column(
        String(16), nullable=False, unique=True
    )
    resident_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("app_user.user_id", onupdate="CASCADE", ondelete="RESTRICT"),
        nullable=False,
    )
    company_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "management_company.company_id", onupdate="CASCADE", ondelete="RESTRICT"
        ),
        nullable=False,
    )
    category_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "problem_category.category_id", onupdate="CASCADE", ondelete="RESTRICT"
        ),
        nullable=False,
    )
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    apartment: Mapped[str] = mapped_column(String(16), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), nullable=False)
    status_code: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("request_status.status_code", onupdate="CASCADE", ondelete="RESTRICT"),
        nullable=False,
        default="accepted",
        server_default="accepted",
    )
    master_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("app_user.user_id", onupdate="CASCADE", ondelete="SET NULL"),
        nullable=True,
    )
    deadline_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    resident = relationship("AppUser", foreign_keys=[resident_id], lazy="selectin")
    master = relationship("AppUser", foreign_keys=[master_id], lazy="selectin")
    company = relationship("ManagementCompany", lazy="selectin")
    category = relationship("ProblemCategory", lazy="joined")
    status = relationship("RequestStatus", lazy="joined")
    history = relationship(
        "RequestStatusHistory",
        back_populates="request",
        order_by="RequestStatusHistory.changed_at",
        lazy="selectin",
    )
    notifications = relationship(
        "Notification",
        back_populates="request",
        order_by="Notification.created_at",
        lazy="selectin",
    )


class RequestStatusHistory(Base):
    __tablename__ = "request_status_history"
    __table_args__ = (
        Index("ix_history_request_changed", "request_id", "changed_at"),
    )

    history_id: Mapped[int] = mapped_column(
        Integer, Identity(always=False), primary_key=True
    )
    request_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("request.request_id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
    )
    from_status_code: Mapped[str | None] = mapped_column(
        String(32),
        ForeignKey("request_status.status_code", onupdate="CASCADE", ondelete="RESTRICT"),
        nullable=True,
    )
    to_status_code: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("request_status.status_code", onupdate="CASCADE", ondelete="RESTRICT"),
        nullable=False,
    )
    actor_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("app_user.user_id", onupdate="CASCADE", ondelete="RESTRICT"),
        nullable=False,
    )
    comment: Mapped[str | None] = mapped_column(String(500), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    request = relationship("Request", back_populates="history")
    from_status = relationship("RequestStatus", foreign_keys=[from_status_code])
    to_status = relationship("RequestStatus", foreign_keys=[to_status_code])
    actor = relationship("AppUser", foreign_keys=[actor_id])


class Notification(Base):
    __tablename__ = "notification"
    __table_args__ = (
        CheckConstraint(
            "state IN ('new', 'sent', 'error')", name="chk_notification_state"
        ),
        CheckConstraint("attempts >= 0", name="chk_notification_attempts"),
        Index("ix_notification_state_created", "state", "created_at"),
        Index("ix_notification_recipient_created", "recipient_id", desc("created_at")),
    )

    notification_id: Mapped[int] = mapped_column(
        Integer, Identity(always=False), primary_key=True
    )
    request_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("request.request_id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
    )
    recipient_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("app_user.user_id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
    )
    status_code: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("request_status.status_code", onupdate="CASCADE", ondelete="RESTRICT"),
        nullable=False,
    )
    message_text: Mapped[str] = mapped_column(String(500), nullable=False)
    state: Mapped[str] = mapped_column(
        String(16), nullable=False, default="new", server_default="new"
    )
    attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    request = relationship("Request", back_populates="notifications")
    recipient = relationship("AppUser", foreign_keys=[recipient_id])
    status = relationship("RequestStatus", foreign_keys=[status_code])