from .normalize import normalize, normalize_number, normalize_text, normalize_unit


def test_normalize_unit_aliases_match() -> None:
    assert normalize_unit("m3") == normalize_unit("m³") == "m³"
    assert normalize_unit("Stück") == normalize_unit("stk") == "Stk"


def test_normalize_unit_unknown_value_is_stripped_but_unchanged() -> None:
    assert normalize_unit(" l ") == "l"


def test_normalize_number_rounds() -> None:
    assert normalize_number(32.746) == 32.75
    assert normalize_number("32.746") == 32.75


def test_normalize_text_casefolds_and_strips() -> None:
    assert normalize_text("  Kies 0/4 ") == normalize_text("kies 0/4") == "kies 0/4"


def test_normalize_dispatches_by_field_name() -> None:
    assert normalize("unit", "m3") == "m³"
    assert normalize("quantity", 32.746) == 32.75
    assert normalize("ls_number", "LS-2024-0001") == "LS-2024-0001"
