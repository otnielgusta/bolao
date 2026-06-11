import datetime

from sqlalchemy import String, DateTime, Integer, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.user import Base


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(primary_key=True)
    home_team: Mapped[str] = mapped_column(String(100))
    away_team: Mapped[str] = mapped_column(String(100))
    match_datetime: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    stage: Mapped[str] = mapped_column(String(50))
    home_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    allow_retroactive: Mapped[bool] = mapped_column(Boolean, default=False)
    is_finished: Mapped[bool] = mapped_column(Boolean, default=False)
    external_id: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    predictions = relationship("Prediction", back_populates="match")
