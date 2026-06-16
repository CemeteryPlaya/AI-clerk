import json
from collections.abc import Callable
from datetime import date, datetime
from typing import Protocol

from ai_clerk.trips.request import TripRequest


class LlmClient(Protocol):
    async def fill_slots(self, current: TripRequest, message: str) -> TripRequest: ...


class FakeLlmClient:
    """Test double: a responder function maps (current, message) -> updated request."""

    def __init__(self, responder: Callable[[TripRequest, str], TripRequest]):
        self._responder = responder

    async def fill_slots(self, current: TripRequest, message: str) -> TripRequest:
        return self._responder(current, message)


_SYSTEM = (
    "Ты помощник по командировкам. Извлеки из сообщения параметры поездки и верни "
    "СТРОГО JSON-объект с ключами: dest_city, origin_city (строки или null), "
    "depart_date, return_date (даты YYYY-MM-DD или null), arrive_by (дата-время "
    "ISO 8601 или null), one_way (true/false), notes (строка или null). "
    "Сохраняй уже известные значения, обновляй только то, что явно сказано. "
    "Никогда не запрашивай и не упоминай персональные данные (ИИН, паспорт, ФИО). "
    "Возвращай только JSON, без пояснений."
)


def _known(current: TripRequest) -> dict:
    return {
        "dest_city": current.dest_city,
        "origin_city": current.origin_city,
        "depart_date": current.depart_date.isoformat() if current.depart_date else None,
        "return_date": current.return_date.isoformat() if current.return_date else None,
        "arrive_by": current.arrive_by.isoformat() if current.arrive_by else None,
        "one_way": current.one_way,
        "notes": current.notes,
    }


def _extract_json(text: str) -> dict:
    """Parse the JSON object from the model reply, tolerating markdown fences
    or surrounding prose by extracting the outermost {...}."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"no JSON object in model reply: {text!r}")
    return json.loads(text[start : end + 1])


def _merge(current: TripRequest, data: dict) -> TripRequest:
    """Merge extracted slots into the current request. Slots are append-only:
    a null/missing value preserves the existing one (use /cancel to start over).
    Resolved iata codes are carried through untouched."""

    def _date(value):
        return date.fromisoformat(value) if value else None

    def _dt(value):
        return datetime.fromisoformat(value) if value else None

    return TripRequest(
        dest_city=data.get("dest_city") or current.dest_city,
        dest_iata=current.dest_iata,
        origin_city=data.get("origin_city") or current.origin_city,
        origin_iata=current.origin_iata,
        depart_date=_date(data.get("depart_date")) or current.depart_date,
        arrive_by=_dt(data.get("arrive_by")) or current.arrive_by,
        return_date=_date(data.get("return_date")) or current.return_date,
        one_way=(
            bool(data["one_way"]) if data.get("one_way") is not None else current.one_way
        ),
        notes=data.get("notes") or current.notes,
    )


class ClaudeClient:
    """Real adapter: extracts trip slots from free text via the Anthropic API.

    `anthropic` is imported lazily so the module loads without it; the prompt
    carries only trip context — never identity PII."""

    def __init__(self, api_key: str, model: str):
        # Imported here (not at module level) so the module loads without the
        # anthropic SDK; the client (and its connection pool) is built once and
        # reused across the multi-turn conversation. Construction makes no
        # network call.
        from anthropic import AsyncAnthropic

        self._model = model
        self._client = AsyncAnthropic(api_key=api_key)

    async def fill_slots(self, current: TripRequest, message: str) -> TripRequest:
        user = json.dumps(
            {"known": _known(current), "message": message}, ensure_ascii=False
        )
        resp = await self._client.messages.create(
            model=self._model,
            max_tokens=512,
            system=_SYSTEM,
            messages=[{"role": "user", "content": user}],
        )
        data = _extract_json(resp.content[0].text)
        return _merge(current, data)
