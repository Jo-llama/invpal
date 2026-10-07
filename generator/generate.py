"""Orchestrates master data + N order bundles into a full Dataset."""

from __future__ import annotations

import random

from faker import Faker

from .business_logic import build_bestellung, build_lieferscheine_for_position, build_rechnung
from .discrepancies import maybe_inject_discrepancy
from .master_data import build_master_data
from .models import Dataset, OrderBundle


def generate_dataset(n_orders: int, seed: int) -> Dataset:
    rng = random.Random(seed)
    faker = Faker("de_DE")
    faker.seed_instance(seed)

    master = build_master_data(rng, faker)

    orders: list[OrderBundle] = []
    discrepancies = []
    ls_index = 0

    for order_index in range(1, n_orders + 1):
        bestellung = build_bestellung(rng, order_index, master)

        lieferscheine = []
        for position in bestellung.positions:
            notes, ls_index = build_lieferscheine_for_position(rng, faker, bestellung, position, ls_index)
            lieferscheine.extend(notes)

        rechnung = build_rechnung(bestellung, lieferscheine)
        bundle = OrderBundle(bestellung=bestellung, lieferscheine=lieferscheine, rechnung=rechnung)

        discrepancy = maybe_inject_discrepancy(rng, bundle)
        if discrepancy is not None:
            discrepancies.append(discrepancy)

        orders.append(bundle)

    return Dataset(master_data=master, orders=orders, discrepancies=discrepancies)
