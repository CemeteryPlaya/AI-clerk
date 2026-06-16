from datetime import timedelta

from ai_clerk.trips.options import FlightOption
from ai_clerk.trips.provider import BookingProvider
from ai_clerk.trips.request import TripRequest


def rank_flights(
    options: list[FlightOption],
    *,
    budget_limit: float | None = None,
    cabin_class: str | None = None,
) -> list[FlightOption]:
    """Filter by policy (only where set), then sort by duration, then price."""
    filtered = [
        o
        for o in options
        if (budget_limit is None or o.price <= budget_limit)
        and (cabin_class is None or o.cabin == cabin_class)
    ]
    return sorted(filtered, key=lambda o: (o.duration, o.price))


async def select_flights(
    provider: BookingProvider,
    origin_iata: str,
    dest_iata: str,
    request: TripRequest,
    *,
    budget_limit: float | None = None,
    cabin_class: str | None = None,
) -> list[FlightOption]:
    """Search candidate dates, honour an arrival deadline (considering a
    departure the day before), and return the ranked result."""
    if request.depart_date is not None:
        candidate_dates = [request.depart_date]
    elif request.arrive_by is not None:
        deadline_day = request.arrive_by.date()
        candidate_dates = [deadline_day - timedelta(days=1), deadline_day]
    else:
        return []

    options: list[FlightOption] = []
    for on_date in candidate_dates:
        options.extend(await provider.search_flights(origin_iata, dest_iata, on_date))

    if request.arrive_by is not None:
        options = [o for o in options if o.arrival <= request.arrive_by]

    return rank_flights(options, budget_limit=budget_limit, cabin_class=cabin_class)
