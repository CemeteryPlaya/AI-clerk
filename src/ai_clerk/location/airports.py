import csv
import math
from dataclasses import dataclass
from pathlib import Path

from ai_clerk.location.aliases import city_to_iata, normalize_city

_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "airports_kz.csv"
_EARTH_RADIUS_KM = 6371.0


@dataclass(frozen=True)
class Airport:
    iata: str
    name: str
    city: str
    lat: float
    lon: float
    country: str


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * _EARTH_RADIUS_KM * math.asin(math.sqrt(a))


class AirportIndex:
    """In-memory airport lookup: by IATA, by city (alias-aware), and nearest."""

    def __init__(self, airports: list[Airport]):
        self._airports = airports
        self._by_iata = {a.iata.upper(): a for a in airports if a.iata}
        self._by_city: dict[str, Airport] = {}
        for airport in airports:
            if airport.city:
                self._by_city.setdefault(normalize_city(airport.city), airport)

    @classmethod
    def from_csv(cls, path: str | Path) -> "AirportIndex":
        airports: list[Airport] = []
        with open(path, newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                iata = (row.get("iata_code") or "").strip()
                lat = row.get("latitude_deg")
                lon = row.get("longitude_deg")
                if not iata or not lat or not lon:
                    continue
                airports.append(
                    Airport(
                        iata=iata,
                        name=(row.get("name") or "").strip(),
                        city=(row.get("municipality") or "").strip(),
                        lat=float(lat),
                        lon=float(lon),
                        country=(row.get("iso_country") or "").strip(),
                    )
                )
        return cls(airports)

    @classmethod
    def bundled(cls) -> "AirportIndex":
        return cls.from_csv(_DATA_PATH)

    def by_iata(self, code: str) -> Airport | None:
        return self._by_iata.get(code.strip().upper())

    def by_city(self, name: str) -> Airport | None:
        iata = city_to_iata(name)
        if iata and iata in self._by_iata:
            return self._by_iata[iata]
        return self._by_city.get(normalize_city(name))

    def nearest(self, lat: float, lon: float) -> Airport | None:
        if not self._airports:
            return None
        return min(
            self._airports,
            key=lambda a: _haversine_km(lat, lon, a.lat, a.lon),
        )
