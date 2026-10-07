"""Serializes a Dataset to disk.

Layout:
    data/docs/orders/           -- what the extraction pipeline will read;
    data/docs/delivery_notes/      must never reveal a planted discrepancy
    data/docs/invoices/
    data/master_data.json
    data/labels/discrepancies.csv  -- ground truth, kept out of docs/
"""

from __future__ import annotations

import csv
from pathlib import Path

from .models import Dataset


def write_dataset(dataset: Dataset, out_dir: Path) -> None:
    out_dir = Path(out_dir)
    docs_dir = out_dir / "docs"
    orders_dir = docs_dir / "orders"
    delivery_notes_dir = docs_dir / "delivery_notes"
    invoices_dir = docs_dir / "invoices"
    labels_dir = out_dir / "labels"
    for directory in (out_dir, docs_dir, orders_dir, delivery_notes_dir, invoices_dir, labels_dir):
        directory.mkdir(parents=True, exist_ok=True)

    (out_dir / "master_data.json").write_text(dataset.master_data.model_dump_json(indent=2), encoding="utf-8")

    for bundle in dataset.orders:
        order_number = bundle.bestellung.order_number
        (orders_dir / f"{order_number}.json").write_text(
            bundle.bestellung.model_dump_json(indent=2), encoding="utf-8"
        )
        for note in bundle.lieferscheine:
            (delivery_notes_dir / f"{note.ls_number}.json").write_text(
                note.model_dump_json(indent=2), encoding="utf-8"
            )
        (invoices_dir / f"{bundle.rechnung.re_number}.json").write_text(
            bundle.rechnung.model_dump_json(indent=2), encoding="utf-8"
        )

    _write_discrepancies_csv(dataset, labels_dir / "discrepancies.csv")


def _write_discrepancies_csv(dataset: Dataset, path: Path) -> None:
    fieldnames = [
        "bestellung_id",
        "order_number",
        "type",
        "document_type",
        "document_id",
        "field",
        "expected_value",
        "actual_value",
        "description",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for discrepancy in dataset.discrepancies:
            writer.writerow(discrepancy.model_dump(mode="json"))
