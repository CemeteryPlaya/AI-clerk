from datetime import datetime

from ai_clerk.trips.options import FlightOption
from ai_clerk.trips.request import OrchestratorReply, TripDraft, TripRequest


def test_trip_request_defaults():
    r = TripRequest()
    assert r.dest_city is None
    assert r.one_way is True
    assert r.arrive_by is None


def test_orchestrator_reply_defaults_to_no_flights():
    reply = OrchestratorReply(text="hi")
    assert reply.flights == []


def test_trip_draft_holds_selection():
    flight = FlightOption(
        id="F-A", airline="A", origin_iata="ALA", dest_iata="NQZ",
        departure=datetime(2026, 7, 14, 7, 0), arrival=datetime(2026, 7, 14, 8, 45),
        stops=0, price=45000.0, cabin="economy",
    )
    draft = TripDraft(request=TripRequest(dest_city="Астана"), flight=flight)
    assert draft.flight.id == "F-A"
    assert draft.hotel is None
