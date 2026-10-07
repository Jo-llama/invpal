"""Injects exactly one plausible discrepancy into a clean OrderBundle, with a
probability of DISCREPANCY_RATE per order. Each injector mutates one document
field without updating the rest of the bundle -- mirroring how a real-world
mismatch enters the paper trail -- and returns a Discrepancy record stating
the expected vs. actual value.
"""

from __future__ import annotations

import random

from .models import Discrepancy, DiscrepancyType, OrderBundle, Unit

DISCREPANCY_RATE = 0.2

# Clean deliveries carry up to +/-3% natural weighing deviation (see
# business_logic.BULK_DEVIATION). A planted QTY_MISMATCH must read as a real
# mismatch, not noise, so its minimum magnitude is set well above that: 8%
# is already ~2.7x the natural tolerance, comfortably outside it even after
# 2-decimal rounding.
QTY_MISMATCH_MIN_DEVIATION = 0.08
QTY_MISMATCH_MAX_DEVIATION = 0.30

# Clean invoices bill at exactly the order's unit_price (zero natural
# deviation), so in principle any nonzero difference is already a true
# mismatch. We still enforce the same 8% floor as QTY_MISMATCH so planted
# price deviations read as unambiguous overbilling/underbilling rather than
# a rounding artifact, and so the two discrepancy types are tuned
# consistently.
PRICE_DEVIATION_MIN_DEVIATION = 0.08
PRICE_DEVIATION_MAX_DEVIATION = 0.30

_OTHER_UNITS = {
    Unit.TONNE: Unit.CUBIC_METER,
    Unit.CUBIC_METER: Unit.TONNE,
    Unit.KILOGRAM: Unit.PIECE,
    Unit.PIECE: Unit.KILOGRAM,
}


def _deviation_factor(rng: random.Random, min_deviation: float, max_deviation: float) -> float:
    """A multiplicative factor at least `min_deviation` away from 1.0, in a
    random direction, up to `max_deviation` away."""
    magnitude = rng.uniform(min_deviation, max_deviation)
    sign = rng.choice([1, -1])
    return 1 + sign * magnitude


def _inject_qty_mismatch(rng: random.Random, bundle: OrderBundle) -> Discrepancy:
    position = rng.choice(bundle.rechnung.positions)
    delivered_qty = position.quantity
    factor = _deviation_factor(rng, QTY_MISMATCH_MIN_DEVIATION, QTY_MISMATCH_MAX_DEVIATION)
    new_qty = round(delivered_qty * factor, 2)
    position.quantity = new_qty
    position.total = round(new_qty * position.unit_price, 2)
    bundle.rechnung.total_amount = round(sum(p.total for p in bundle.rechnung.positions), 2)
    return Discrepancy(
        bestellung_id=bundle.bestellung.id,
        order_number=bundle.bestellung.order_number,
        type=DiscrepancyType.QTY_MISMATCH,
        document_type="Rechnung",
        document_id=bundle.rechnung.id,
        field=f"positions[position_no={position.position_no}].quantity",
        expected_value=str(delivered_qty),
        actual_value=str(new_qty),
        description="Invoiced quantity does not match the sum of delivered Lieferschein quantities.",
    )


def _inject_missing_signature(rng: random.Random, bundle: OrderBundle) -> Discrepancy:
    note = rng.choice(bundle.lieferscheine)
    note.signed = False
    return Discrepancy(
        bestellung_id=bundle.bestellung.id,
        order_number=bundle.bestellung.order_number,
        type=DiscrepancyType.MISSING_SIGNATURE,
        document_type="Lieferschein",
        document_id=note.id,
        field="signed",
        expected_value="True",
        actual_value="False",
        description="Lieferschein is missing the delivery signature.",
    )


def _inject_wrong_order_ref(rng: random.Random, bundle: OrderBundle) -> Discrepancy:
    note = rng.choice(bundle.lieferscheine)
    true_ref = note.order_number_ref
    wrong_ref = true_ref
    while wrong_ref == true_ref:
        wrong_ref = f"BST-2024-{rng.randint(1, 9999):04d}"
    note.order_number_ref = wrong_ref
    return Discrepancy(
        bestellung_id=bundle.bestellung.id,
        order_number=bundle.bestellung.order_number,
        type=DiscrepancyType.WRONG_ORDER_REF,
        document_type="Lieferschein",
        document_id=note.id,
        field="order_number_ref",
        expected_value=true_ref,
        actual_value=wrong_ref,
        description="Lieferschein references an order number that does not match its actual order.",
    )


def _inject_duplicate_note(rng: random.Random, bundle: OrderBundle) -> Discrepancy:
    original = rng.choice(bundle.lieferscheine)
    duplicate = original.model_copy(update={"id": f"{original.id}-DUP", "ls_number": f"{original.ls_number}-DUP"})
    bundle.lieferscheine.append(duplicate)
    return Discrepancy(
        bestellung_id=bundle.bestellung.id,
        order_number=bundle.bestellung.order_number,
        type=DiscrepancyType.DUPLICATE_NOTE,
        document_type="Lieferschein",
        document_id=duplicate.id,
        field="ls_number",
        expected_value=original.ls_number,
        actual_value=duplicate.ls_number,
        description="A Lieferschein was entered twice for the same delivery.",
    )


def _inject_unit_mismatch(rng: random.Random, bundle: OrderBundle) -> Discrepancy:
    note = rng.choice(bundle.lieferscheine)
    true_unit = note.unit
    note.unit = _OTHER_UNITS[true_unit]
    return Discrepancy(
        bestellung_id=bundle.bestellung.id,
        order_number=bundle.bestellung.order_number,
        type=DiscrepancyType.UNIT_MISMATCH,
        document_type="Lieferschein",
        document_id=note.id,
        field="unit",
        expected_value=true_unit.value,
        actual_value=note.unit.value,
        description="Lieferschein unit does not match the order line's unit.",
    )


def _inject_price_deviation(rng: random.Random, bundle: OrderBundle) -> Discrepancy:
    order_position = rng.choice(bundle.bestellung.positions)
    rechnung_position = next(p for p in bundle.rechnung.positions if p.position_no == order_position.position_no)
    true_price = order_position.unit_price
    factor = _deviation_factor(rng, PRICE_DEVIATION_MIN_DEVIATION, PRICE_DEVIATION_MAX_DEVIATION)
    new_price = round(true_price * factor, 2)
    rechnung_position.unit_price = new_price
    rechnung_position.total = round(rechnung_position.quantity * new_price, 2)
    bundle.rechnung.total_amount = round(sum(p.total for p in bundle.rechnung.positions), 2)
    return Discrepancy(
        bestellung_id=bundle.bestellung.id,
        order_number=bundle.bestellung.order_number,
        type=DiscrepancyType.PRICE_DEVIATION,
        document_type="Rechnung",
        document_id=bundle.rechnung.id,
        field=f"positions[position_no={rechnung_position.position_no}].unit_price",
        expected_value=str(true_price),
        actual_value=str(new_price),
        description="Invoiced unit price deviates from the agreed order price.",
    )


_INJECTORS = {
    DiscrepancyType.QTY_MISMATCH: _inject_qty_mismatch,
    DiscrepancyType.MISSING_SIGNATURE: _inject_missing_signature,
    DiscrepancyType.WRONG_ORDER_REF: _inject_wrong_order_ref,
    DiscrepancyType.DUPLICATE_NOTE: _inject_duplicate_note,
    DiscrepancyType.UNIT_MISMATCH: _inject_unit_mismatch,
    DiscrepancyType.PRICE_DEVIATION: _inject_price_deviation,
}


def maybe_inject_discrepancy(rng: random.Random, bundle: OrderBundle) -> Discrepancy | None:
    if rng.random() >= DISCREPANCY_RATE:
        return None
    dtype = rng.choice(list(DiscrepancyType))
    return _INJECTORS[dtype](rng, bundle)
