import random

from faker import Faker

from .master_data import N_BAUSTELLEN, N_COMPANIES, N_SUPPLIERS, build_master_data


def _build(seed: int):
    rng = random.Random(seed)
    faker = Faker("de_DE")
    faker.seed_instance(seed)
    return build_master_data(rng, faker)


def test_master_data_counts():
    master = _build(42)
    assert len(master.suppliers) == N_SUPPLIERS == 5
    assert len(master.companies) == N_COMPANIES == 8
    assert len(master.baustellen) == N_BAUSTELLEN == 15


def test_baustelle_company_fk_is_valid():
    master = _build(42)
    company_ids = {c.id for c in master.companies}
    for baustelle in master.baustellen:
        assert baustelle.company_id in company_ids


def test_same_seed_is_reproducible():
    master_a = _build(42)
    master_b = _build(42)
    assert master_a.model_dump() == master_b.model_dump()


def test_different_seed_differs():
    master_a = _build(42)
    master_b = _build(43)
    assert master_a.model_dump() != master_b.model_dump()
