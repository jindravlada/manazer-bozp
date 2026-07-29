from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class Employer(Base):
    __tablename__ = "employers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    ico: Mapped[str] = mapped_column(String(20), default="")
    name: Mapped[str] = mapped_column(String(250), nullable=False)
    address: Mapped[str] = mapped_column(String(300), default="")
    nace: Mapped[str] = mapped_column(String(50), default="")
    abbreviation: Mapped[str] = mapped_column(String(32), default="")

    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
