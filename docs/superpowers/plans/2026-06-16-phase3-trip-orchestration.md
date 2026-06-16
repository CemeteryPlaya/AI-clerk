# Phase 3 — Trip Orchestration & Search — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn a free-text trip request into a ranked set of flight options and persist a confirmed `Trip`, via a Claude-backed slot-filling orchestrator (behind an interface), a `BookingProvider` (mock now), and duration→price ranking that respects an optional arrival deadline.

**Architecture:** Modular monolith (Python 3.14 + aiogram). New `trips/` package with focused units behind interfaces, mirroring Plan 2: `LlmClient` (Protocol) has a scripted `FakeLlmClient` for offline TDD and a real `ClaudeClient` adapter (Anthropic SDK, lazy import) for prod; `BookingProvider` has a deterministic `MockProvider`; the `Orchestrator` is a pure, fully-tested dialog state machine holding in-memory per-chat state and persisting a `Trip(status=CONFIRMED)` at confirmation. Booking/OTP/real providers are Plan 4.

**Tech Stack:** SQLAlchemy 2.0 async, aiogram 3.x, `anthropic` SDK (prod only; tests use the fake), pytest + pytest-asyncio.

**Spec:** `docs/superpowers/specs/2026-06-16-phase3-trip-orchestration-design.md`

> **Repo conventions:**
> - Tests: `.venv\Scripts\python.exe -m pytest -q` (Windows; `asyncio_mode=auto`, `pythonpath=src`).
> - PII never enters the orchestration prompt — Claude sees only trip context (destination/dates/preferences).
> - End every commit message with the `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` trailer.

---

## File Structure

```
src/ai_clerk/
  config.py                       # MODIFY: add anthropic_api_key, anthropic_model
  db/models.py                    # MODIFY: add TripStatus enum + Trip model
  location/service.py             # MODIFY: add airport_for_city(city) helper
  trips/
    __init__.py                   # NEW (empty)
    options.py                    # NEW: FlightOption, HotelOption (frozen, to_dict)
    request.py                    # NEW: TripRequest, TripDraft, OrchestratorReply
    provider.py                   # NEW: BookingProvider Protocol
    mock_provider.py              # NEW: MockProvider (deterministic KZ data)
    ranking.py                    # NEW: rank_flights, select_flights
    llm.py                        # NEW: LlmClient Protocol, FakeLlmClient, ClaudeClient
    orchestrator.py               # NEW: Orchestrator (dialog state machine)
    presentation.py               # NEW: render_flight_options (text + keyboard)
    service.py                    # NEW: TripService (persist confirmed Trip)
  bot/
    trip_handlers.py              # NEW: free-text -> orchestrator; option callbacks; /cancel
    main.py                       # MODIFY: build singletons, include trip router
pyproject.toml                    # MODIFY: add anthropic dependency
tests/
  test_config.py                  # MODIFY: assert new settings defaults
  test_trip_model.py              # NEW
  test_trip_options.py            # NEW
  test_trip_request.py            # NEW
  test_trip_provider_mock.py      # NEW
  test_trip_ranking.py            # NEW
  test_trip_llm.py                # NEW
  test_location_airport_for_city.py  # NEW
  test_trip_orchestrator.py       # NEW
  test_trip_presentation.py       # NEW
  test_trip_service.py            # NEW
```

---

## Task 1: Config — Anthropic settings + dependency

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/ai_clerk/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Add the dependency**

In `pyproject.toml`, add `"anthropic>=0.40"` to `[project].dependencies` (after `"pypdf>=5.1"`). Then run:
`.venv\Scripts\python.exe -m pip install -e ".[dev]"`
Expected: installs `anthropic` for Python 3.14.x.

- [ ] **Step 2: Write the failing test**

Append to `tests/test_config.py`:
```python
def test_anthropic_settings_defaults(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "x")
    monkeypatch.setenv("SECRET_KEY", "x")
    monkeypatch.setenv("FERNET_KEY", "x")

    s = Settings(_env_file=None)

    assert s.anthropic_api_key is None
    assert s.anthropic_model == "claude-sonnet-4-6"


def test_anthropic_settings_from_env(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "x")
    monkeypatch.setenv("SECRET_KEY", "x")
    monkeypatch.setenv("FERNET_KEY", "x")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-123")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-opus-4-8")

    s = Settings(_env_file=None)

    assert s.anthropic_api_key == "sk-ant-123"
    assert s.anthropic_model == "claude-opus-4-8"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_config.py -v`
Expected: FAIL — `AttributeError`/missing `anthropic_model`.

- [ ] **Step 4: Add the settings**

In `src/ai_clerk/config.py`, add these fields to `Settings` (after the `# Ops` block's `log_level`, keep everything else):
```python
    # LLM (Claude orchestrator)
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-6"
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_config.py -v`
Expected: PASS (all).

- [ ] **Step 6: Document the env vars**

Append to `.env.example`:
```dotenv
# Anthropic API for the trip orchestrator (leave blank to disable real LLM)
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-sonnet-4-6
```

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml src/ai_clerk/config.py tests/test_config.py .env.example
git commit -m "feat: Anthropic settings for the trip orchestrator"
```

---

## Task 2: Trip model + TripStatus

**Files:**
- Modify: `src/ai_clerk/db/models.py`
- Test: `tests/test_trip_model.py`

- [ ] **Step 1: Write the failing test**

`tests/test_trip_model.py`:
```python
from datetime import date

from sqlalchemy import select

from ai_clerk.db.models import Trip, TripStatus


async def test_trip_persists(session):
    session.add(
        Trip(
            chat_id=10,
            telegram_user_id=10,
            origin_iata="ALA",
            dest_city="Астана",
            dest_iata="NQZ",
            depart_date=date(2026, 7, 14),
            return_date=date(2026, 7, 16),
            selected_flight={"id": "F-A", "price": 45000.0},
            selected_hotel={"id": "H-4", "stars": 4},
            status=TripStatus.CONFIRMED.value,
        )
    )
    await session.commit()

    trip = (
        await session.execute(select(Trip).where(Trip.telegram_user_id == 10))
    ).scalar_one()
    assert trip.id is not None
    assert trip.status == "confirmed"
    assert trip.selected_flight["price"] == 45000.0
    assert trip.dest_iata == "NQZ"
    assert trip.created_at is not None


async def test_trip_status_enum_values():
    assert TripStatus.CONFIRMED.value == "confirmed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_trip_model.py -v`
Expected: FAIL — `ImportError: cannot import name 'Trip'`.

- [ ] **Step 3: Implement the model**

In `src/ai_clerk/db/models.py`:

Change the datetime import line `from datetime import datetime, timezone` to:
```python
from datetime import date, datetime, timezone
```
Change the sqlalchemy import line to add `Date`:
```python
from sqlalchemy import BigInteger, Boolean, Date, DateTime, Float, Integer, JSON, String, Text
```
Add `import enum` at the top (with the other stdlib imports).

Append:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_trip_model.py -v`
Expected: PASS (both). `init_models` imports `ai_clerk.db.models`, so `create_all` builds `trips`.

- [ ] **Step 5: Commit**

```bash
git add src/ai_clerk/db/models.py tests/test_trip_model.py
git commit -m "feat: Trip model and TripStatus enum"
```

---

## Task 3: Trip dataclasses (options + request)

**Files:**
- Create: `src/ai_clerk/trips/__init__.py` (empty)
- Create: `src/ai_clerk/trips/options.py`
- Create: `src/ai_clerk/trips/request.py`
- Test: `tests/test_trip_options.py`
- Test: `tests/test_trip_request.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_trip_options.py`:
```python
from datetime import datetime, timedelta

from ai_clerk.trips.options import FlightOption, HotelOption


def _flight() -> FlightOption:
    return FlightOption(
        id="F-A", airline="Air Astana", origin_iata="ALA", dest_iata="NQZ",
        departure=datetime(2026, 7, 14, 7, 0), arrival=datetime(2026, 7, 14, 8, 45),
        stops=0, price=45000.0, cabin="economy",
    )


def test_flight_duration():
    assert _flight().duration == timedelta(hours=1, minutes=45)


def test_flight_to_dict_is_json_safe():
    d = _flight().to_dict()
    assert d["departure"] == "2026-07-14T07:00:00"
    assert d["arrival"] == "2026-07-14T08:45:00"
    assert d["price"] == 45000.0


def test_hotel_total_price():
    h = HotelOption(id="H-4", name="Grand", stars=4, price_per_night=28000.0, nights=2, address="Астана")
    assert h.total_price == 56000.0
    assert h.to_dict()["total_price"] == 56000.0
```

`tests/test_trip_request.py`:
```python
from datetime import date, datetime

from ai_clerk.trips.options import FlightOption
from ai_clerk.trips.request import OrchestratorReply, TripDraft, TripRequest


def test_trip_request_defaults():
    r = TripRequest()
    assert r.dest_city is None
    assert r.one_way is True
    assert r.arrive_by is None


def test_orchestrator_reply_defaults_to_no_flights():
    reply = OrchestratorReply(text="hi")
    assert reply.flights == []


def test_trip_draft_holds_selection():
    flight = FlightOption(
        id="F-A", airline="A", origin_iata="ALA", dest_iata="NQZ",
        departure=datetime(2026, 7, 14, 7, 0), arrival=datetime(2026, 7, 14, 8, 45),
        stops=0, price=45000.0, cabin="economy",
    )
    draft = TripDraft(request=TripRequest(dest_city="Астана"), flight=flight)
    assert draft.flight.id == "F-A"
    assert draft.hotel is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_trip_options.py tests/test_trip_request.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ai_clerk.trips'`.

- [ ] **Step 3: Write the implementation**

`src/ai_clerk/trips/__init__.py`:
```python
```

`src/ai_clerk/trips/options.py`:
```python
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class FlightOption:
    id: str
    airline: str
    origin_iata: str
    dest_iata: str
    departure: datetime
    arrival: datetime
    stops: int
    price: float
    cabin: str  # "economy" | "business"

    @property
    def duration(self) -> timedelta:
        return self.arrival - self.departure

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "airline": self.airline,
            "origin_iata": self.origin_iata,
            "dest_iata": self.dest_iata,
            "departure": self.departure.isoformat(),
            "arrival": self.arrival.isoformat(),
            "stops": self.stops,
            "price": self.price,
            "cabin": self.cabin,
        }


@dataclass(frozen=True)
class HotelOption:
    id: str
    name: str
    stars: int
    price_per_night: float
    nights: int
    address: str

    @property
    def total_price(self) -> float:
        return self.price_per_night * self.nights

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "stars": self.stars,
            "price_per_night": self.price_per_night,
            "nights": self.nights,
            "total_price": self.total_price,
            "address": self.address,
        }
```

`src/ai_clerk/trips/request.py`:
```python
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
    arrive_by: datetime | None = None  # required arrival time at destination
    return_date: date | None = None
    one_way: bool = True
    notes: str | None = None


@dataclass(frozen=True)
class TripDraft:
    request: TripRequest
    flight: FlightOption
    hotel: HotelOption | None = None


@dataclass
class OrchestratorReply:
    text: str
    flights: list[FlightOption] = field(default_factory=list)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_trip_options.py tests/test_trip_request.py -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add src/ai_clerk/trips/__init__.py src/ai_clerk/trips/options.py src/ai_clerk/trips/request.py tests/test_trip_options.py tests/test_trip_request.py
git commit -m "feat: trip option and request dataclasses"
```

---

## Task 4: BookingProvider interface + MockProvider

**Files:**
- Create: `src/ai_clerk/trips/provider.py`
- Create: `src/ai_clerk/trips/mock_provider.py`
- Test: `tests/test_trip_provider_mock.py`

- [ ] **Step 1: Write the failing test**

`tests/test_trip_provider_mock.py`:
```python
from datetime import date

import pytest

from ai_clerk.trips.mock_provider import MockProvider


async def test_search_flights_returns_options():
    flights = await MockProvider().search_flights("ALA", "NQZ", date(2026, 7, 14))
    assert len(flights) == 3
    assert all(f.origin_iata == "ALA" and f.dest_iata == "NQZ" for f in flights)
    assert all(f.departure.date() == date(2026, 7, 14) for f in flights)
    # ids are deterministic and distinct
    assert len({f.id for f in flights}) == 3


async def test_search_hotels_scales_nights():
    hotels = await MockProvider().search_hotels("Астана", date(2026, 7, 14), date(2026, 7, 16))
    assert len(hotels) == 3
    assert all(h.nights == 2 for h in hotels)


async def test_book_not_implemented():
    with pytest.raises(NotImplementedError):
        await MockProvider().book(object())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_trip_provider_mock.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ai_clerk.trips.mock_provider'`.

- [ ] **Step 3: Write the implementation**

`src/ai_clerk/trips/provider.py`:
```python
from datetime import date
from typing import Protocol

from ai_clerk.trips.options import FlightOption, HotelOption
from ai_clerk.trips.request import TripDraft


class BookingProvider(Protocol):
    async def search_flights(
        self, origin_iata: str, dest_iata: str, on_date: date
    ) -> list[FlightOption]: ...

    async def search_hotels(
        self, city: str, checkin: date, checkout: date
    ) -> list[HotelOption]: ...

    async def book(self, draft: TripDraft) -> object: ...
```

`src/ai_clerk/trips/mock_provider.py`:
```python
from datetime import date, datetime, time

from ai_clerk.trips.options import FlightOption, HotelOption
from ai_clerk.trips.request import TripDraft


class MockProvider:
    """Deterministic canned KZ flight/hotel results for tests and local dev."""

    async def search_flights(
        self, origin_iata: str, dest_iata: str, on_date: date
    ) -> list[FlightOption]:
        base = f"{origin_iata}-{dest_iata}-{on_date.isoformat()}"
        return [
            FlightOption(
                id=f"{base}-A", airline="Air Astana",
                origin_iata=origin_iata, dest_iata=dest_iata,
                departure=datetime.combine(on_date, time(7, 0)),
                arrival=datetime.combine(on_date, time(8, 45)),
                stops=0, price=45000.0, cabin="economy",
            ),
            FlightOption(
                id=f"{base}-B", airline="FlyArystan",
                origin_iata=origin_iata, dest_iata=dest_iata,
                departure=datetime.combine(on_date, time(9, 30)),
                arrival=datetime.combine(on_date, time(13, 40)),
                stops=1, price=28000.0, cabin="economy",
            ),
            FlightOption(
                id=f"{base}-C", airline="SCAT",
                origin_iata=origin_iata, dest_iata=dest_iata,
                departure=datetime.combine(on_date, time(18, 0)),
                arrival=datetime.combine(on_date, time(19, 50)),
                stops=0, price=52000.0, cabin="business",
            ),
        ]

    async def search_hotels(
        self, city: str, checkin: date, checkout: date
    ) -> list[HotelOption]:
        nights = max((checkout - checkin).days, 1)
        return [
            HotelOption(id="H-3", name="City Inn", stars=3,
                        price_per_night=15000.0, nights=nights, address=city),
            HotelOption(id="H-4", name="Grand Plaza", stars=4,
                        price_per_night=28000.0, nights=nights, address=city),
            HotelOption(id="H-5", name="Royal Palace", stars=5,
                        price_per_night=55000.0, nights=nights, address=city),
        ]

    async def book(self, draft: TripDraft) -> object:
        raise NotImplementedError(
            "Booking is implemented by the browser-agent provider in Plan 4"
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_trip_provider_mock.py -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add src/ai_clerk/trips/provider.py src/ai_clerk/trips/mock_provider.py tests/test_trip_provider_mock.py
git commit -m "feat: BookingProvider interface and deterministic MockProvider"
```

---

## Task 5: Ranking + deadline-aware selection

**Files:**
- Create: `src/ai_clerk/trips/ranking.py`
- Test: `tests/test_trip_ranking.py`

- [ ] **Step 1: Write the failing test**

`tests/test_trip_ranking.py`:
```python
from datetime import date, datetime

from ai_clerk.trips.mock_provider import MockProvider
from ai_clerk.trips.ranking import rank_flights, select_flights
from ai_clerk.trips.request import TripRequest


async def _flights(on_date):
    return await MockProvider().search_flights("ALA", "NQZ", on_date)


async def test_rank_orders_by_duration_then_price():
    flights = await _flights(date(2026, 7, 14))
    ranked = rank_flights(flights)
    # direct 1h45 (A) and 1h50 (C) beat the 1-stop 4h10 (B); A before C by duration
    assert [f.id.split("-")[-1] for f in ranked][:2] == ["A", "C"]
    assert ranked[-1].id.endswith("B")


async def test_policy_filters_budget_and_cabin():
    flights = await _flights(date(2026, 7, 14))
    assert all(f.price <= 30000 for f in rank_flights(flights, budget_limit=30000))
    assert all(f.cabin == "business" for f in rank_flights(flights, cabin_class="business"))


async def test_policy_unset_keeps_all():
    flights = await _flights(date(2026, 7, 14))
    assert len(rank_flights(flights)) == len(flights)


async def test_select_flights_uses_depart_date():
    req = TripRequest(depart_date=date(2026, 7, 14))
    ranked = await select_flights(MockProvider(), "ALA", "NQZ", req)
    assert ranked and all(f.departure.date() == date(2026, 7, 14) for f in ranked)


async def test_select_flights_arrive_by_considers_day_before_and_filters():
    # Deadline 08:50 on the 14th: only the 07:00->08:45 flight (A) qualifies on
    # the 14th; the day-before (13th) flights also arrive before the deadline.
    req = TripRequest(arrive_by=datetime(2026, 7, 14, 8, 50))
    ranked = await select_flights(MockProvider(), "ALA", "NQZ", req)
    assert ranked  # found something
    assert all(f.arrival <= datetime(2026, 7, 14, 8, 50) for f in ranked)
    # the 14th's qualifying flight is present
    assert any(f.departure.date() == date(2026, 7, 14) for f in ranked)


async def test_select_flights_no_date_returns_empty():
    assert await select_flights(MockProvider(), "ALA", "NQZ", TripRequest()) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_trip_ranking.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ai_clerk.trips.ranking'`.

- [ ] **Step 3: Write the implementation**

`src/ai_clerk/trips/ranking.py`:
```python
from datetime import timedelta

from ai_clerk.trips.options import FlightOption
from ai_clerk.trips.provider import BookingProvider
from ai_clerk.trips.request import TripRequest


def rank_flights(
    options: list[FlightOption],
    *,
    budget_limit: float | None = None,
    cabin_class: str | None = None,
) -> list[FlightOption]:
    """Filter by policy (only where set), then sort by duration, then price."""
    filtered = [
        o
        for o in options
        if (budget_limit is None or o.price <= budget_limit)
        and (cabin_class is None or o.cabin == cabin_class)
    ]
    return sorted(filtered, key=lambda o: (o.duration, o.price))


async def select_flights(
    provider: BookingProvider,
    origin_iata: str,
    dest_iata: str,
    request: TripRequest,
    *,
    budget_limit: float | None = None,
    cabin_class: str | None = None,
) -> list[FlightOption]:
    """Search candidate dates, honour an arrival deadline (considering a
    departure the day before), and return the ranked result."""
    if request.depart_date is not None:
        candidate_dates = [request.depart_date]
    elif request.arrive_by is not None:
        deadline_day = request.arrive_by.date()
        candidate_dates = [deadline_day - timedelta(days=1), deadline_day]
    else:
        return []

    options: list[FlightOption] = []
    for on_date in candidate_dates:
        options.extend(await provider.search_flights(origin_iata, dest_iata, on_date))

    if request.arrive_by is not None:
        options = [o for o in options if o.arrival <= request.arrive_by]

    return rank_flights(options, budget_limit=budget_limit, cabin_class=cabin_class)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_trip_ranking.py -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add src/ai_clerk/trips/ranking.py tests/test_trip_ranking.py
git commit -m "feat: flight ranking and deadline-aware selection"
```

---

## Task 6: LlmClient interface (Fake + Claude adapter)

**Files:**
- Create: `src/ai_clerk/trips/llm.py`
- Test: `tests/test_trip_llm.py`

> The real `ClaudeClient` imports `anthropic` lazily and is verified manually (Task 12); unit tests cover only `FakeLlmClient` and that `ClaudeClient` constructs without network. When implementing/verifying `ClaudeClient`, consult the `claude-api` reference skill for the current model id and Messages-API usage.

- [ ] **Step 1: Write the failing test**

`tests/test_trip_llm.py`:
```python
from dataclasses import replace
from datetime import date

from ai_clerk.trips.llm import ClaudeClient, FakeLlmClient
from ai_clerk.trips.request import TripRequest


async def test_fake_llm_applies_responder():
    def responder(current: TripRequest, message: str) -> TripRequest:
        return replace(current, dest_city="Астана", depart_date=date(2026, 7, 14))

    out = await FakeLlmClient(responder).fill_slots(TripRequest(), "хочу в Астану 14 июля")
    assert out.dest_city == "Астана"
    assert out.depart_date == date(2026, 7, 14)


def test_claude_client_constructs_without_network():
    # No API call happens at construction; anthropic is imported lazily in fill_slots.
    client = ClaudeClient(api_key="sk-test", model="claude-sonnet-4-6")
    assert client._model == "claude-sonnet-4-6"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_trip_llm.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ai_clerk.trips.llm'`.

- [ ] **Step 3: Write the implementation**

`src/ai_clerk/trips/llm.py`:
```python
import json
from collections.abc import Callable
from datetime import date, datetime
from typing import Protocol

from ai_clerk.trips.request import TripRequest


class LlmClient(Protocol):
    async def fill_slots(self, current: TripRequest, message: str) -> TripRequest: ...


class FakeLlmClient:
    """Test double: a responder function maps (current, message) -> updated request."""

    def __init__(self, responder: Callable[[TripRequest, str], TripRequest]):
        self._responder = responder

    async def fill_slots(self, current: TripRequest, message: str) -> TripRequest:
        return self._responder(current, message)


_SYSTEM = (
    "Ты помощник по командировкам. Извлеки из сообщения параметры поездки и верни "
    "СТРОГО JSON-объект с ключами: dest_city, origin_city (строки или null), "
    "depart_date, return_date (даты YYYY-MM-DD или null), arrive_by (дата-время "
    "ISO 8601 или null), one_way (true/false), notes (строка или null). "
    "Сохраняй уже известные значения, обновляй только то, что явно сказано. "
    "Никогда не запрашивай и не упоминай персональные данные (ИИН, паспорт, ФИО). "
    "Возвращай только JSON, без пояснений."
)


def _known(current: TripRequest) -> dict:
    return {
        "dest_city": current.dest_city,
        "origin_city": current.origin_city,
        "depart_date": current.depart_date.isoformat() if current.depart_date else None,
        "return_date": current.return_date.isoformat() if current.return_date else None,
        "arrive_by": current.arrive_by.isoformat() if current.arrive_by else None,
        "one_way": current.one_way,
        "notes": current.notes,
    }


def _merge(current: TripRequest, data: dict) -> TripRequest:
    def _date(value):
        return date.fromisoformat(value) if value else None

    def _dt(value):
        return datetime.fromisoformat(value) if value else None

    return TripRequest(
        dest_city=data.get("dest_city") or current.dest_city,
        dest_iata=current.dest_iata,
        origin_city=data.get("origin_city") or current.origin_city,
        origin_iata=current.origin_iata,
        depart_date=_date(data.get("depart_date")) or current.depart_date,
        arrive_by=_dt(data.get("arrive_by")) or current.arrive_by,
        return_date=_date(data.get("return_date")) or current.return_date,
        one_way=bool(data.get("one_way", current.one_way)),
        notes=data.get("notes") or current.notes,
    )


class ClaudeClient:
    """Real adapter: extracts trip slots from free text via the Anthropic API.

    `anthropic` is imported lazily so the module loads without it; the prompt
    carries only trip context — never identity PII."""

    def __init__(self, api_key: str, model: str):
        self._api_key = api_key
        self._model = model

    async def fill_slots(self, current: TripRequest, message: str) -> TripRequest:
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=self._api_key)
        user = json.dumps(
            {"known": _known(current), "message": message}, ensure_ascii=False
        )
        resp = await client.messages.create(
            model=self._model,
            max_tokens=512,
            system=_SYSTEM,
            messages=[{"role": "user", "content": user}],
        )
        data = json.loads(resp.content[0].text)
        return _merge(current, data)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_trip_llm.py -v`
Expected: PASS (both). The `ClaudeClient` test never calls `fill_slots`, so no network/import of `anthropic` is triggered.

- [ ] **Step 5: Commit**

```bash
git add src/ai_clerk/trips/llm.py tests/test_trip_llm.py
git commit -m "feat: LlmClient interface with Fake and Claude adapters"
```

---

## Task 7: LocationService.airport_for_city

**Files:**
- Modify: `src/ai_clerk/location/service.py`
- Test: `tests/test_location_airport_for_city.py`

> The orchestrator needs city→airport for the DESTINATION (the existing `resolve_departure` is for the origin). Add a thin method delegating to the index.

- [ ] **Step 1: Write the failing test**

`tests/test_location_airport_for_city.py`:
```python
from pathlib import Path

from ai_clerk.location.airports import AirportIndex
from ai_clerk.location.service import LocationService

FIXTURE = Path(__file__).parent / "fixtures" / "airports_sample.csv"


def _service() -> LocationService:
    return LocationService(AirportIndex.from_csv(FIXTURE))


def test_airport_for_city_resolves_alias():
    assert _service().airport_for_city("Астана").iata == "NQZ"


def test_airport_for_city_unknown_returns_none():
    assert _service().airport_for_city("Париж") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_location_airport_for_city.py -v`
Expected: FAIL — `AttributeError: 'LocationService' object has no attribute 'airport_for_city'`.

- [ ] **Step 3: Write the implementation**

In `src/ai_clerk/location/service.py`, add this method to `LocationService` (the class already stores `self._index`):
```python
    def airport_for_city(self, city: str) -> "Airport | None":
        """Resolve a destination city name to an airport (alias-aware)."""
        return self._index.by_city(city)
```
Ensure `Airport` is imported in that file (it already imports from `ai_clerk.location.airports`; if only `AirportIndex` is imported, add `Airport`):
```python
from ai_clerk.location.airports import Airport, AirportIndex
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_location_airport_for_city.py -v`
Expected: PASS (both).

- [ ] **Step 5: Commit**

```bash
git add src/ai_clerk/location/service.py tests/test_location_airport_for_city.py
git commit -m "feat: LocationService.airport_for_city for destination resolution"
```

---

## Task 8: Orchestrator (dialog state machine)

**Files:**
- Create: `src/ai_clerk/trips/orchestrator.py`
- Test: `tests/test_trip_orchestrator.py`

- [ ] **Step 1: Write the failing test**

`tests/test_trip_orchestrator.py`:
```python
from dataclasses import replace
from datetime import date
from pathlib import Path

from ai_clerk.location.airports import AirportIndex
from ai_clerk.location.service import LocationService
from ai_clerk.profile.dto import ProfileDTO
from ai_clerk.trips.llm import FakeLlmClient
from ai_clerk.trips.mock_provider import MockProvider
from ai_clerk.trips.orchestrator import Orchestrator
from ai_clerk.trips.request import TripRequest

FIXTURE = Path(__file__).parent / "fixtures" / "airports_sample.csv"


def _orchestrator(responder) -> Orchestrator:
    location = LocationService(AirportIndex.from_csv(FIXTURE))
    return Orchestrator(FakeLlmClient(responder), location, MockProvider())


def _profile(**kw) -> ProfileDTO:
    return ProfileDTO(telegram_user_id=1, **kw)


async def test_asks_for_destination_when_missing():
    orch = _orchestrator(lambda cur, msg: cur)  # LLM extracts nothing
    reply = await orch.handle_message(1, "привет", _profile(default_departure_city="Алматы"))
    assert "куда" in reply.text.lower()
    assert reply.flights == []


async def test_asks_for_origin_when_no_destination_default():
    orch = _orchestrator(lambda cur, msg: replace(cur, dest_city="Астана"))
    reply = await orch.handle_message(1, "в Астану", _profile())  # no default departure
    assert "откуда" in reply.text.lower()


async def test_asks_for_date_when_missing():
    orch = _orchestrator(lambda cur, msg: replace(cur, dest_city="Астана"))
    reply = await orch.handle_message(1, "в Астану", _profile(default_departure_city="Алматы"))
    assert "дат" in reply.text.lower()


async def test_presents_flights_when_slots_complete():
    orch = _orchestrator(
        lambda cur, msg: replace(cur, dest_city="Астана", depart_date=date(2026, 7, 14))
    )
    reply = await orch.handle_message(1, "в Астану 14 июля", _profile(default_departure_city="Алматы"))
    assert reply.flights, "expected ranked flight options"
    assert reply.flights[0].dest_iata == "NQZ"


async def test_pick_returns_draft_and_clears_dialog():
    orch = _orchestrator(
        lambda cur, msg: replace(
            cur, dest_city="Астана", depart_date=date(2026, 7, 14), return_date=date(2026, 7, 16)
        )
    )
    await orch.handle_message(1, "в Астану 14-16 июля", _profile(default_departure_city="Алматы"))
    draft = await orch.pick(1, 0, _profile(default_departure_city="Алматы"))
    assert draft is not None
    assert draft.flight.dest_iata == "NQZ"
    assert draft.hotel is not None  # round trip -> top hotel attached
    # dialog cleared: picking again returns None
    assert await orch.pick(1, 0, _profile()) is None


async def test_pick_out_of_range_returns_none():
    orch = _orchestrator(lambda cur, msg: cur)
    assert await orch.pick(999, 0, _profile()) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_trip_orchestrator.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ai_clerk.trips.orchestrator'`.

- [ ] **Step 3: Write the implementation**

`src/ai_clerk/trips/orchestrator.py`:
```python
from dataclasses import dataclass, field

from ai_clerk.location.service import LocationService
from ai_clerk.profile.dto import ProfileDTO
from ai_clerk.trips.llm import LlmClient
from ai_clerk.trips.options import FlightOption, HotelOption
from ai_clerk.trips.provider import BookingProvider
from ai_clerk.trips.ranking import select_flights
from ai_clerk.trips.request import OrchestratorReply, TripDraft, TripRequest


@dataclass
class _Dialog:
    request: TripRequest = field(default_factory=TripRequest)
    presented: list[FlightOption] = field(default_factory=list)


def _top_hotel(hotels: list[HotelOption], max_stars: int | None) -> HotelOption | None:
    eligible = [h for h in hotels if max_stars is None or h.stars <= max_stars]
    return min(eligible, key=lambda h: h.total_price) if eligible else None


class Orchestrator:
    """In-memory dialog state machine: fill slots -> clarify or search/present;
    pick -> TripDraft. Pure logic; no DB or aiogram."""

    def __init__(
        self,
        llm: LlmClient,
        location: LocationService,
        provider: BookingProvider,
        top_n: int = 3,
    ):
        self._llm = llm
        self._location = location
        self._provider = provider
        self._top_n = top_n
        self._dialogs: dict[int, _Dialog] = {}

    def cancel(self, chat_id: int) -> None:
        self._dialogs.pop(chat_id, None)

    async def handle_message(
        self, chat_id: int, message: str, profile: ProfileDTO | None
    ) -> OrchestratorReply:
        dialog = self._dialogs.setdefault(chat_id, _Dialog())
        dialog.request = await self._llm.fill_slots(dialog.request, message)
        req = dialog.request

        dest = self._location.airport_for_city(req.dest_city) if req.dest_city else None
        if dest is None:
            return OrchestratorReply(text="Куда летим? Укажите город назначения.")

        profile_default = None
        if profile is not None:
            profile_default = profile.default_departure_city or profile.default_departure_iata
        origin = self._location.resolve_departure(
            explicit_city=req.origin_city, profile_default=profile_default
        )
        if origin is None:
            return OrchestratorReply(
                text="Откуда вылетаем? Укажите город вылета "
                "(или сохраните его в профиле через /location)."
            )

        if req.depart_date is None and req.arrive_by is None:
            return OrchestratorReply(
                text="На какую дату планируете поездку "
                "(или к какому времени нужно быть на месте)?"
            )

        budget = profile.budget_limit if profile else None
        cabin = profile.cabin_class if profile else None
        flights = await select_flights(
            self._provider,
            origin.airport.iata,
            dest.iata,
            req,
            budget_limit=budget,
            cabin_class=cabin,
        )
        if not flights:
            return OrchestratorReply(
                text="Не нашёл подходящих рейсов на эти даты. "
                "Попробуем другие даты или направление?"
            )

        req.dest_iata = dest.iata
        req.origin_iata = origin.airport.iata
        dialog.presented = flights[: self._top_n]
        return OrchestratorReply(text="Нашёл варианты:", flights=dialog.presented)

    async def pick(
        self, chat_id: int, index: int, profile: ProfileDTO | None
    ) -> TripDraft | None:
        dialog = self._dialogs.get(chat_id)
        if dialog is None or not (0 <= index < len(dialog.presented)):
            return None
        flight = dialog.presented[index]
        req = dialog.request

        hotel = None
        if req.return_date is not None:
            checkin = req.depart_date or (req.arrive_by.date() if req.arrive_by else None)
            if checkin is not None:
                hotels = await self._provider.search_hotels(
                    req.dest_city, checkin, req.return_date
                )
                hotel = _top_hotel(hotels, profile.hotel_max_stars if profile else None)

        self._dialogs.pop(chat_id, None)
        return TripDraft(request=req, flight=flight, hotel=hotel)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_trip_orchestrator.py -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add src/ai_clerk/trips/orchestrator.py tests/test_trip_orchestrator.py
git commit -m "feat: trip dialog orchestrator (slot-filling, search, pick)"
```

---

## Task 9: Presentation (options message + keyboard)

**Files:**
- Create: `src/ai_clerk/trips/presentation.py`
- Test: `tests/test_trip_presentation.py`

- [ ] **Step 1: Write the failing test**

`tests/test_trip_presentation.py`:
```python
from datetime import datetime

from ai_clerk.trips.options import FlightOption
from ai_clerk.trips.presentation import render_flight_options


def _flight(suffix: str, dep_h: int, arr_h: int, price: float, stops: int = 0) -> FlightOption:
    return FlightOption(
        id=f"F-{suffix}", airline="Air Astana", origin_iata="ALA", dest_iata="NQZ",
        departure=datetime(2026, 7, 14, dep_h, 0), arrival=datetime(2026, 7, 14, arr_h, 0),
        stops=stops, price=price, cabin="economy",
    )


def test_render_lists_options_with_buttons():
    flights = [_flight("A", 7, 9, 45000.0), _flight("B", 10, 14, 28000.0, stops=1)]
    text, keyboard = render_flight_options(flights)

    assert "Air Astana" in text
    assert "1." in text and "2." in text
    # one button per option, callback encodes the index
    buttons = [b for row in keyboard.inline_keyboard for b in row]
    assert len(buttons) == 2
    assert buttons[0].callback_data == "trip:pick:0"
    assert buttons[1].callback_data == "trip:pick:1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_trip_presentation.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ai_clerk.trips.presentation'`.

- [ ] **Step 3: Write the implementation**

`src/ai_clerk/trips/presentation.py`:
```python
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from ai_clerk.trips.options import FlightOption


def _format_line(index: int, flight: FlightOption) -> str:
    minutes = int(flight.duration.total_seconds() // 60)
    hours, mins = divmod(minutes, 60)
    stops = "прямой" if flight.stops == 0 else f"{flight.stops} пересад."
    return (
        f"{index + 1}. {flight.airline} "
        f"{flight.departure:%d.%m %H:%M}→{flight.arrival:%H:%M} "
        f"({hours}ч{mins:02d}м, {stops}), {int(flight.price)} ₸, {flight.cabin}"
    )


def render_flight_options(
    flights: list[FlightOption],
) -> tuple[str, InlineKeyboardMarkup]:
    lines = [_format_line(i, f) for i, f in enumerate(flights)]
    text = (
        "Варианты перелёта (по времени в пути):\n"
        + "\n".join(lines)
        + "\n\nВыберите вариант кнопкой ниже:"
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=str(i + 1), callback_data=f"trip:pick:{i}")]
            for i in range(len(flights))
        ]
    )
    return text, keyboard
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_trip_presentation.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ai_clerk/trips/presentation.py tests/test_trip_presentation.py
git commit -m "feat: flight options presentation (message + inline keyboard)"
```

---

## Task 10: TripService (persist confirmed trip)

**Files:**
- Create: `src/ai_clerk/trips/service.py`
- Test: `tests/test_trip_service.py`

- [ ] **Step 1: Write the failing test**

`tests/test_trip_service.py`:
```python
from datetime import date, datetime

from sqlalchemy import select

from ai_clerk.db.models import Trip
from ai_clerk.trips.options import FlightOption, HotelOption
from ai_clerk.trips.request import TripDraft, TripRequest
from ai_clerk.trips.service import TripService


def _draft(with_hotel: bool) -> TripDraft:
    flight = FlightOption(
        id="F-A", airline="Air Astana", origin_iata="ALA", dest_iata="NQZ",
        departure=datetime(2026, 7, 14, 7, 0), arrival=datetime(2026, 7, 14, 8, 45),
        stops=0, price=45000.0, cabin="economy",
    )
    hotel = (
        HotelOption(id="H-4", name="Grand", stars=4, price_per_night=28000.0, nights=2, address="Астана")
        if with_hotel else None
    )
    request = TripRequest(
        dest_city="Астана", dest_iata="NQZ", origin_iata="ALA",
        depart_date=date(2026, 7, 14), return_date=date(2026, 7, 16),
    )
    return TripDraft(request=request, flight=flight, hotel=hotel)


async def test_create_confirmed_trip_persists_selection(session):
    trip = await TripService(session).create_confirmed_trip(10, 20, _draft(with_hotel=True))
    assert trip.id is not None
    assert trip.status == "confirmed"
    assert trip.dest_iata == "NQZ"
    assert trip.selected_flight["id"] == "F-A"
    assert trip.selected_hotel["stars"] == 4

    row = (await session.execute(select(Trip).where(Trip.id == trip.id))).scalar_one()
    assert row.telegram_user_id == 20
    assert row.depart_date == date(2026, 7, 14)


async def test_create_confirmed_trip_without_hotel(session):
    trip = await TripService(session).create_confirmed_trip(10, 20, _draft(with_hotel=False))
    assert trip.selected_hotel is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_trip_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ai_clerk.trips.service'`.

- [ ] **Step 3: Write the implementation**

`src/ai_clerk/trips/service.py`:
```python
from sqlalchemy.ext.asyncio import AsyncSession

from ai_clerk.db.models import Trip, TripStatus
from ai_clerk.trips.request import TripDraft


class TripService:
    """Persists a confirmed Trip — the durable hand-off point for Plan 4."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def create_confirmed_trip(
        self, chat_id: int, telegram_user_id: int, draft: TripDraft
    ) -> Trip:
        req = draft.request
        checkin = req.depart_date or (req.arrive_by.date() if req.arrive_by else None)
        trip = Trip(
            chat_id=chat_id,
            telegram_user_id=telegram_user_id,
            origin_iata=req.origin_iata,
            dest_city=req.dest_city,
            dest_iata=req.dest_iata,
            depart_date=checkin,
            return_date=req.return_date,
            selected_flight=draft.flight.to_dict(),
            selected_hotel=draft.hotel.to_dict() if draft.hotel else None,
            status=TripStatus.CONFIRMED.value,
        )
        self._session.add(trip)
        await self._session.commit()
        await self._session.refresh(trip)
        return trip
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_trip_service.py -v`
Expected: PASS (both).

- [ ] **Step 5: Commit**

```bash
git add src/ai_clerk/trips/service.py tests/test_trip_service.py
git commit -m "feat: TripService persists the confirmed trip"
```

---

## Task 11: Bot wiring — trip handlers + entrypoint (manual run verification)

**Files:**
- Create: `src/ai_clerk/bot/trip_handlers.py`
- Modify: `src/ai_clerk/bot/main.py`

> Glue between aiogram and the tested orchestrator/services. No unit test; verify by importing the module, building the router, and running the suite. The live Telegram conversation needs a real `BOT_TOKEN` (+ `ANTHROPIC_API_KEY` for real NLU) and is an owner step. The orchestrator/ranking/persistence logic is already covered by Tasks 5–10.

- [ ] **Step 1: Write the trip handlers**

`src/ai_clerk/bot/trip_handlers.py`:
```python
import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from ai_clerk.bot.permissions import is_allowed
from ai_clerk.profile.service import ProfileService
from ai_clerk.roles.service import RoleService
from ai_clerk.trips.orchestrator import Orchestrator
from ai_clerk.trips.presentation import render_flight_options
from ai_clerk.trips.service import TripService

logger = logging.getLogger(__name__)


def build_trip_router(orchestrator: Orchestrator) -> Router:
    router = Router()

    async def _can_create(message: Message, role_service: RoleService) -> bool:
        if message.from_user is None:
            return False
        role = await role_service.get_role(message.from_user.id)
        return is_allowed(role, "trip.create")

    @router.message(Command("cancel"))
    async def on_cancel(message: Message, role_service: RoleService) -> None:
        if not await _can_create(message, role_service):
            return
        orchestrator.cancel(message.chat.id)
        await message.answer("Текущий запрос на поездку сброшен.")

    @router.message(F.text & ~F.text.startswith("/"))
    async def on_text(
        message: Message,
        role_service: RoleService,
        profile_service: ProfileService,
    ) -> None:
        if not await _can_create(message, role_service):
            return  # ignore free text from users without trip.create
        profile = await profile_service.get_profile(message.from_user.id)
        try:
            reply = await orchestrator.handle_message(
                message.chat.id, message.text, profile
            )
        except Exception:
            logger.exception("Orchestrator failed for chat %s", message.chat.id)
            await message.answer(
                "Не смог обработать запрос. Попробуйте сформулировать ещё раз."
            )
            return
        if reply.flights:
            text, keyboard = render_flight_options(reply.flights)
            await message.answer(text, reply_markup=keyboard)
        else:
            await message.answer(reply.text)

    @router.callback_query(F.data.startswith("trip:pick:"))
    async def on_pick(
        callback: CallbackQuery,
        session: AsyncSession,
        profile_service: ProfileService,
    ) -> None:
        index = int(callback.data.rsplit(":", 1)[1])
        profile = await profile_service.get_profile(callback.from_user.id)
        draft = await orchestrator.pick(callback.message.chat.id, index, profile)
        if draft is None:
            await callback.answer("Вариант недоступен, начните поиск заново.", show_alert=True)
            return
        trip = await TripService(session).create_confirmed_trip(
            callback.message.chat.id, callback.from_user.id, draft
        )
        flight = draft.flight
        hotel_line = (
            f"\nОтель: {draft.hotel.name} {draft.hotel.stars}★, "
            f"{int(draft.hotel.total_price)} ₸"
            if draft.hotel
            else ""
        )
        text = (
            f"Вариант выбран (поездка #{trip.id}).\n"
            f"Рейс: {flight.airline} {flight.departure:%d.%m %H:%M}→{flight.arrival:%H:%M}, "
            f"{int(flight.price)} ₸.{hotel_line}\n"
            "Бронирование и оплата — на следующем шаге."
        )
        if callback.message is not None and hasattr(callback.message, "edit_text"):
            await callback.message.edit_text(text)
        await callback.answer()

    return router
```

- [ ] **Step 2: Wire it into `src/ai_clerk/bot/main.py`**

Add imports alongside the existing ones:
```python
from ai_clerk.bot.trip_handlers import build_trip_router
from ai_clerk.trips.llm import ClaudeClient, FakeLlmClient
from ai_clerk.trips.mock_provider import MockProvider
from ai_clerk.trips.orchestrator import Orchestrator
```

After the existing singletons block (the lines that build `cipher`, `location_service`, `pdf_extractor`, `field_extractor`), add:
```python
    if settings.anthropic_api_key:
        llm_client = ClaudeClient(settings.anthropic_api_key, settings.anthropic_model)
    else:
        # No API key configured: a minimal fallback that extracts nothing, so the
        # orchestrator just asks for the missing slots. Set ANTHROPIC_API_KEY for real NLU.
        llm_client = FakeLlmClient(lambda current, message: current)
    orchestrator = Orchestrator(llm_client, location_service, MockProvider())
```

Immediately before the `dp.include_router(build_profile_router(...))` line, add:
```python
    dp.include_router(build_trip_router(orchestrator))
```
> Include the trip router BEFORE the profile router is not required, but keep the trip router's free-text handler from shadowing profile commands: it already excludes `/`-commands via `~F.text.startswith("/")`, and `F.document`/`F.location` are different content types, so order is safe. Leave the profile router include where it is and add the trip include next to it.

- [ ] **Step 3: Verify imports, router build, full suite**

Run:
```
.venv\Scripts\python.exe -c "import ai_clerk.bot.main; from ai_clerk.bot.trip_handlers import build_trip_router; from ai_clerk.trips.llm import FakeLlmClient; from ai_clerk.location.airports import AirportIndex; from ai_clerk.location.service import LocationService; from ai_clerk.trips.mock_provider import MockProvider; from ai_clerk.trips.orchestrator import Orchestrator; build_trip_router(Orchestrator(FakeLlmClient(lambda c,m:c), LocationService(AirportIndex.bundled()), MockProvider())); print('trip router OK')"
```
Expected: `trip router OK`.
Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: all tests pass (Plan 1+2+3).

- [ ] **Step 4: (Owner, manual) live check**

With `.env` containing `BOT_TOKEN` and (optionally) `ANTHROPIC_API_KEY`, run `.venv\Scripts\python.exe -m ai_clerk.bot.main`. As the onboarded DIRECTOR, send e.g. "Нужно в Астану 14 июля и обратно 16-го". With a key, Claude fills slots; without, the bot asks for destination/origin/date. Once complete, the bot lists flights; tapping a number confirms and persists the trip.

- [ ] **Step 5: Commit**

```bash
git add src/ai_clerk/bot/trip_handlers.py src/ai_clerk/bot/main.py
git commit -m "feat: trip orchestration wired into the bot (free-text + confirm)"
```

---

## Task 12: Manual Claude adapter verification (owner, optional)

> Confirms the real `ClaudeClient` extracts slots. Needs `ANTHROPIC_API_KEY`. Not a unit test (the adapter is intentionally not unit-tested); this exercises the prod path once. No commit unless fixes are made.

- [ ] **Step 1: Run a one-off extraction**

With `ANTHROPIC_API_KEY` set in the environment, run:
```
.venv\Scripts\python.exe -c "import asyncio; from ai_clerk.config import get_settings; from ai_clerk.trips.llm import ClaudeClient; from ai_clerk.trips.request import TripRequest; s=get_settings(); c=ClaudeClient(s.anthropic_api_key, s.anthropic_model); print(asyncio.run(c.fill_slots(TripRequest(), 'нужно в Астану 14 июля и обратно 16-го')))"
```
Expected: a `TripRequest` with `dest_city` ≈ "Астана", `depart_date=2026-07-14`, `return_date=2026-07-16`, `one_way=False` (exact phrasing/parse may vary; adjust the system prompt in `llm.py` if extraction is off).

- [ ] **Step 2: If extraction is wrong**

Tune `_SYSTEM` in `src/ai_clerk/trips/llm.py` (consult the `claude-api` reference skill for model id / Messages-API specifics), re-run, and commit any prompt fix:
```bash
git add src/ai_clerk/trips/llm.py
git commit -m "fix: tune Claude slot-extraction prompt"
```

---

## Self-Review

**Spec coverage** (against `2026-06-16-phase3-trip-orchestration-design.md`):
- §1 chain gather→departure→search→rank→present→confirm→persist Trip → Tasks 8 (orchestrator), 7 (departure), 5 (search/rank), 9 (present), 11 (confirm), 10 (persist). ✓
- §1/§4 arrival-deadline (`arrive_by`, consider day-earlier, filter by deadline) → Task 5 `select_flights` + Task 3 `TripRequest.arrive_by`. ✓
- §2 LlmClient interface + FakeLlmClient (TDD) + ClaudeClient (prod) → Task 6. Claude = NLU only; orchestrator owns dialog → Task 8. ✓
- §2 in-memory dialog; Trip persisted at confirmation → Tasks 8 (in-memory `_dialogs`), 10/11 (persist on pick). ✓
- §2 ranking duration→price within policy (filter only when policy set) → Task 5. ✓
- §3 BookingProvider + MockProvider (`book()` raises) → Task 4. ✓
- §3 components (orchestrator/provider/ranking/llm/presentation/service) → Tasks 4–10. ✓
- §4 Trip model (no raw PII) + TripRequest → Tasks 2, 3. ✓
- §5 flow + `/cancel` → Tasks 8, 11. ✓
- §6 privacy: only trip context to Claude (PII never in prompt); `trip.create` gating → Task 6 (`_known` sends only trip fields), Task 11 (`_can_create`). ✓
- §7 error handling: Claude failure → friendly message (Task 11 try/except); no flights → message (Task 8); missing slots → clarifying question (Task 8); `book()` NotImplementedError (Task 4). ✓
- §8 testing offline with FakeLlmClient/MockProvider; ClaudeClient manual → Tasks 5–10 unit, Task 12 manual. ✓
- §9 anthropic dep + settings → Task 1. ✓
- Deferred (Plan 4/5): real providers, `book()`, OTP, full persistent saga, ground-access time, explicit hotel choice (MVP auto-attaches top hotel), order generation. Correctly out of scope. ✓

**Placeholder scan:** No TBD/TODO/"handle edge cases". Empty `trips/__init__.py` is intentionally empty. ✓

**Type consistency:** `TripRequest` fields (`dest_city`/`dest_iata`/`origin_city`/`origin_iata`/`depart_date`/`arrive_by`/`return_date`/`one_way`/`notes`) consistent across Tasks 3, 5, 6, 8, 10. `FlightOption`/`HotelOption` (with `duration`/`total_price`/`to_dict`) consistent across Tasks 3, 4, 5, 8, 9, 10. `LlmClient.fill_slots(current, message) -> TripRequest` consistent across Tasks 6, 8 (refines the spec's `SlotFillResult`: the LLM does pure extraction, the orchestrator owns missing-slot questions). `BookingProvider.search_flights(origin_iata, dest_iata, on_date)` / `search_hotels(city, checkin, checkout)` / `book(draft)` consistent across Tasks 4, 5, 8. `Orchestrator.handle_message(chat_id, message, profile) -> OrchestratorReply` and `pick(chat_id, index, profile) -> TripDraft | None` consistent across Tasks 8, 11. `render_flight_options(flights) -> (text, keyboard)` with `trip:pick:<i>` callbacks consistent across Tasks 9, 11. `TripService.create_confirmed_trip(chat_id, telegram_user_id, draft)` consistent across Tasks 10, 11. `LocationService.airport_for_city`/`resolve_departure(...).airport` consistent across Tasks 7, 8. ✓

> **Refinement note vs spec:** the spec's `SlotFillResult` (with `missing_fields`/`assistant_message`) is implemented as: `LlmClient.fill_slots` returns the updated `TripRequest` (pure extraction), and the `Orchestrator` deterministically computes missing slots and the clarifying question. This keeps dialog control testable without the LLM and is a deliberate, spec-consistent simplification.
