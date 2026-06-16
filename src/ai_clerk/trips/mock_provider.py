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
