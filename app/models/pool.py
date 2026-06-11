import datetime
import uuid

from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.user import Base


class Pool(Base):
    __tablename__ = "pools"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(String(500), default="")
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    invite_code: Mapped[str] = mapped_column(
        String(36), unique=True, default=lambda: str(uuid.uuid4())
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    owner = relationship("User", back_populates="owned_pools")
    members = relationship("PoolMember", back_populates="pool", cascade="all, delete-orphan")
    predictions = relationship("Prediction", back_populates="pool", cascade="all, delete-orphan")


class PoolMember(Base):
    __tablename__ = "pool_members"

    id: Mapped[int] = mapped_column(primary_key=True)
    pool_id: Mapped[int] = mapped_column(ForeignKey("pools.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    joined_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    pool = relationship("Pool", back_populates="members")
    user = relationship("User", back_populates="memberships")
