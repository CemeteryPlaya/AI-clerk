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
