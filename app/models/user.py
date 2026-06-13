import datetime

from sqlalchemy import Boolean, Integer, String, DateTime, func, true
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(100))
    # When True, saving a prediction copies it to every pool the user belongs to.
    mirror_predictions: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=true()
    )
    # Bumped on logout to invalidate every previously issued session token.
    token_version: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    owned_pools = relationship("Pool", back_populates="owner")
    memberships = relationship("PoolMember", back_populates="user")
    predictions = relationship("Prediction", back_populates="user")
