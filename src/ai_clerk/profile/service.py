from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_clerk.crypto import Cipher
from ai_clerk.db.models import Profile
from ai_clerk.profile.dto import ProfileDTO

_PREFERENCE_FIELDS = {
    "preferred_airlines",
    "preferred_hotels",
    "seat_preference",
    "meal_preference",
    "prefer_faster",
    "loyalty",
}
_POLICY_FIELDS = {"budget_limit", "cabin_class", "hotel_max_stars", "per_diem"}


class ProfileService:
    """Stores and reads traveler profiles; encrypts PII at rest via Cipher."""

    def __init__(self, session: AsyncSession, cipher: Cipher):
        self._session = session
        self._cipher = cipher

    async def upsert_identity(
        self,
        telegram_user_id: int,
        *,
        full_name: str | None = None,
        iin: str | None = None,
        document_type: str | None = None,
        document_number: str | None = None,
        birth_date: str | None = None,
        position: str | None = None,
        citizenship: str | None = None,
    ) -> ProfileDTO:
        profile = await self._get_or_create(telegram_user_id)
        if full_name is not None:
            profile.full_name_enc = self._cipher.encrypt(full_name)
        if iin is not None:
            profile.iin_enc = self._cipher.encrypt(iin)
        if document_number is not None:
            profile.document_number_enc = self._cipher.encrypt(document_number)
        if birth_date is not None:
            profile.birth_date_enc = self._cipher.encrypt(birth_date)
        if document_type is not None:
            profile.document_type = document_type
        if position is not None:
            profile.position = position
        if citizenship is not None:
            profile.citizenship = citizenship
        await self._session.commit()
        return await self.get_profile(telegram_user_id)

    async def set_default_departure(
        self, telegram_user_id: int, *, iata: str | None = None, city: str | None = None
    ) -> ProfileDTO:
        profile = await self._get_or_create(telegram_user_id)
        if iata is not None:
            profile.default_departure_iata = iata
        if city is not None:
            profile.default_departure_city = city
        await self._session.commit()
        return await self.get_profile(telegram_user_id)

    async def set_preferences(self, telegram_user_id: int, **prefs) -> ProfileDTO:
        return await self._set_fields(telegram_user_id, _PREFERENCE_FIELDS, prefs)

    async def set_policy(self, telegram_user_id: int, **limits) -> ProfileDTO:
        return await self._set_fields(telegram_user_id, _POLICY_FIELDS, limits)

    async def get_profile(self, telegram_user_id: int) -> ProfileDTO | None:
        profile = await self._get(telegram_user_id)
        if profile is None:
            return None
        return ProfileDTO(
            telegram_user_id=profile.telegram_user_id,
            full_name=self._dec(profile.full_name_enc),
            iin=self._dec(profile.iin_enc),
            document_type=profile.document_type,
            document_number=self._dec(profile.document_number_enc),
            birth_date=self._dec(profile.birth_date_enc),
            position=profile.position,
            citizenship=profile.citizenship,
            default_departure_iata=profile.default_departure_iata,
            default_departure_city=profile.default_departure_city,
            preferred_airlines=profile.preferred_airlines or [],
            preferred_hotels=profile.preferred_hotels or [],
            seat_preference=profile.seat_preference,
            meal_preference=profile.meal_preference,
            prefer_faster=profile.prefer_faster,
            loyalty=profile.loyalty or [],
            budget_limit=profile.budget_limit,
            cabin_class=profile.cabin_class,
            hotel_max_stars=profile.hotel_max_stars,
            per_diem=profile.per_diem,
        )

    async def _set_fields(
        self, telegram_user_id: int, allowed: set[str], values: dict
    ) -> ProfileDTO:
        unknown = set(values) - allowed
        if unknown:
            raise ValueError(f"unknown fields: {sorted(unknown)}")
        profile = await self._get_or_create(telegram_user_id)
        for key, value in values.items():
            setattr(profile, key, value)
        await self._session.commit()
        return await self.get_profile(telegram_user_id)

    async def _get(self, telegram_user_id: int) -> Profile | None:
        result = await self._session.execute(
            select(Profile).where(Profile.telegram_user_id == telegram_user_id)
        )
        return result.scalar_one_or_none()

    async def _get_or_create(self, telegram_user_id: int) -> Profile:
        profile = await self._get(telegram_user_id)
        if profile is None:
            # Set prefer_faster explicitly so the in-memory object matches the DB
            # default before any refresh (session uses expire_on_commit=False).
            profile = Profile(telegram_user_id=telegram_user_id, prefer_faster=True)
            self._session.add(profile)
        return profile

    def _dec(self, token: str | None) -> str | None:
        return self._cipher.decrypt(token) if token is not None else None
