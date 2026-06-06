import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, Integer, Text, Numeric, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB


def gen_uuid() -> str:
    return str(uuid.uuid4())


def utcnow():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Branch(Base):
    __tablename__ = "branches"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    name = Column(Text, nullable=False)
    address = Column(Text, default="", server_default="")
    gst_percent = Column(Numeric, default=18, server_default="18")
    created_at = Column(DateTime(timezone=True), default=utcnow)


class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    username = Column(Text, nullable=False)
    password_hash = Column(Text, nullable=False)
    role = Column(Text, nullable=False)  # admin | manager | user
    branch_id = Column(UUID(as_uuid=False), ForeignKey("branches.id", ondelete="CASCADE"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("username", "role", name="users_username_role_unique"),)


class Category(Base):
    __tablename__ = "categories"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    branch_id = Column(UUID(as_uuid=False), ForeignKey("branches.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(Text, nullable=False)
    sort_order = Column(Integer, default=0, server_default="0")


class MenuItem(Base):
    __tablename__ = "menu_items"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    branch_id = Column(UUID(as_uuid=False), ForeignKey("branches.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id = Column(UUID(as_uuid=False), ForeignKey("categories.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(Text, nullable=False)
    price = Column(Numeric, nullable=False)


class Booking(Base):
    __tablename__ = "bookings"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    branch_id = Column(UUID(as_uuid=False), ForeignKey("branches.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_name = Column(Text, nullable=False)
    phone = Column(Text, nullable=False)
    num_people = Column(Integer, nullable=False)
    venue_type = Column(Text, nullable=False)  # in_house | outside
    venue_address = Column(Text, default="", server_default="")
    event_date = Column(Text, nullable=False, index=True)  # YYYY-MM-DD
    event_time = Column(Text, nullable=False)  # HH:MM
    event_end_time = Column(Text, nullable=False)
    # Absolute timestamps used for conflict detection. Handles overnight events
    # (where event_end_time <= event_time, end is +1 day).
    start_at = Column(DateTime(timezone=True), nullable=True, index=True)
    end_at = Column(DateTime(timezone=True), nullable=True, index=True)
    items = Column(JSONB, nullable=False, server_default="[]")
    discount_amount = Column(Numeric, default=0, server_default="0")
    discount_percent = Column(Numeric, default=0, server_default="0")
    transportation_cost = Column(Numeric, default=0, server_default="0")
    advance_paid = Column(Numeric, default=0, server_default="0")
    gst_percent = Column(Numeric, default=18, server_default="18")
    notes = Column(Text, default="", server_default="")
    status = Column(Text, default="booked", server_default="booked", index=True)
    created_by = Column(Text)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (
        Index("ix_bookings_branch_date", "branch_id", "event_date"),
    )


class Settings(Base):
    __tablename__ = "settings"
    id = Column(Text, primary_key=True, default="global")
    company_logo = Column(Text, default="", server_default="")
