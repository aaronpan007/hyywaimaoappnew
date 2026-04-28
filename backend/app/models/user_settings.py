from sqlalchemy import DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UserSettings(Base):
    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    sender_name: Mapped[str] = mapped_column(Text, nullable=False, default="")
    from_email_prefix: Mapped[str] = mapped_column(Text, nullable=False, default="")
    reply_to_email: Mapped[str] = mapped_column(Text, nullable=False, default="")
    profile_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("company_profiles.id"), nullable=True
    )
    updated_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
