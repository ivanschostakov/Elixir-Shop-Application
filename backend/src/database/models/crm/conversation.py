from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from config import SUPPORT_MEDIA_DIR
from src.database import Base
from src.database.mixins import IdPkMixin, TimestampMixin


class CrmConversation(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "crm_conversations"
    __table_args__ = (
        Index("ix_crm_conversations_queue", "status", "priority", "last_message_at"),
        Index("ix_crm_conversations_assignee_status", "assignee_user_id", "status"),
        Index("ix_crm_conversations_customer_status", "customer_user_id", "status"),
        Index("ix_crm_conversations_sla", "status", "response_due_at", "resolution_due_at"),
        Index(
            "uq_crm_conversations_active_customer_channel",
            "customer_user_id",
            "channel",
            unique=True,
            postgresql_where=text("status NOT IN ('resolved', 'spam')"),
        ),
    )

    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="app_support", server_default=text("'app_support'"))
    customer_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    subject: Mapped[str | None] = mapped_column(String(240), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="new", server_default=text("'new'"), index=True)
    priority: Mapped[str] = mapped_column(String(24), nullable=False, default="normal", server_default=text("'normal'"), index=True)
    assignee_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("admins.user_id", ondelete="SET NULL"), nullable=True, index=True)
    sla_policy_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("admin_sla_policies.id", ondelete="SET NULL"), nullable=True, index=True)
    order_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("orders.id", ondelete="SET NULL"), nullable=True, index=True)

    response_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    customer_last_read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    admin_last_read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sla_breached_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    customer_unread_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    admin_unread_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))

    customer: Mapped["User"] = relationship(foreign_keys=[customer_user_id], back_populates="support_conversations")
    assignee: Mapped["Admin | None"] = relationship(foreign_keys=[assignee_user_id])
    sla_policy: Mapped["AdminSlaPolicy | None"] = relationship(foreign_keys=[sla_policy_id])
    order: Mapped["Order | None"] = relationship(foreign_keys=[order_id])
    messages: Mapped[list["CrmMessage"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="CrmMessage.id",
    )
    assignment_history: Mapped[list["CrmAssignmentHistory"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="CrmAssignmentHistory.id",
    )
    leads: Mapped[list["CrmLead"]] = relationship(back_populates="conversation")


class CrmMessage(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "crm_messages"
    __table_args__ = (
        Index("ix_crm_messages_conversation_created", "conversation_id", "created_at"),
        Index("ix_crm_messages_sender_created", "sender_type", "created_at"),
    )

    conversation_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("crm_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_type: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    admin_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("admins.user_id", ondelete="SET NULL"), nullable=True, index=True)
    client_message_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True, unique=True)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default=text("''"))
    is_internal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    conversation: Mapped["CrmConversation"] = relationship(back_populates="messages")
    user: Mapped["User | None"] = relationship(foreign_keys=[user_id])
    admin: Mapped["Admin | None"] = relationship(foreign_keys=[admin_user_id])
    attachments: Mapped[list["CrmMessageAttachment"]] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="CrmMessageAttachment.id",
    )


class CrmMessageAttachment(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "crm_message_attachments"

    message_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("crm_messages.id", ondelete="CASCADE"), nullable=False, index=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False, default=lambda: uuid4().hex)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)

    message: Mapped["CrmMessage"] = relationship(back_populates="attachments")

    @property
    def relative_path(self) -> Path:
        return Path(str(self.message.conversation_id)) / str(self.message_id) / self.filename

    @property
    def path(self) -> Path:
        return SUPPORT_MEDIA_DIR / self.relative_path


class CrmAssignmentHistory(Base, IdPkMixin):
    __tablename__ = "crm_assignment_history"
    __table_args__ = (Index("ix_crm_assignment_history_conversation_created", "conversation_id", "created_at"),)

    conversation_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("crm_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    from_admin_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("admins.user_id", ondelete="SET NULL"), nullable=True)
    to_admin_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("admins.user_id", ondelete="SET NULL"), nullable=True)
    changed_by_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("admins.user_id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    conversation: Mapped["CrmConversation"] = relationship(back_populates="assignment_history")
    from_admin: Mapped["Admin | None"] = relationship(foreign_keys=[from_admin_user_id])
    to_admin: Mapped["Admin | None"] = relationship(foreign_keys=[to_admin_user_id])
    changed_by: Mapped["Admin | None"] = relationship(foreign_keys=[changed_by_user_id])
