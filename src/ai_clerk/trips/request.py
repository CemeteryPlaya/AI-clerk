from dataclasses import dataclass, field
from datetime import date, datetime

from ai_clerk.trips.options import FlightOption, HotelOption


@dataclass
class TripRequest:
    """Accumulated trip slots (mutable; the orchestrator fills it over turns)."""

    dest_city: str | None = None
    dest_iata: str | None = None
    origin_city: str | None = None
    origin_iata: str | None = None
    depart_date: date | None = None
    arrive_by: datetime | None = None  # required arrival time (naive local, no tz)
    return_date: date | None = None
    one_way: bool = True
    notes: str | None = None

    def checkin_date(self) -> date | None:
        """Hotel check-in date: the outbound date (explicit, or the arrival
        deadline's day if only arrive_by is set)."""
        return self.depart_date or (self.arrive_by.date() if self.arrive_by else None)


@dataclass(frozen=True)
class TripDraft:
    """A confirmed selection. `request` is held by reference; the orchestrator
    passes a snapshot (dataclasses.replace) at pick() time so the draft is
    self-contained and immune to later dialog mutation."""

    request: TripRequest
    flight: FlightOption
    hotel: HotelOption | None = None


@dataclass
class OrchestratorReply:
    text: str
    flights: list[FlightOption] = field(default_factory=list)
