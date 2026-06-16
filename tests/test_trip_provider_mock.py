from datetime import date

import pytest

from ai_clerk.trips.mock_provider import MockProvider


async def test_search_flights_returns_options():
    flights = await MockProvider().search_flights("ALA", "NQZ", date(2026, 7, 14))
    assert len(flights) == 3
    assert all(f.origin_iata == "ALA" and f.dest_iata == "NQZ" for f in flights)
    assert all(f.departure.date() == date(2026, 7, 14) for f in flights)
    assert len({f.id for f in flights}) == 3


async def test_search_flights_is_deterministic():
    # Downstream ranking/deadline tests rely on stable results.
    provider = MockProvider()
    first = await provider.search_flights("ALA", "NQZ", date(2026, 7, 14))
    second = await provider.search_flights("ALA", "NQZ", date(2026, 7, 14))
    assert first == second


async def test_search_hotels_scales_nights():
    hotels = await MockProvider().search_hotels("Астана", date(2026, 7, 14), date(2026, 7, 16))
    assert len(hotels) == 3
    assert all(h.nights == 2 for h in hotels)


async def test_book_not_implemented():
    with pytest.raises(NotImplementedError):
        await MockProvider().book(object())
