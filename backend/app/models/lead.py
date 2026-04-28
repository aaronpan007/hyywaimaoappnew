from sqlalchemy import Float, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Lead(Base, TimestampMixin):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("tasks.id"), nullable=False)
    company_name: Mapped[str] = mapped_column(Text, nullable=False, default="")
    website: Mapped[str] = mapped_column(Text, nullable=False, default="")
    country: Mapped[str] = mapped_column(Text, nullable=False, default="")
    industry: Mapped[str] = mapped_column(Text, nullable=False, default="")
    company_role: Mapped[str] = mapped_column(Text, nullable=False, default="")
    contact_name: Mapped[str] = mapped_column(Text, nullable=False, default="")
    email: Mapped[str] = mapped_column(Text, nullable=False, default="")
    phone: Mapped[str] = mapped_column(Text, nullable=False, default="")
    ai_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    business_match: Mapped[str] = mapped_column(Text, nullable=False, default="")
    outreach_suggestion: Mapped[str] = mapped_column(Text, nullable=False, default="")
    match_score: Mapped[float] = mapped_column(Float, nullable=False, default=0)
