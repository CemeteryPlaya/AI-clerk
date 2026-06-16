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
