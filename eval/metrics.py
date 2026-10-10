"""Field-level comparison of one extraction result against ground truth, and aggregation into
accuracy per (pipeline, doc_type, quality_level, field).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from extraction.models import LieferscheinExtraction, RechnungExtraction, RechnungPositionExtraction

from .normalize import normalize


@dataclass(frozen=True)
class FieldComparison:
    pipeline: str
    doc_type: str
    quality_level: str
    field: str
    exact_match: bool
    normalized_match: bool


def _compare_scalar(field_name: str, predicted: Any, true: Any) -> tuple[bool, bool]:
    exact = predicted == true
    normalized = normalize(field_name, predicted) == normalize(field_name, true)
    return exact, normalized


def compare_lieferschein(
    pipeline: str, quality_level: str, predicted: LieferscheinExtraction, true: LieferscheinExtraction
) -> list[FieldComparison]:
    comparisons = []
    for field_name in LieferscheinExtraction.model_fields:
        exact, normalized = _compare_scalar(field_name, getattr(predicted, field_name), getattr(true, field_name))
        comparisons.append(FieldComparison(pipeline, "lieferschein", quality_level, field_name, exact, normalized))
    return comparisons


def compare_rechnung(
    pipeline: str, quality_level: str, predicted: RechnungExtraction, true: RechnungExtraction
) -> list[FieldComparison]:
    comparisons = []
    top_level_fields = [name for name in RechnungExtraction.model_fields if name != "positions"]
    for field_name in top_level_fields:
        exact, normalized = _compare_scalar(field_name, getattr(predicted, field_name), getattr(true, field_name))
        comparisons.append(FieldComparison(pipeline, "rechnung", quality_level, field_name, exact, normalized))

    true_by_position = {p.position_no: p for p in true.positions}
    predicted_by_position = {p.position_no: p for p in predicted.positions}
    position_field_names = [name for name in RechnungPositionExtraction.model_fields if name != "position_no"]

    for position_no in sorted(set(true_by_position) | set(predicted_by_position)):
        true_position = true_by_position.get(position_no)
        predicted_position = predicted_by_position.get(position_no)
        for field_name in position_field_names:
            qualified_name = f"positions.{field_name}"
            if true_position is None or predicted_position is None:
                comparisons.append(
                    FieldComparison(pipeline, "rechnung", quality_level, qualified_name, False, False)
                )
                continue
            exact, normalized = _compare_scalar(
                field_name, getattr(predicted_position, field_name), getattr(true_position, field_name)
            )
            comparisons.append(
                FieldComparison(pipeline, "rechnung", quality_level, qualified_name, exact, normalized)
            )
    return comparisons


@dataclass(frozen=True)
class AggregatedAccuracy:
    pipeline: str
    doc_type: str
    quality_level: str
    field: str
    n: int
    exact_accuracy: float
    normalized_accuracy: float


def aggregate(comparisons: list[FieldComparison]) -> list[AggregatedAccuracy]:
    buckets: dict[tuple[str, str, str, str], list[FieldComparison]] = defaultdict(list)
    for comparison in comparisons:
        key = (comparison.pipeline, comparison.doc_type, comparison.quality_level, comparison.field)
        buckets[key].append(comparison)

    aggregated = []
    for (pipeline, doc_type, quality_level, field), items in buckets.items():
        n = len(items)
        exact_accuracy = sum(item.exact_match for item in items) / n
        normalized_accuracy = sum(item.normalized_match for item in items) / n
        aggregated.append(
            AggregatedAccuracy(pipeline, doc_type, quality_level, field, n, exact_accuracy, normalized_accuracy)
        )

    aggregated.sort(key=lambda a: (a.doc_type, a.pipeline, a.quality_level, a.field))
    return aggregated
