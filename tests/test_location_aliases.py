from ai_clerk.location.aliases import city_to_iata, normalize_city


def test_normalize_lowercases_trims_and_collapses():
    assert normalize_city("  Алма-Ата  ") == "алма-ата"
    assert normalize_city("Нур-Султан") == "нур-султан"


def test_aliases_map_to_iata():
    assert city_to_iata("Алматы") == "ALA"
    assert city_to_iata("almaty") == "ALA"
    assert city_to_iata("Алма-Ата") == "ALA"
    assert city_to_iata("Астана") == "NQZ"
    assert city_to_iata("Нур-Султан") == "NQZ"
    assert city_to_iata("Шымкент") == "CIT"


def test_unknown_city_returns_none():
    assert city_to_iata("Париж") is None
