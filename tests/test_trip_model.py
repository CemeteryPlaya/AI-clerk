from datetime import date

from sqlalchemy import select

from ai_clerk.db.models import Trip, TripStatus


async def test_trip_persists(session):
    session.add(
        Trip(
            chat_id=10,
            telegram_user_id=10,
            origin_iata="ALA",
            dest_city="Астана",
            dest_iata="NQZ",
            depart_date=date(2026, 7, 14),
            return_date=date(2026, 7, 16),
            selected_flight={"id": "F-A", "price": 45000.0},
            selected_hotel={"id": "H-4", "stars": 4},
            status=TripStatus.CONFIRMED.value,
        )
    )
    await session.commit()

    trip = (
        await session.execute(select(Trip).where(Trip.telegram_user_id == 10))
    ).scalar_one()
    assert trip.id is not None
    assert trip.status == "confirmed"
    assert trip.selected_flight["price"] == 45000.0
    assert trip.dest_iata == "NQZ"
    assert trip.created_at is not None


async def test_trip_updated_at_advances_on_update(session):
    trip = Trip(
        chat_id=1, telegram_user_id=1, dest_city="Астана",
        status=TripStatus.CONFIRMED.value,
    )
    session.add(trip)
    await session.commit()
    await session.refresh(trip)
    original_updated = trip.updated_at

    trip.dest_city = "Алматы"  # a real change -> triggers an UPDATE
    await session.commit()
    await session.refresh(trip)
    assert trip.updated_at > original_updated


async def test_trip_status_enum_values():
    assert TripStatus.CONFIRMED.value == "confirmed"
