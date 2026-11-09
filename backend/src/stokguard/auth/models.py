from uuid import uuid4

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from stokguard.core.db import Base


def new_id() -> str:
    return str(uuid4())


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    username: Mapped[str] = mapped_column(unique=True)
    password_hash: Mapped[str]
    active: Mapped[bool] = mapped_column(default=True)


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("user_id", "business_id"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"))
    role: Mapped[str]


class AuthSession(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    token_hash: Mapped[str] = mapped_column(unique=True)
    csrf_token: Mapped[str]
    issued_at: Mapped[str]
    expires_at: Mapped[str]
    revoked: Mapped[bool] = mapped_column(default=False)
