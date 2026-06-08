from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    BigInteger, 
    Boolean, 
    Column, 
    DateTime, 
    ForeignKey, 
    Integer, 
    String, 
    Text, 
    func,
    Index
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models with common timestamp fields."""
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(255))
    username: Mapped[Optional[str]] = mapped_column(String(255))
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_seen: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    requests: Mapped[List["Request"]] = relationship(back_populates="user")


class Admin(Base):
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    added_by: Mapped[Optional[int]] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Service(Base):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    group_id: Mapped[int] = mapped_column(BigInteger, index=True)
    reply_to_message_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    message_link: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    total_requests: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    requests: Mapped[List["Request"]] = relationship(back_populates="service")


class Request(Base):
    __tablename__ = "requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"), index=True)
    mobile_number: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", index=True)
    result_text: Mapped[Optional[str]] = mapped_column(Text)
    group_message_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    user_message_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    is_bulk: Mapped[bool] = mapped_column(Boolean, default=False)
    extra_data: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="requests")
    service: Mapped["Service"] = relationship(back_populates="requests")

# Multi-column index for matching logic: service_id + mobile_number + status=PENDING
Index("idx_request_matching", Request.service_id, Request.mobile_number, Request.status)
