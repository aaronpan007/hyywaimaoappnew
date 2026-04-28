from sqlalchemy import DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class OutreachEmail(Base, TimestampMixin):
    __tablename__ = "outreach_emails"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lead_id: Mapped[int] = mapped_column(Integer, ForeignKey("leads.id"), nullable=False)
    task_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("tasks.id"), nullable=True
    )
    email_subject: Mapped[str] = mapped_column(Text, nullable=False, default="")
    email_body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    send_status: Mapped[str] = mapped_column(Text, nullable=False, default="draft")
    sent_at: Mapped[str | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[str] = mapped_column(Text, nullable=False, default="")
