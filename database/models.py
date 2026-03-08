"""
SQLAlchemy ORM models.

Tables:
    users        – Telegram/WhatsApp user profiles
    search_logs  – Every search request for analytics
    bookings     – Confirmed bookings
    tickets      – Issued ticket details
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Integer, Float, Boolean,
    DateTime, Text, ForeignKey, JSON, Enum as SAEnum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from database.db import Base


# ─── Enums ────────────────────────────────────────────────────────────────────

class TravelType(str, enum.Enum):
    train = "train"
    flight = "flight"
    hotel = "hotel"


class BookingStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    cancelled = "cancelled"
    failed = "failed"


class Platform(str, enum.Enum):
    telegram = "telegram"
    whatsapp = "whatsapp"


# ─── Models ───────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    platform = Column(SAEnum(Platform), nullable=False)
    platform_user_id = Column(String(64), nullable=False, index=True)
    username = Column(String(128), nullable=True)
    full_name = Column(String(256), nullable=True)
    phone = Column(String(32), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    bookings = relationship("Booking", back_populates="user")
    search_logs = relationship("SearchLog", back_populates="user")

    def __repr__(self):
        return f"<User {self.platform}:{self.platform_user_id}>"


class SearchLog(Base):
    __tablename__ = "search_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    travel_type = Column(SAEnum(TravelType), nullable=False)
    origin = Column(String(128), nullable=True)
    destination = Column(String(128), nullable=True)
    date = Column(String(32), nullable=True)
    raw_query = Column(Text, nullable=True)
    providers_called = Column(JSON, default=list)
    results_count = Column(Integer, default=0)
    cheapest_price = Column(Float, nullable=True)
    currency = Column(String(8), default="IDR")
    duration_ms = Column(Integer, nullable=True)
    cache_hit = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="search_logs")


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    travel_type = Column(SAEnum(TravelType), nullable=False)
    status = Column(SAEnum(BookingStatus), default=BookingStatus.pending)

    # Passenger info
    passenger_name = Column(String(256), nullable=True)
    passenger_id_number = Column(String(64), nullable=True)
    passenger_phone = Column(String(32), nullable=True)
    passenger_email = Column(String(256), nullable=True)

    # Travel details
    provider = Column(String(64), nullable=True)
    origin = Column(String(128), nullable=True)
    destination = Column(String(128), nullable=True)
    travel_date = Column(String(32), nullable=True)
    departure_time = Column(String(32), nullable=True)
    arrival_time = Column(String, nullable=True)
    train_name = Column(String(128), nullable=True)   # for train
    flight_number = Column(String(32), nullable=True)  # for flight
    hotel_name = Column(String(256), nullable=True)    # for hotel
    check_in = Column(String(32), nullable=True)
    check_out = Column(String(32), nullable=True)

    # Pricing
    price = Column(Float, nullable=True)
    currency = Column(String(8), default="IDR")

    # Raw offer snapshot from provider
    offer_snapshot = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="bookings")
    ticket = relationship("Ticket", back_populates="booking", uselist=False)


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_id = Column(UUID(as_uuid=True), ForeignKey("bookings.id"), nullable=False)
    ticket_code = Column(String(128), nullable=True)
    ticket_pdf_url = Column(String(512), nullable=True)
    issued_at = Column(DateTime, default=datetime.utcnow)
    raw_data = Column(JSON, nullable=True)

    booking = relationship("Booking", back_populates="ticket")
