"""Renders aggregated eval metrics as a markdown table and a JSON-serializable report."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .metrics import AggregatedAccuracy


def render_markdown_table(aggregated: list[AggregatedAccuracy]) -> str:
    header = "| doc_type | pipeline | quality_level | field | n | exact_acc | normalized_acc |"
    separator = "|---|---|---|---|---|---|---|"
    rows = [
        f"| {a.doc_type} | {a.pipeline} | {a.quality_level} | {a.field} | {a.n} "
        f"| {a.exact_accuracy:.2f} | {a.normalized_accuracy:.2f} |"
        for a in aggregated
    ]
    return "\n".join([header, separator, *rows])


def build_report(run_id: str, n_docs: int, aggregated: list[AggregatedAccuracy]) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "n_docs": n_docs,
        "per_field": [asdict(a) for a in aggregated],
    }
