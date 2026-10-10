"""Loads the generator's own ground truth as extraction-schema objects.

Shared by MockProvider (tests) and the eval harness (step 3): both need exactly the same
mapping from the generator's internal records (master-data IDs) to the fields a real extraction
pipeline would read off the printed document (material name, not material_id).
"""

from __future__ import annotations

import json
from pathlib import Path

from .models import LieferscheinExtraction, RechnungExtraction, RechnungPositionExtraction


def load_material_names(data_dir: Path) -> dict[str, str]:
    master_data = json.loads((Path(data_dir) / "master_data.json").read_text())
    return {m["id"]: m["name"] for m in master_data["materials"]}


def load_lieferschein_truth(doc_id: str, data_dir: Path, materials: dict[str, str] | None = None) -> LieferscheinExtraction:
    data_dir = Path(data_dir)
    materials = materials if materials is not None else load_material_names(data_dir)
    truth = json.loads((data_dir / "docs" / "delivery_notes" / f"{doc_id}.json").read_text())
    return LieferscheinExtraction(
        ls_number=truth["ls_number"],
        order_number=truth["order_number_ref"],
        position_no=truth["position_no"],
        date=truth["date"],
        material_name=materials[truth["material_id"]],
        quantity=truth["quantity"],
        unit=truth["unit"],
        driver_name=truth["driver_name"],
        vehicle_plate=truth["vehicle_plate"],
        signed=truth["signed"],
    )


def load_rechnung_truth(doc_id: str, data_dir: Path, materials: dict[str, str] | None = None) -> RechnungExtraction:
    data_dir = Path(data_dir)
    materials = materials if materials is not None else load_material_names(data_dir)
    truth = json.loads((data_dir / "docs" / "invoices" / f"{doc_id}.json").read_text())
    positions = [
        RechnungPositionExtraction(
            position_no=p["position_no"],
            material_name=materials[p["material_id"]],
            quantity=p["quantity"],
            unit=p["unit"],
            unit_price=p["unit_price"],
            total=p["total"],
        )
        for p in truth["positions"]
    ]
    return RechnungExtraction(
        re_number=truth["re_number"],
        order_number=truth["order_number_ref"],
        date=truth["date"],
        positions=positions,
        total_amount=truth["total_amount"],
    )
