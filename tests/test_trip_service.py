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
