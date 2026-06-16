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


async def test_unresolvable_destination_names_the_city():
    orch = _orchestrator(lambda cur, msg: replace(cur, dest_city="Париж"))
    reply = await orch.handle_message(1, "хочу в Париж", _profile(default_departure_city="Алматы"))
    assert reply.flights == []
    assert "париж" in reply.text.lower()  # distinguishes 'not found' from 'missing'


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
    assert await orch.pick(1, 0, _profile()) is None  # dialog cleared


async def test_multi_turn_accumulates_then_presents():
    # Slots filled across two turns on the same chat: turn 1 adds the city
    # (orchestrator asks for the date), turn 2 adds the date (now it searches).
    calls: list[str] = []

    def responder(cur: TripRequest, msg: str) -> TripRequest:
        calls.append(msg)
        if len(calls) == 1:
            return replace(cur, dest_city="Астана")
        return replace(cur, depart_date=date(2026, 7, 14))

    orch = _orchestrator(responder)
    profile = _profile(default_departure_city="Алматы")

    first = await orch.handle_message(1, "в Астану", profile)
    assert first.flights == []
    assert "дат" in first.text.lower()

    second = await orch.handle_message(1, "14 июля", profile)
    assert second.flights  # dest_city from turn 1 persisted -> now complete
    assert second.flights[0].dest_iata == "NQZ"


async def test_no_flights_when_policy_excludes_all():
    orch = _orchestrator(
        lambda cur, msg: replace(cur, dest_city="Астана", depart_date=date(2026, 7, 14))
    )
    reply = await orch.handle_message(
        1, "в Астану 14 июля",
        _profile(default_departure_city="Алматы", budget_limit=1000.0),
    )
    assert reply.flights == []
    assert "не нашёл" in reply.text.lower()


async def test_pick_one_way_has_no_hotel():
    orch = _orchestrator(
        lambda cur, msg: replace(cur, dest_city="Астана", depart_date=date(2026, 7, 14))
    )  # no return_date -> one-way
    await orch.handle_message(1, "в Астану 14 июля", _profile(default_departure_city="Алматы"))
    draft = await orch.pick(1, 0, _profile(default_departure_city="Алматы"))
    assert draft is not None
    assert draft.hotel is None


async def test_pick_out_of_range_returns_none():
    orch = _orchestrator(lambda cur, msg: cur)
    assert await orch.pick(999, 0, _profile()) is None
