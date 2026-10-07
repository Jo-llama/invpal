import random
from collections import Counter

from faker import Faker

from .business_logic import BULK_DEVIATION, build_bestellung, build_lieferscheine_for_position, build_rechnung
from .discrepancies import (
    DISCREPANCY_RATE,
    PRICE_DEVIATION_MIN_DEVIATION,
    QTY_MISMATCH_MIN_DEVIATION,
    _inject_duplicate_note,
    _inject_missing_signature,
    _inject_price_deviation,
    _inject_qty_mismatch,
    _inject_unit_mismatch,
    _inject_wrong_order_ref,
)
from .master_data import build_master_data
from .models import DiscrepancyType, OrderBundle

QTY_TOLERANCE = 0.04
PRICE_TOLERANCE = 0.01

# Rounding to 2 decimals can shave a hair off the nominal deviation for
# small quantities/prices; this is just floating-point slack, not a
# loosening of the enforced minimum.
ROUNDING_SLACK = 0.005


def _clean_bundle(seed: int, order_index: int = 1) -> OrderBundle:
    rng = random.Random(seed)
    faker = Faker("de_DE")
    faker.seed_instance(seed)
    master = build_master_data(rng, faker)
    bestellung = build_bestellung(rng, order_index, master)

    lieferscheine = []
    ls_index = 0
    for position in bestellung.positions:
        notes, ls_index = build_lieferscheine_for_position(rng, faker, bestellung, position, ls_index)
        lieferscheine.extend(notes)

    rechnung = build_rechnung(bestellung, lieferscheine)
    return OrderBundle(bestellung=bestellung, lieferscheine=lieferscheine, rechnung=rechnung)


# Independent re-derivation of each anomaly from the ground-truth bundle
# alone -- i.e. "is this discrepancy detectable", not "did the injector set
# the flag it was told to set".


def detect_qty_mismatch(bundle: OrderBundle) -> bool:
    for rechnung_position in bundle.rechnung.positions:
        delivered = sum(
            ls.quantity for ls in bundle.lieferscheine if ls.position_no == rechnung_position.position_no
        )
        if delivered == 0:
            continue
        if abs(rechnung_position.quantity - delivered) / delivered > QTY_TOLERANCE:
            return True
    return False


def detect_missing_signature(bundle: OrderBundle) -> bool:
    return any(not ls.signed for ls in bundle.lieferscheine)


def detect_wrong_order_ref(bundle: OrderBundle) -> bool:
    return any(ls.order_number_ref != bundle.bestellung.order_number for ls in bundle.lieferscheine)


def detect_duplicate_note(bundle: OrderBundle) -> bool:
    keys = [(ls.position_no, ls.quantity, ls.unit, ls.date, ls.material_id) for ls in bundle.lieferscheine]
    return any(count > 1 for count in Counter(keys).values())


def detect_unit_mismatch(bundle: OrderBundle) -> bool:
    order_unit_by_position = {p.position_no: p.unit for p in bundle.bestellung.positions}
    return any(ls.unit != order_unit_by_position[ls.position_no] for ls in bundle.lieferscheine)


def detect_price_deviation(bundle: OrderBundle) -> bool:
    order_price_by_position = {p.position_no: p.unit_price for p in bundle.bestellung.positions}
    for rechnung_position in bundle.rechnung.positions:
        order_price = order_price_by_position[rechnung_position.position_no]
        if abs(rechnung_position.unit_price - order_price) / order_price > PRICE_TOLERANCE:
            return True
    return False


DETECTORS = {
    DiscrepancyType.QTY_MISMATCH: detect_qty_mismatch,
    DiscrepancyType.MISSING_SIGNATURE: detect_missing_signature,
    DiscrepancyType.WRONG_ORDER_REF: detect_wrong_order_ref,
    DiscrepancyType.DUPLICATE_NOTE: detect_duplicate_note,
    DiscrepancyType.UNIT_MISMATCH: detect_unit_mismatch,
    DiscrepancyType.PRICE_DEVIATION: detect_price_deviation,
}


def test_discrepancy_rate_is_twenty_percent():
    assert DISCREPANCY_RATE == 0.2


def test_clean_bundle_has_no_detectable_discrepancy():
    for seed in range(30):
        bundle = _clean_bundle(seed)
        for detector in DETECTORS.values():
            assert not detector(bundle)


def test_qty_mismatch_is_detectable():
    for seed in range(10):
        bundle = _clean_bundle(seed)
        rng = random.Random(seed + 1000)
        discrepancy = _inject_qty_mismatch(rng, bundle)
        assert discrepancy.type == DiscrepancyType.QTY_MISMATCH
        assert detect_qty_mismatch(bundle)


def test_missing_signature_is_detectable():
    for seed in range(10):
        bundle = _clean_bundle(seed)
        rng = random.Random(seed + 1000)
        discrepancy = _inject_missing_signature(rng, bundle)
        assert discrepancy.type == DiscrepancyType.MISSING_SIGNATURE
        assert detect_missing_signature(bundle)


def test_wrong_order_ref_is_detectable():
    for seed in range(10):
        bundle = _clean_bundle(seed)
        rng = random.Random(seed + 1000)
        discrepancy = _inject_wrong_order_ref(rng, bundle)
        assert discrepancy.type == DiscrepancyType.WRONG_ORDER_REF
        assert detect_wrong_order_ref(bundle)


def test_duplicate_note_is_detectable():
    for seed in range(10):
        bundle = _clean_bundle(seed)
        rng = random.Random(seed + 1000)
        discrepancy = _inject_duplicate_note(rng, bundle)
        assert discrepancy.type == DiscrepancyType.DUPLICATE_NOTE
        assert detect_duplicate_note(bundle)


def test_unit_mismatch_is_detectable():
    for seed in range(10):
        bundle = _clean_bundle(seed)
        rng = random.Random(seed + 1000)
        discrepancy = _inject_unit_mismatch(rng, bundle)
        assert discrepancy.type == DiscrepancyType.UNIT_MISMATCH
        assert detect_unit_mismatch(bundle)


def test_price_deviation_is_detectable():
    for seed in range(10):
        bundle = _clean_bundle(seed)
        rng = random.Random(seed + 1000)
        discrepancy = _inject_price_deviation(rng, bundle)
        assert discrepancy.type == DiscrepancyType.PRICE_DEVIATION
        assert detect_price_deviation(bundle)


def test_qty_mismatch_minimum_deviation_clears_natural_weighing_tolerance():
    assert QTY_MISMATCH_MIN_DEVIATION >= 0.08
    assert QTY_MISMATCH_MIN_DEVIATION > BULK_DEVIATION * 2  # clearly separable from +/-3% noise

    for seed in range(100):
        bundle = _clean_bundle(seed)
        rng = random.Random(seed + 2000)
        before = {p.position_no: p.quantity for p in bundle.rechnung.positions}
        discrepancy = _inject_qty_mismatch(rng, bundle)
        position_no = int(discrepancy.field.split("position_no=")[1].split("]")[0])
        after = next(p.quantity for p in bundle.rechnung.positions if p.position_no == position_no)
        relative_deviation = abs(after - before[position_no]) / before[position_no]
        assert relative_deviation >= QTY_MISMATCH_MIN_DEVIATION - ROUNDING_SLACK


def test_price_deviation_minimum_deviation_clears_normal_price_range():
    assert PRICE_DEVIATION_MIN_DEVIATION >= 0.08

    for seed in range(100):
        bundle = _clean_bundle(seed)
        rng = random.Random(seed + 3000)
        before = {p.position_no: p.unit_price for p in bundle.bestellung.positions}
        discrepancy = _inject_price_deviation(rng, bundle)
        position_no = int(discrepancy.field.split("position_no=")[1].split("]")[0])
        after = next(p.unit_price for p in bundle.rechnung.positions if p.position_no == position_no)
        relative_deviation = abs(after - before[position_no]) / before[position_no]
        assert relative_deviation >= PRICE_DEVIATION_MIN_DEVIATION - ROUNDING_SLACK
