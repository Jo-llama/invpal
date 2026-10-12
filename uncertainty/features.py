"""Turns rows into a feature matrix: continuous signals are imputed to 0 when missing, paired
with a `has_*` indicator so the model can tell "signal present and ~0" apart from "signal
absent" (pipeline B never has ocr_confidence; token_logprob is never present for gpt-5-mini;
bestellung_deviation only applies to quantity/unit; self_consistency_rate is pipeline-A-only).
"""

from __future__ import annotations

import numpy as np

from .dataset import Row

FEATURE_NAMES = [
    "ocr_confidence",
    "has_ocr_confidence",
    "token_logprob",
    "has_token_logprob",
    "pipeline_agreement",
    "bestellung_deviation",
    "has_bestellung_check",
    "self_consistency_rate",
    "has_self_consistency",
]


def _row_features(row: Row) -> list[float]:
    return [
        row.ocr_confidence if row.ocr_confidence is not None else 0.0,
        1.0 if row.ocr_confidence is not None else 0.0,
        row.token_logprob if row.token_logprob is not None else 0.0,
        1.0 if row.token_logprob is not None else 0.0,
        1.0 if row.pipeline_agreement else 0.0,
        row.bestellung_deviation if row.bestellung_deviation is not None else 0.0,
        1.0 if row.bestellung_deviation is not None else 0.0,
        row.self_consistency_rate if row.self_consistency_rate is not None else 0.0,
        1.0 if row.self_consistency_rate is not None else 0.0,
    ]


def rows_to_matrix(rows: list[Row]) -> tuple[np.ndarray, np.ndarray]:
    x = np.array([_row_features(r) for r in rows], dtype=float)
    y = np.array([1.0 if r.is_correct else 0.0 for r in rows], dtype=float)
    return x, y
