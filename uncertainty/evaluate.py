"""Evaluates calibrated confidence on the test split: ECE, a reliability diagram,
precision-vs-auto-approval-rate, the threshold for a target field precision, and the
doc-level headline metric.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .dataset import Row


def expected_calibration_error(confidences: np.ndarray, correct: np.ndarray, n_bins: int = 10) -> float:
    bin_edges = np.linspace(0, 1, n_bins + 1)
    n = len(confidences)
    if n == 0:
        return 0.0
    ece = 0.0
    for lo, hi in zip(bin_edges[:-1], bin_edges[1:]):
        mask = (confidences >= lo) & (confidences < hi if hi < 1 else confidences <= hi)
        if mask.sum() == 0:
            continue
        ece += (mask.sum() / n) * abs(confidences[mask].mean() - correct[mask].mean())
    return ece


def reliability_diagram(confidences: np.ndarray, correct: np.ndarray, out_path: Path, n_bins: int = 10) -> None:
    bin_edges = np.linspace(0, 1, n_bins + 1)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    accuracies = []
    for lo, hi in zip(bin_edges[:-1], bin_edges[1:]):
        mask = (confidences >= lo) & (confidences < hi if hi < 1 else confidences <= hi)
        accuracies.append(correct[mask].mean() if mask.sum() else np.nan)

    fig, ax = plt.subplots(figsize=(5, 5))
    ax.plot([0, 1], [0, 1], linestyle="--", color="gray", label="perfect calibration")
    ax.bar(bin_centers, accuracies, width=(1 / n_bins) * 0.9, color="#3C7A5E", edgecolor="black", label="observed accuracy")
    ax.set_xlabel("Predicted confidence")
    ax.set_ylabel("Observed accuracy")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_title("Reliability diagram (test split)")
    ax.legend()
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def precision_at_threshold(confidences: np.ndarray, correct: np.ndarray, threshold: float) -> tuple[float, float]:
    """Returns (field precision, field auto-approval rate) among fields at or above threshold."""
    mask = confidences >= threshold
    if mask.sum() == 0:
        return 1.0, 0.0
    return float(correct[mask].mean()), float(mask.mean())


def find_threshold_for_precision(confidences: np.ndarray, correct: np.ndarray, target_precision: float) -> float | None:
    """The lowest threshold (so the highest auto-approval rate) that hits target_precision
    while still selecting at least one field -- a threshold nothing clears vacuously "reaches"
    any precision target, which isn't a useful answer. None if no threshold reaches it.
    """
    candidates = sorted(set(confidences.tolist()))
    best = None
    for t in candidates:
        precision, rate = precision_at_threshold(confidences, correct, t)
        if rate > 0 and precision >= target_precision and (best is None or t < best):
            best = t
    return best


def per_field_confidence_summary(rows: list[Row], confidences: np.ndarray) -> dict[str, dict[str, float]]:
    """Min/max/mean calibrated confidence per field -- diagnostic for *why* a doc-level
    threshold does or doesn't clear, not something the model is selected on.
    """
    by_field: dict[str, list[float]] = {}
    for row, conf in zip(rows, confidences):
        by_field.setdefault(row.field, []).append(float(conf))
    return {
        field: {"n": len(values), "min": min(values), "max": max(values), "mean": sum(values) / len(values)}
        for field, values in sorted(by_field.items())
    }


@dataclass(frozen=True)
class DocLevelResult:
    n_docs: int
    n_auto_approved: int

    @property
    def auto_approval_rate(self) -> float:
        return self.n_auto_approved / self.n_docs if self.n_docs else 0.0


def doc_level_auto_approval(rows: list[Row], confidences: np.ndarray, threshold: float) -> DocLevelResult:
    """A Lieferschein auto-approves only if every one of its own fields clears the threshold."""
    by_doc: dict[str, list[float]] = {}
    for row, conf in zip(rows, confidences):
        by_doc.setdefault(row.doc_id, []).append(float(conf))
    n_approved = sum(1 for confs in by_doc.values() if min(confs) >= threshold)
    return DocLevelResult(n_docs=len(by_doc), n_auto_approved=n_approved)
