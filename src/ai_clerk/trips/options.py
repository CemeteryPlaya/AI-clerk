from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class FlightOption:
    id: str
    airline: str
    origin_iata: str
    dest_iata: str
    departure: datetime
    arrival: datetime
    stops: int
    price: float
    cabin: str  # "economy" | "business"

    @property
    def duration(self) -> timedelta:
        return self.arrival - self.departure

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "airline": self.airline,
            "origin_iata": self.origin_iata,
            "dest_iata": self.dest_iata,
            "departure": self.departure.isoformat(),
            "arrival": self.arrival.isoformat(),
            "stops": self.stops,
            "price": self.price,
            "cabin": self.cabin,
        }


@dataclass(frozen=True)
class HotelOption:
    id: str
    name: str
    stars: int
    price_per_night: float
    nights: int
    address: str

    @property
    def total_price(self) -> float:
        return self.price_per_night * self.nights

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "stars": self.stars,
            "price_per_night": self.price_per_night,
            "nights": self.nights,
            "total_price": self.total_price,
            "address": self.address,
        }
