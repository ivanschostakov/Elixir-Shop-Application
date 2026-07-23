from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.database.mixins import IdPkMixin, TimestampMixin


class CrmLead(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "crm_leads"
    __table_args__ = (
        Index("ix_crm_leads_pipeline", "status", "priority", "next_action_at"),
        Index("ix_crm_leads_owner_status", "owner_user_id", "status"),
        Index("ix_crm_leads_customer_status", "customer_user_id", "status"),
    )

    title: Mapped[str] = mapped_column(String(240), nullable=False)
    source: Mapped[str] = mapped_column(String(48), nullable=False, default="manual", server_default=text("'manual'"), index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="new", server_default=text("'new'"), index=True)
    priority: Mapped[str] = mapped_column(String(24), nullable=False, default="normal", server_default=text("'normal'"), index=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    customer_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    conversation_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("crm_conversations.id", ondelete="SET NULL"), nullable=True, index=True)
    product_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True)
    category_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("product_categories.id", ondelete="SET NULL"), nullable=True, index=True)
    owner_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("admins.user_id", ondelete="SET NULL"), nullable=True, index=True)
    created_by_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("admins.user_id", ondelete="SET NULL"), nullable=True)
    converted_order_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("orders.id", ondelete="SET NULL"), nullable=True, index=True)
    contact_name: Mapped[str | None] = mapped_column(String(240), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_action_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    lost_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    converted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lost_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    customer: Mapped["User | None"] = relationship(foreign_keys=[customer_user_id], back_populates="crm_leads")
    conversation: Mapped["CrmConversation | None"] = relationship(back_populates="leads")
    product: Mapped["Product | None"] = relationship(foreign_keys=[product_id])
    category: Mapped["ProductCategory | None"] = relationship(foreign_keys=[category_id])
    owner: Mapped["Admin | None"] = relationship(foreign_keys=[owner_user_id])
    created_by: Mapped["Admin | None"] = relationship(foreign_keys=[created_by_user_id])
    converted_order: Mapped["Order | None"] = relationship(foreign_keys=[converted_order_id])
    stage_history: Mapped[list["CrmLeadStageHistory"]] = relationship(
        back_populates="lead",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="CrmLeadStageHistory.id",
    )
    notes: Mapped[list["CrmLeadNote"]] = relationship(
        back_populates="lead",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="CrmLeadNote.id",
    )


class CrmLeadStageHistory(Base, IdPkMixin):
    __tablename__ = "crm_lead_stage_history"
    __table_args__ = (Index("ix_crm_lead_stage_history_lead_created", "lead_id", "created_at"),)

    lead_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("crm_leads.id", ondelete="CASCADE"), nullable=False, index=True)
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    changed_by_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("admins.user_id", ondelete="SET NULL"), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    lead: Mapped["CrmLead"] = relationship(back_populates="stage_history")
    changed_by: Mapped["Admin | None"] = relationship(foreign_keys=[changed_by_user_id])


class CrmLeadNote(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "crm_lead_notes"

    lead_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("crm_leads.id", ondelete="CASCADE"), nullable=False, index=True)
    author_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("admins.user_id", ondelete="SET NULL"), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    lead: Mapped["CrmLead"] = relationship(back_populates="notes")
    author: Mapped["Admin | None"] = relationship(foreign_keys=[author_user_id])
