import datetime

from sqlalchemy import Integer, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.user import Base


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (
        UniqueConstraint("user_id", "pool_id", "match_id", name="uq_user_pool_match"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    pool_id: Mapped[int] = mapped_column(ForeignKey("pools.id"))
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"))
    predicted_home: Mapped[int] = mapped_column(Integer)
    predicted_away: Mapped[int] = mapped_column(Integer)
    submitted_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    points_awarded: Mapped[int | None] = mapped_column(Integer, nullable=True)

    user = relationship("User", back_populates="predictions")
    pool = relationship("Pool", back_populates="predictions")
    match = relationship("Match", back_populates="predictions")
