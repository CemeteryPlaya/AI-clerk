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
    req = TripRequest(arrive_by=datetime(2026, 7, 14, 8, 50))
    ranked = await select_flights(MockProvider(), "ALA", "NQZ", req)
    assert ranked
    assert all(f.arrival <= datetime(2026, 7, 14, 8, 50) for f in ranked)
    assert any(f.departure.date() == date(2026, 7, 14) for f in ranked)


async def test_select_flights_no_date_returns_empty():
    assert await select_flights(MockProvider(), "ALA", "NQZ", TripRequest()) == []
