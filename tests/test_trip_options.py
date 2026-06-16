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
