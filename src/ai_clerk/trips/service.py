from sqlalchemy.ext.asyncio import AsyncSession

from ai_clerk.db.models import Trip, TripStatus
from ai_clerk.trips.request import TripDraft


class TripService:
    """Persists a confirmed Trip — the durable hand-off point for Plan 4."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def create_confirmed_trip(
        self, chat_id: int, telegram_user_id: int, draft: TripDraft
    ) -> Trip:
        req = draft.request
        trip = Trip(
            chat_id=chat_id,
            telegram_user_id=telegram_user_id,
            origin_iata=req.origin_iata,
            dest_city=req.dest_city,
            dest_iata=req.dest_iata,
            depart_date=req.checkin_date(),
            return_date=req.return_date,
            selected_flight=draft.flight.to_dict(),
            selected_hotel=draft.hotel.to_dict() if draft.hotel else None,
            status=TripStatus.CONFIRMED.value,
        )
        self._session.add(trip)
        await self._session.commit()
        await self._session.refresh(trip)
        return trip
