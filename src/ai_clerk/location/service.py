from dataclasses import dataclass

from ai_clerk.location.airports import Airport, AirportIndex


@dataclass
class DepartureResolution:
    airport: Airport
    source: str  # "explicit" | "coordinates" | "profile_default"


class LocationService:
    """Resolves the trip's departure airport per spec §5 priority chain."""

    def __init__(self, index: AirportIndex):
        self._index = index

    def resolve_departure(
        self,
        *,
        explicit_city: str | None = None,
        coords: tuple[float, float] | None = None,
        profile_default: str | None = None,
    ) -> DepartureResolution | None:
        if explicit_city:
            airport = self._index.by_city(explicit_city)
            if airport:
                return DepartureResolution(airport, "explicit")
        if coords:
            airport = self._index.nearest(coords[0], coords[1])
            if airport:
                return DepartureResolution(airport, "coordinates")
        if profile_default:
            airport = self._index.by_city(profile_default) or self._index.by_iata(
                profile_default
            )
            if airport:
                return DepartureResolution(airport, "profile_default")
        return None
