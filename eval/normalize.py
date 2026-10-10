"""Per-field normalization rules for the "normalized" accuracy variant.

Fields with no rule here fall back to exact equality for both the exact and normalized metric
(dates are already normalized by Pydantic's type coercion to `date`, so no extra rule is needed).
"""

from __future__ import annotations

from typing import Any, Callable

_UNIT_ALIASES = {
    "m3": "m³",
    "m³": "m³",
    "m^3": "m³",
    "t": "t",
    "to": "t",
    "tonne": "t",
    "tonnen": "t",
    "kg": "kg",
    "stk": "Stk",
    "stück": "Stk",
    "stueck": "Stk",
}


def normalize_unit(value: Any) -> str:
    text = str(value).strip().lower()
    return _UNIT_ALIASES.get(text, str(value).strip())


def normalize_number(value: Any) -> float:
    return round(float(value), 2)


def normalize_text(value: Any) -> str:
    return str(value).strip().casefold()


FIELD_NORMALIZERS: dict[str, Callable[[Any], Any]] = {
    "unit": normalize_unit,
    "quantity": normalize_number,
    "unit_price": normalize_number,
    "total": normalize_number,
    "total_amount": normalize_number,
    "material_name": normalize_text,
    "driver_name": normalize_text,
    "vehicle_plate": normalize_text,
}


def normalize(field_name: str, value: Any) -> Any:
    normalizer = FIELD_NORMALIZERS.get(field_name)
    if normalizer is None:
        return value
    try:
        return normalizer(value)
    except (TypeError, ValueError):
        return value
