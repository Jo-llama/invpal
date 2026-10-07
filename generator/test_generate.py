from .generate import generate_dataset
from .test_discrepancies import DETECTORS


def test_same_seed_gives_identical_dataset():
    dataset_a = generate_dataset(n_orders=30, seed=42)
    dataset_b = generate_dataset(n_orders=30, seed=42)
    assert dataset_a.model_dump() == dataset_b.model_dump()


def test_different_seed_gives_different_dataset():
    dataset_a = generate_dataset(n_orders=30, seed=42)
    dataset_b = generate_dataset(n_orders=30, seed=43)
    assert dataset_a.model_dump() != dataset_b.model_dump()


def test_discrepancy_rate_is_roughly_twenty_percent():
    dataset = generate_dataset(n_orders=500, seed=42)
    rate = len(dataset.discrepancies) / len(dataset.orders)
    assert 0.1 <= rate <= 0.3


def test_every_planted_discrepancy_is_detectable_from_ground_truth():
    dataset = generate_dataset(n_orders=200, seed=42)
    bundle_by_order_id = {bundle.bestellung.id: bundle for bundle in dataset.orders}

    assert len(dataset.discrepancies) > 0
    for discrepancy in dataset.discrepancies:
        bundle = bundle_by_order_id[discrepancy.bestellung_id]
        detector = DETECTORS[discrepancy.type]
        assert detector(bundle), f"{discrepancy.type} on {discrepancy.bestellung_id} not detectable"


def test_each_order_has_at_most_one_planted_discrepancy():
    dataset = generate_dataset(n_orders=200, seed=42)
    order_ids = [d.bestellung_id for d in dataset.discrepancies]
    assert len(order_ids) == len(set(order_ids))
