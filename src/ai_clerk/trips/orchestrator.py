from dataclasses import dataclass, field, replace

from ai_clerk.location.service import LocationService
from ai_clerk.profile.dto import ProfileDTO
from ai_clerk.trips.llm import LlmClient
from ai_clerk.trips.options import FlightOption, HotelOption
from ai_clerk.trips.provider import BookingProvider
from ai_clerk.trips.ranking import select_flights
from ai_clerk.trips.request import OrchestratorReply, TripDraft, TripRequest


@dataclass
class _Dialog:
    request: TripRequest = field(default_factory=TripRequest)
    presented: list[FlightOption] = field(default_factory=list)


def _top_hotel(hotels: list[HotelOption], max_stars: int | None) -> HotelOption | None:
    eligible = [h for h in hotels if max_stars is None or h.stars <= max_stars]
    return min(eligible, key=lambda h: h.total_price) if eligible else None


class Orchestrator:
    """In-memory dialog state machine: fill slots -> clarify or search/present;
    pick -> TripDraft. Pure logic; no DB or aiogram."""

    def __init__(
        self,
        llm: LlmClient,
        location: LocationService,
        provider: BookingProvider,
        top_n: int = 3,
    ):
        self._llm = llm
        self._location = location
        self._provider = provider
        self._top_n = top_n
        self._dialogs: dict[int, _Dialog] = {}

    def cancel(self, chat_id: int) -> None:
        self._dialogs.pop(chat_id, None)

    async def handle_message(
        self, chat_id: int, message: str, profile: ProfileDTO | None
    ) -> OrchestratorReply:
        dialog = self._dialogs.setdefault(chat_id, _Dialog())
        dialog.request = await self._llm.fill_slots(dialog.request, message)
        req = dialog.request

        dest = self._location.airport_for_city(req.dest_city) if req.dest_city else None
        if dest is None:
            return OrchestratorReply(text="Куда летим? Укажите город назначения.")

        profile_default = None
        if profile is not None:
            profile_default = profile.default_departure_city or profile.default_departure_iata
        origin = self._location.resolve_departure(
            explicit_city=req.origin_city, profile_default=profile_default
        )
        if origin is None:
            return OrchestratorReply(
                text="Откуда вылетаем? Укажите город вылета "
                "(или сохраните его в профиле через /location)."
            )

        if req.depart_date is None and req.arrive_by is None:
            return OrchestratorReply(
                text="На какую дату планируете поездку "
                "(или к какому времени нужно быть на месте)?"
            )

        budget = profile.budget_limit if profile else None
        cabin = profile.cabin_class if profile else None
        flights = await select_flights(
            self._provider,
            origin.airport.iata,
            dest.iata,
            req,
            budget_limit=budget,
            cabin_class=cabin,
        )
        if not flights:
            return OrchestratorReply(
                text="Не нашёл подходящих рейсов на эти даты. "
                "Попробуем другие даты или направление?"
            )

        req.dest_iata = dest.iata
        req.origin_iata = origin.airport.iata
        dialog.presented = flights[: self._top_n]
        return OrchestratorReply(text="Нашёл варианты:", flights=dialog.presented)

    async def pick(
        self, chat_id: int, index: int, profile: ProfileDTO | None
    ) -> TripDraft | None:
        dialog = self._dialogs.get(chat_id)
        if dialog is None or not (0 <= index < len(dialog.presented)):
            return None
        flight = dialog.presented[index]
        req = dialog.request

        hotel = None
        if req.return_date is not None:
            checkin = req.depart_date or (req.arrive_by.date() if req.arrive_by else None)
            if checkin is not None:
                hotels = await self._provider.search_hotels(
                    req.dest_city, checkin, req.return_date
                )
                hotel = _top_hotel(hotels, profile.hotel_max_stars if profile else None)

        self._dialogs.pop(chat_id, None)
        # Snapshot the request so the draft is self-contained (immune to any
        # later dialog mutation).
        return TripDraft(request=replace(req), flight=flight, hotel=hotel)
