from dataclasses import dataclass, field


@dataclass
class ProfileDTO:
    """Decrypted, read-only view of a profile returned by ProfileService."""

    telegram_user_id: int
    full_name: str | None = None
    iin: str | None = None
    document_type: str | None = None
    document_number: str | None = None
    birth_date: str | None = None
    position: str | None = None
    citizenship: str | None = None
    default_departure_iata: str | None = None
    default_departure_city: str | None = None
    preferred_airlines: list[str] = field(default_factory=list)
    preferred_hotels: list[str] = field(default_factory=list)
    seat_preference: str | None = None
    meal_preference: str | None = None
    prefer_faster: bool = True
    loyalty: list[dict] = field(default_factory=list)
    budget_limit: float | None = None
    cabin_class: str | None = None
    hotel_max_stars: int | None = None
    per_diem: float | None = None
