"""Clean, internally-consistent construction of Bestellung -> Lieferscheine ->
Rechnung. Nothing in this module ever introduces an inconsistency; that is
the sole job of :mod:`generator.discrepancies`.
"""

from __future__ import annotations

import random
from datetime import date, timedelta

from faker import Faker

from .models import (
    Bestellposition,
    Bestellung,
    Lieferschein,
    MasterData,
    Rechnung,
    RechnungsPosition,
    Unit,
)

BASE_DATE = date(2024, 1, 1)

QUANTITY_RANGES: dict[Unit, tuple[float, float]] = {
    Unit.TONNE: (5.0, 150.0),
    Unit.CUBIC_METER: (5.0, 60.0),
    Unit.KILOGRAM: (200.0, 4000.0),
    Unit.PIECE: (10.0, 300.0),
}

BULK_UNITS = {Unit.TONNE, Unit.CUBIC_METER, Unit.KILOGRAM}
BULK_DEVIATION = 0.03


def _random_date(rng: random.Random, max_offset_days: int = 300) -> date:
    return BASE_DATE + timedelta(days=rng.randint(0, max_offset_days))


def _random_quantity(rng: random.Random, unit: Unit) -> float:
    low, high = QUANTITY_RANGES[unit]
    value = rng.uniform(low, high)
    if unit == Unit.PIECE:
        return float(round(value))
    return round(value, 2)


def build_bestellung(rng: random.Random, order_index: int, master: MasterData) -> Bestellung:
    supplier = rng.choice(master.suppliers)
    company = rng.choice(master.companies)
    baustelle = rng.choice([bs for bs in master.baustellen if bs.company_id == company.id] or master.baustellen)

    n_positions = rng.randint(1, 3)
    materials = rng.sample(master.materials, k=n_positions)

    positions = []
    for pos_no, material in enumerate(materials, start=1):
        quantity = _random_quantity(rng, material.unit)
        unit_price = round(rng.uniform(material.price_min, material.price_max), 2)
        positions.append(
            Bestellposition(
                position_no=pos_no,
                material_id=material.id,
                quantity=quantity,
                unit=material.unit,
                unit_price=unit_price,
            )
        )

    return Bestellung(
        id=f"BST-2024-{order_index:04d}",
        order_number=f"BST-2024-{order_index:04d}",
        date=_random_date(rng),
        supplier_id=supplier.id,
        company_id=company.id,
        baustelle_id=baustelle.id,
        positions=positions,
    )


def _split_quantity(rng: random.Random, total: float, n_parts: int, unit: Unit) -> list[float]:
    """Split `total` into `n_parts` randomly-weighted parts. Bulk units get an
    independent +/-3% weighing deviation per part (bounded so the *sum* also
    stays within +/-3% of `total`, since it is a weighted average of the
    per-part deviations). Stk is split into exact integers with no deviation.
    """
    raw_weights = [rng.random() + 0.3 for _ in range(n_parts)]
    weight_sum = sum(raw_weights)
    shares = [total * w / weight_sum for w in raw_weights]

    if unit == Unit.PIECE:
        int_shares = [int(s) for s in shares]
        remainder = int(round(total)) - sum(int_shares)
        for i in range(remainder):
            int_shares[i % n_parts] += 1
        return [float(s) for s in int_shares]

    deviated = [s * (1 + rng.uniform(-BULK_DEVIATION, BULK_DEVIATION)) for s in shares]
    return [round(s, 2) for s in deviated]


def build_lieferscheine_for_position(
    rng: random.Random,
    faker: Faker,
    bestellung: Bestellung,
    position: Bestellposition,
    ls_start_index: int,
) -> tuple[list[Lieferschein], int]:
    n_notes = rng.randint(1, 4)
    quantities = _split_quantity(rng, position.quantity, n_notes, position.unit)

    notes = []
    ls_index = ls_start_index
    for quantity in quantities:
        ls_index += 1
        notes.append(
            Lieferschein(
                id=f"LS-2024-{ls_index:04d}",
                ls_number=f"LS-2024-{ls_index:04d}",
                order_number_ref=bestellung.order_number,
                bestellung_id=bestellung.id,
                position_no=position.position_no,
                date=_random_date(rng),
                material_id=position.material_id,
                quantity=quantity,
                unit=position.unit,
                signed=True,
                driver_name=faker.name(),
                vehicle_plate=faker.license_plate(),
            )
        )
    return notes, ls_index


def build_rechnung(bestellung: Bestellung, lieferscheine: list[Lieferschein]) -> Rechnung:
    positions = []
    for order_position in bestellung.positions:
        delivered = [ls for ls in lieferscheine if ls.position_no == order_position.position_no]
        quantity = round(sum(ls.quantity for ls in delivered), 2)
        total = round(quantity * order_position.unit_price, 2)
        positions.append(
            RechnungsPosition(
                position_no=order_position.position_no,
                material_id=order_position.material_id,
                quantity=quantity,
                unit=order_position.unit,
                unit_price=order_position.unit_price,
                total=total,
            )
        )

    latest_ls_date = max((ls.date for ls in lieferscheine), default=bestellung.date)
    return Rechnung(
        id=f"RE-2024-{bestellung.order_number.split('-')[-1]}",
        re_number=f"RE-2024-{bestellung.order_number.split('-')[-1]}",
        order_number_ref=bestellung.order_number,
        bestellung_id=bestellung.id,
        date=latest_ls_date,
        positions=positions,
        total_amount=round(sum(p.total for p in positions), 2),
    )
