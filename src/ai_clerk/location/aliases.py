def normalize_city(name: str) -> str:
    """Lowercase, replace ё→е, trim, and collapse internal whitespace."""
    return " ".join(name.strip().lower().replace("ё", "е").split())


# Common RU/KK/EN spellings of Kazakhstan cities → airport IATA code.
CITY_ALIASES: dict[str, str] = {
    # Almaty
    "алматы": "ALA", "almaty": "ALA", "алма-ата": "ALA", "alma-ata": "ALA",
    # Astana
    "астана": "NQZ", "astana": "NQZ", "нур-султан": "NQZ", "nur-sultan": "NQZ",
    "нурсултан": "NQZ", "nursultan": "NQZ", "целиноград": "NQZ",
    # Shymkent
    "шымкент": "CIT", "shymkent": "CIT", "чимкент": "CIT", "chimkent": "CIT",
    # Aktobe
    "актобе": "AKX", "aktobe": "AKX", "актюбинск": "AKX",
    # Atyrau
    "атырау": "GUW", "atyrau": "GUW", "гурьев": "GUW",
    # Karaganda
    "караганда": "KGF", "karaganda": "KGF", "qaraganda": "KGF",
    # Aktau
    "актау": "SCO", "aktau": "SCO", "шевченко": "SCO",
    # Taraz
    "тараз": "DMZ", "taraz": "DMZ", "джамбул": "DMZ", "жамбыл": "DMZ",
    # Pavlodar
    "павлодар": "PWQ", "pavlodar": "PWQ",
    # Oral / Uralsk
    "уральск": "URA", "oral": "URA", "орал": "URA",
    # Oskemen / Ust-Kamenogorsk
    "усть-каменогорск": "UKK", "oskemen": "UKK", "ust-kamenogorsk": "UKK",
    "оскемен": "UKK",
    # Kostanay
    "костанай": "KSN", "kostanay": "KSN", "кустанай": "KSN",
    # Kyzylorda
    "кызылорда": "KZO", "kyzylorda": "KZO", "qyzylorda": "KZO",
    # Petropavl
    "петропавловск": "PPK", "petropavl": "PPK", "петропавл": "PPK",
    # Semey
    "семей": "PLX", "semey": "PLX", "семипалатинск": "PLX",
    # Turkistan
    "туркестан": "HSA", "turkistan": "HSA", "turkestan": "HSA",
    # Kokshetau
    "кокшетау": "KOV", "kokshetau": "KOV",
}


def city_to_iata(name: str) -> str | None:
    """Return the IATA code for a city name (any supported spelling), or None."""
    return CITY_ALIASES.get(normalize_city(name))
