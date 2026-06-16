import enum
import time
from datetime import date, datetime, timezone

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Float, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ai_clerk.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, index=True
    )
    chat_id: Mapped[int] = mapped_column(BigInteger)
    role: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class PendingInvite(Base):
    """A pending, single-use role invite addressed by an opaque token."""

    __tablename__ = "pending_invites"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    role: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[float] = mapped_column(Float, default=lambda: time.time())


class Profile(Base):
    """Traveler profile, 1:1 with a user (keyed by telegram_user_id).

    PII fields ending in `_enc` hold Fernet ciphertext; ProfileService is the
    only place that encrypts/decrypts them.
    """

    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, index=True
    )

    # Encrypted PII (Fernet tokens)
    full_name_enc: Mapped[str | None] = mapped_column(Text, default=None)
    iin_enc: Mapped[str | None] = mapped_column(Text, default=None)
    document_number_enc: Mapped[str | None] = mapped_column(Text, default=None)
    birth_date_enc: Mapped[str | None] = mapped_column(Text, default=None)

    # Plaintext, non-sensitive identity
    document_type: Mapped[str | None] = mapped_column(String(16), default=None)
    position: Mapped[str | None] = mapped_column(String(128), default=None)
    citizenship: Mapped[str | None] = mapped_column(String(64), default=None)

    # Preferences
    default_departure_iata: Mapped[str | None] = mapped_column(String(8), default=None)
    default_departure_city: Mapped[str | None] = mapped_column(String(128), default=None)
    preferred_airlines: Mapped[list | None] = mapped_column(JSON, default=None)
    preferred_hotels: Mapped[list | None] = mapped_column(JSON, default=None)
    seat_preference: Mapped[str | None] = mapped_column(String(32), default=None)
    meal_preference: Mapped[str | None] = mapped_column(String(64), default=None)
    prefer_faster: Mapped[bool] = mapped_column(Boolean, default=True)

    # Loyalty programs: list of {"program": str, "number": str}
    loyalty: Mapped[list | None] = mapped_column(JSON, default=None)

    # Policy / limits (nullable; stored, not yet enforced)
    budget_limit: Mapped[float | None] = mapped_column(Float, default=None)
    cabin_class: Mapped[str | None] = mapped_column(String(32), default=None)
    hotel_max_stars: Mapped[int | None] = mapped_column(Integer, default=None)
    per_diem: Mapped[float | None] = mapped_column(Float, default=None)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class TripStatus(str, enum.Enum):
    CONFIRMED = "confirmed"  # Plan 4 adds BOOKING/BOOKED/etc.


class Trip(Base):
    """A trip created by the orchestrator. Plan 3 persists it at CONFIRMED;
    Plan 4's booking saga resumes from here. No raw PII is stored — traveler
    identity stays in Profile and is pulled at order-generation time (Plan 5)."""

    __tablename__ = "trips"

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, index=True)

    origin_iata: Mapped[str | None] = mapped_column(String(8), default=None)
    dest_city: Mapped[str | None] = mapped_column(String(128), default=None)
    dest_iata: Mapped[str | None] = mapped_column(String(8), default=None)
    depart_date: Mapped[date | None] = mapped_column(Date, default=None)
    return_date: Mapped[date | None] = mapped_column(Date, default=None)

    selected_flight: Mapped[dict | None] = mapped_column(JSON, default=None)
    selected_hotel: Mapped[dict | None] = mapped_column(JSON, default=None)

    status: Mapped[str] = mapped_column(String(16))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
