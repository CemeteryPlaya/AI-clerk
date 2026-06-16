from dataclasses import replace
from datetime import date

from ai_clerk.trips.llm import ClaudeClient, FakeLlmClient
from ai_clerk.trips.request import TripRequest


async def test_fake_llm_applies_responder():
    def responder(current: TripRequest, message: str) -> TripRequest:
        return replace(current, dest_city="Астана", depart_date=date(2026, 7, 14))

    out = await FakeLlmClient(responder).fill_slots(TripRequest(), "хочу в Астану 14 июля")
    assert out.dest_city == "Астана"
    assert out.depart_date == date(2026, 7, 14)


def test_claude_client_constructs_without_network():
    # No API call happens at construction; anthropic is imported lazily in fill_slots.
    client = ClaudeClient(api_key="sk-test", model="claude-sonnet-4-6")
    assert client._model == "claude-sonnet-4-6"
