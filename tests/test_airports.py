from pathlib import Path

from ai_clerk.location.airports import AirportIndex

FIXTURE = Path(__file__).parent / "fixtures" / "airports_sample.csv"


def _index() -> AirportIndex:
    return AirportIndex.from_csv(FIXTURE)


def test_by_iata():
    airport = _index().by_iata("ala")
    assert airport is not None
    assert airport.iata == "ALA"
    assert airport.city == "Almaty"


def test_by_city_via_alias():
    # "Алматы" is an alias mapping to ALA even though the CSV city is "Almaty".
    assert _index().by_city("Алматы").iata == "ALA"


def test_by_city_via_municipality():
    assert _index().by_city("Astana").iata == "NQZ"


def test_nearest_returns_closest_airport():
    index = _index()
    # Coordinates in central Almaty → ALA, not NQZ/CIT.
    assert index.nearest(43.238949, 76.889709).iata == "ALA"
    # Coordinates near Astana → NQZ.
    assert index.nearest(51.160520, 71.470355).iata == "NQZ"


def test_bundled_dataset_loads():
    index = AirportIndex.bundled()
    assert index.by_iata("NQZ") is not None
    assert index.by_iata("ALA") is not None
