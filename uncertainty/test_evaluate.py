import numpy as np

from .dataset import Row
from .evaluate import (
    doc_level_auto_approval,
    expected_calibration_error,
    find_threshold_for_precision,
    per_field_confidence_summary,
    precision_at_threshold,
)


def _row(doc_id: str) -> Row:
    return Row(
        bestellung_id="BST-0001", doc_id=doc_id, pipeline="A", field="quantity",
        is_correct=True, ocr_confidence=None, token_logprob=None,
        pipeline_agreement=True, bestellung_deviation=None, self_consistency_rate=None,
    )


def test_ece_is_near_zero_for_perfectly_calibrated_predictions() -> None:
    rng = np.random.default_rng(0)
    confidences = rng.uniform(0, 1, 2000)
    correct = (rng.uniform(0, 1, 2000) < confidences).astype(float)

    ece = expected_calibration_error(confidences, correct, n_bins=10)

    assert ece < 0.05


def test_ece_is_large_for_badly_calibrated_predictions() -> None:
    confidences = np.full(200, 0.95)
    correct = np.array([1.0] * 50 + [0.0] * 150)  # only 25% actually correct

    ece = expected_calibration_error(confidences, correct, n_bins=10)

    assert ece > 0.5


def test_precision_at_threshold_only_considers_fields_above_it() -> None:
    confidences = np.array([0.9, 0.9, 0.4, 0.4])
    correct = np.array([1.0, 0.0, 1.0, 1.0])

    precision, rate = precision_at_threshold(confidences, correct, threshold=0.8)

    assert precision == 0.5  # 1 of 2 fields >= 0.8 is correct
    assert rate == 0.5


def test_find_threshold_for_precision_picks_the_lowest_threshold_that_qualifies() -> None:
    confidences = np.array([0.5, 0.6, 0.7, 0.95, 0.99])
    correct = np.array([0.0, 1.0, 1.0, 1.0, 1.0])  # everything from 0.6 up is correct

    threshold = find_threshold_for_precision(confidences, correct, target_precision=1.0)

    assert threshold == 0.6


def test_find_threshold_for_precision_returns_none_when_unreachable() -> None:
    confidences = np.array([0.9, 0.9])
    correct = np.array([1.0, 0.0])

    threshold = find_threshold_for_precision(confidences, correct, target_precision=0.99)

    assert threshold is None


def test_doc_level_auto_approval_requires_every_field_above_threshold() -> None:
    rows = [_row("LS-1"), _row("LS-1"), _row("LS-2"), _row("LS-2")]
    confidences = np.array([0.95, 0.95, 0.95, 0.5])  # LS-2's second field is low

    result = doc_level_auto_approval(rows, confidences, threshold=0.9)

    assert result.n_docs == 2
    assert result.n_auto_approved == 1
    assert result.auto_approval_rate == 0.5


def test_per_field_confidence_summary_groups_by_field() -> None:
    date_row = _row("LS-1").__class__(**{**_row("LS-1").__dict__, "field": "date"})
    rows = [_row("LS-1"), _row("LS-2"), date_row]
    confidences = np.array([0.9, 0.7, 0.2])

    summary = per_field_confidence_summary(rows, confidences)

    assert summary["quantity"] == {"n": 2, "min": 0.7, "max": 0.9, "mean": 0.8}
    assert summary["date"] == {"n": 1, "min": 0.2, "max": 0.2, "mean": 0.2}
