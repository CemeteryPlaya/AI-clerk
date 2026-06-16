from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from ai_clerk.trips.options import FlightOption

_CABIN_LABELS = {"economy": "эконом", "business": "бизнес"}


def _format_line(index: int, flight: FlightOption) -> str:
    minutes = int(flight.duration.total_seconds() // 60)
    hours, mins = divmod(minutes, 60)
    stops = "прямой" if flight.stops == 0 else f"{flight.stops} пересад."
    cabin = _CABIN_LABELS.get(flight.cabin, flight.cabin)
    # Arrival shows time only (KZ domestic flights arrive same-day at MVP); add
    # the date here if overnight/international routes are introduced later.
    return (
        f"{index + 1}. {flight.airline} "
        f"{flight.departure:%d.%m %H:%M}→{flight.arrival:%H:%M} "
        f"({hours}ч{mins:02d}м, {stops}), {int(flight.price)} ₸, {cabin}"
    )


def render_flight_options(
    flights: list[FlightOption],
) -> tuple[str, InlineKeyboardMarkup]:
    lines = [_format_line(i, f) for i, f in enumerate(flights)]
    text = (
        "Варианты перелёта (по времени в пути):\n"
        + "\n".join(lines)
        + "\n\nВыберите вариант кнопкой ниже:"
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=str(i + 1), callback_data=f"trip:pick:{i}")]
            for i in range(len(flights))
        ]
    )
    return text, keyboard
