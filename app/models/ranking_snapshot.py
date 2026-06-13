import datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.user import Base


class RankingSnapshot(Base):
    __tablename__ = "ranking_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "pool_id",
            "match_id",
            "user_id",
            name="uq_ranking_snapshot_pool_match_user",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    pool_id: Mapped[int] = mapped_column(ForeignKey("pools.id"))
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    snapshot_date: Mapped[datetime.date] = mapped_column(Date)
    position: Mapped[int] = mapped_column(Integer)
    total: Mapped[int] = mapped_column(Integer)
    count_10: Mapped[int] = mapped_column(Integer, default=0)
    count_7: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
