"""Builds the (doc, pipeline, field) row-level table used for calibration: the correctness
label (from step 3's comparison logic) plus raw per-field signals.

Lieferschein only -- see package docstring.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from eval.metrics import compare_lieferschein
from eval.normalize import normalize
from extraction.ground_truth import load_lieferschein_truth, load_material_names
from extraction.models import ExtractionResult, LieferscheinExtraction
from extraction.training_set import select_training_set

from .self_consistency import sample_lieferschein

CROSS_CHECK_FIELDS = {"quantity", "unit"}


@dataclass(frozen=True)
class Row:
    bestellung_id: str
    doc_id: str
    pipeline: str
    field: str
    is_correct: bool
    ocr_confidence: float | None
    token_logprob: float | None
    pipeline_agreement: bool
    bestellung_deviation: float | None
    self_consistency_rate: float | None


def _load_result(extracted_dir: Path, doc_id: str, pipeline: str) -> ExtractionResult[LieferscheinExtraction] | None:
    path = Path(extracted_dir) / f"{doc_id}_{pipeline}.json"
    if not path.exists():
        return None
    return ExtractionResult[LieferscheinExtraction].model_validate_json(path.read_text())


def _bestellung_position(data_dir: Path, bestellung_id: str, position_no: int) -> dict | None:
    order = json.loads((Path(data_dir) / "docs" / "orders" / f"{bestellung_id}.json").read_text())
    return next((p for p in order["positions"] if p["position_no"] == position_no), None)


def _cross_check(field: str, extracted_value, position: dict | None) -> float | None:
    if position is None or field not in CROSS_CHECK_FIELDS:
        return None
    if field == "quantity":
        true_qty = position["quantity"]
        return (extracted_value - true_qty) / true_qty if true_qty else 0.0
    return 0.0 if normalize("unit", extracted_value) == normalize("unit", position["unit"]) else 1.0


def build_rows(
    data_dir: Path,
    extracted_dir: Path,
    live_provider_a=None,
    self_consistency_dir: Path | None = None,
    n_self_consistency: int = 2,
) -> list[Row]:
    """live_provider_a + self_consistency_dir: pass to compute the self-consistency signal with
    live Azure calls (cached under self_consistency_dir). Omit both to skip that signal (e.g.
    offline tests, or data/extracted_training built without it).
    """
    ls_files, _ = select_training_set(data_dir)
    materials = load_material_names(data_dir)
    rows: list[Row] = []

    for path in ls_files:
        doc_id = path.stem
        truth_raw = json.loads((Path(data_dir) / "docs" / "delivery_notes" / f"{doc_id}.json").read_text())
        bestellung_id = truth_raw["bestellung_id"]
        true_fields = load_lieferschein_truth(doc_id, data_dir, materials)
        position = _bestellung_position(data_dir, bestellung_id, truth_raw["position_no"])

        result_a = _load_result(extracted_dir, doc_id, "A")
        result_b = _load_result(extracted_dir, doc_id, "B")
        if result_a is None or result_b is None:
            continue

        samples = None
        if live_provider_a is not None and self_consistency_dir is not None:
            samples = sample_lieferschein(live_provider_a, path, doc_id, n_self_consistency, self_consistency_dir)

        for pipeline, result, other in (("A", result_a, result_b), ("B", result_b, result_a)):
            comparisons = compare_lieferschein(pipeline, "na", result.fields, true_fields)
            for comparison in comparisons:
                field = comparison.field
                extracted_value = getattr(result.fields, field)
                other_value = getattr(other.fields, field)
                agreement = normalize(field, extracted_value) == normalize(field, other_value)

                signal = result.signals.get(field)

                consistency_rate = None
                if pipeline == "A" and samples:
                    matches = sum(
                        1 for s in samples if normalize(field, getattr(s.fields, field)) == normalize(field, extracted_value)
                    )
                    consistency_rate = matches / len(samples)

                rows.append(
                    Row(
                        bestellung_id=bestellung_id,
                        doc_id=doc_id,
                        pipeline=pipeline,
                        field=field,
                        is_correct=comparison.normalized_match,
                        ocr_confidence=signal.ocr_confidence if signal else None,
                        token_logprob=signal.token_logprob if signal else None,
                        pipeline_agreement=agreement,
                        bestellung_deviation=_cross_check(field, extracted_value, position),
                        self_consistency_rate=consistency_rate,
                    )
                )
    return rows
