from pathlib import Path

from ai_clerk.location.airports import AirportIndex
from ai_clerk.location.service import LocationService

FIXTURE = Path(__file__).parent / "fixtures" / "airports_sample.csv"


def _service() -> LocationService:
    return LocationService(AirportIndex.from_csv(FIXTURE))


def test_explicit_city_wins():
    res = _service().resolve_departure(
        explicit_city="Астана",
        coords=(43.238949, 76.889709),  # would resolve to ALA if coords were used
        profile_default="Шымкент",
    )
    assert res.airport.iata == "NQZ"
    assert res.source == "explicit"


def test_coords_used_when_no_explicit_city():
    res = _service().resolve_departure(coords=(43.238949, 76.889709))
    assert res.airport.iata == "ALA"
    assert res.source == "coordinates"


def test_unresolvable_explicit_falls_through_to_coords():
    # An explicit city we can't resolve must not abort the chain; coords win.
    res = _service().resolve_departure(
        explicit_city="Париж",  # not in index
        coords=(43.238949, 76.889709),  # resolves to ALA
    )
    assert res.airport.iata == "ALA"
    assert res.source == "coordinates"


def test_profile_default_used_last():
    res = _service().resolve_departure(profile_default="ALA")
    assert res.airport.iata == "ALA"
    assert res.source == "profile_default"


def test_profile_default_resolves_city_name():
    res = _service().resolve_departure(profile_default="Алматы")
    assert res.airport.iata == "ALA"
    assert res.source == "profile_default"


def test_unresolvable_returns_none():
    assert _service().resolve_departure(explicit_city="Париж") is None


def test_no_inputs_returns_none():
    assert _service().resolve_departure() is None
