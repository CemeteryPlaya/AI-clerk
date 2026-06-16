from datetime import datetime

from ai_clerk.trips.options import FlightOption
from ai_clerk.trips.presentation import render_flight_options


def _flight(suffix: str, dep_h: int, arr_h: int, price: float, stops: int = 0) -> FlightOption:
    return FlightOption(
        id=f"F-{suffix}", airline="Air Astana", origin_iata="ALA", dest_iata="NQZ",
        departure=datetime(2026, 7, 14, dep_h, 0), arrival=datetime(2026, 7, 14, arr_h, 0),
        stops=stops, price=price, cabin="economy",
    )


def test_render_lists_options_with_buttons():
    flights = [_flight("A", 7, 9, 45000.0), _flight("B", 10, 14, 28000.0, stops=1)]
    text, keyboard = render_flight_options(flights)

    assert "Air Astana" in text
    assert "1." in text and "2." in text
    buttons = [b for row in keyboard.inline_keyboard for b in row]
    assert len(buttons) == 2
    assert buttons[0].callback_data == "trip:pick:0"
    assert buttons[1].callback_data == "trip:pick:1"
