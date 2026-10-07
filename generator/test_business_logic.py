import random

from faker import Faker

from .business_logic import build_bestellung, build_lieferscheine_for_position, build_rechnung
from .master_data import build_master_data
from .models import Unit

BULK_TOLERANCE = 0.035  # 3% deviation + a little headroom for 2-decimal rounding


def _build_clean_bundle(seed: int, order_index: int = 1):
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
    return bestellung, lieferscheine, rechnung


def test_order_has_one_to_three_positions():
    for seed in range(20):
        bestellung, _, _ = _build_clean_bundle(seed)
        assert 1 <= len(bestellung.positions) <= 3


def test_each_position_split_into_one_to_four_notes():
    for seed in range(20):
        bestellung, lieferscheine, _ = _build_clean_bundle(seed)
        for position in bestellung.positions:
            notes = [ls for ls in lieferscheine if ls.position_no == position.position_no]
            assert 1 <= len(notes) <= 4


def test_delivered_sum_within_tolerance_of_ordered_quantity():
    for seed in range(50):
        bestellung, lieferscheine, _ = _build_clean_bundle(seed)
        for position in bestellung.positions:
            delivered = sum(ls.quantity for ls in lieferscheine if ls.position_no == position.position_no)
            if position.unit == Unit.PIECE:
                assert delivered == position.quantity
            else:
                relative_error = abs(delivered - position.quantity) / position.quantity
                assert relative_error <= BULK_TOLERANCE, (seed, position, delivered)


def test_rechnung_quantity_equals_delivered_sum():
    for seed in range(20):
        bestellung, lieferscheine, rechnung = _build_clean_bundle(seed)
        for rechnung_position in rechnung.positions:
            delivered = round(
                sum(ls.quantity for ls in lieferscheine if ls.position_no == rechnung_position.position_no), 2
            )
            assert rechnung_position.quantity == delivered


def test_rechnung_totals_are_consistent():
    for seed in range(20):
        _, _, rechnung = _build_clean_bundle(seed)
        for position in rechnung.positions:
            assert position.total == round(position.quantity * position.unit_price, 2)
        assert rechnung.total_amount == round(sum(p.total for p in rechnung.positions), 2)
