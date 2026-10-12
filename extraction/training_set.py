"""Picks one Lieferschein + one Rechnung per Bestellung across the whole dataset.

Distinct from `golden_set.py`'s fixed 20 docs (step 3's eval set, kept stable for
comparability): step 4's calibration needs many more distinct Bestellung groups to split
train/calib/test without leakage, so this draws on all 50 Bestellungen instead.
"""

from __future__ import annotations

import json
from pathlib import Path


def select_training_set(data_dir: Path) -> tuple[list[Path], list[Path]]:
    """Returns (lieferschein_paths, rechnung_paths): the first Lieferschein (by filename
    sort) for every Bestellung that has one, plus that Bestellung's Rechnung.
    """
    data_dir = Path(data_dir)
    orders_dir = data_dir / "docs" / "orders"
    delivery_notes_dir = data_dir / "docs" / "delivery_notes"
    ls_dir = data_dir / "rendered" / "img"
    re_dir = data_dir / "rendered" / "pdf"

    order_numbers = sorted(p.stem for p in orders_dir.glob("BST-*.json"))

    ls_by_bestellung: dict[str, Path] = {}
    for path in sorted(ls_dir.glob("LS-*.png")):
        truth = json.loads((delivery_notes_dir / f"{path.stem}.json").read_text())
        ls_by_bestellung.setdefault(truth["bestellung_id"], path)

    ls_paths = [ls_by_bestellung[order] for order in order_numbers if order in ls_by_bestellung]
    re_paths = [re_dir / f"RE-2024-{order.split('-')[-1]}.pdf" for order in order_numbers]
    re_paths = [path for path in re_paths if path.exists()]
    return ls_paths, re_paths
