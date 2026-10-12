"""Splits rows by distinct Bestellung id so no order leaks across train/calib/test --
several fields of the same Lieferschein (and a doc's own near-duplicate rows) would otherwise
let the model see a near-copy of a test example during training.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from .dataset import Row


@dataclass(frozen=True)
class Split:
    train: list[Row]
    calib: list[Row]
    test: list[Row]


def split_by_bestellung(rows: list[Row], seed: int, train_frac: float = 0.6, calib_frac: float = 0.2) -> Split:
    bestellung_ids = sorted({row.bestellung_id for row in rows})
    rng = random.Random(seed)
    rng.shuffle(bestellung_ids)

    n = len(bestellung_ids)
    n_train = round(n * train_frac)
    n_calib = round(n * calib_frac)

    train_ids = set(bestellung_ids[:n_train])
    calib_ids = set(bestellung_ids[n_train : n_train + n_calib])
    test_ids = set(bestellung_ids[n_train + n_calib :])

    return Split(
        train=[r for r in rows if r.bestellung_id in train_ids],
        calib=[r for r in rows if r.bestellung_id in calib_ids],
        test=[r for r in rows if r.bestellung_id in test_ids],
    )
