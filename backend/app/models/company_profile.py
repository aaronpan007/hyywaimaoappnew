from sqlalchemy import Boolean, ForeignKey, Integer, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class CompanyProfile(Base, TimestampMixin):
    __tablename__ = "company_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    task_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("tasks.id"), nullable=True
    )
    company_name: Mapped[str] = mapped_column(Text, nullable=False, default="")
    profile_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    profile_markdown: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
