from .dataset import Row
from .features import FEATURE_NAMES, rows_to_matrix


def _row(**overrides) -> Row:
    base = dict(
        bestellung_id="BST-0001", doc_id="LS-0001", pipeline="A", field="quantity",
        is_correct=True, ocr_confidence=None, token_logprob=None,
        pipeline_agreement=True, bestellung_deviation=None, self_consistency_rate=None,
    )
    base.update(overrides)
    return Row(**base)


def test_missing_signals_are_imputed_with_a_zero_indicator() -> None:
    x, y = rows_to_matrix([_row()])

    assert x.shape == (1, len(FEATURE_NAMES))
    idx = {name: i for i, name in enumerate(FEATURE_NAMES)}
    assert x[0, idx["ocr_confidence"]] == 0.0
    assert x[0, idx["has_ocr_confidence"]] == 0.0
    assert x[0, idx["bestellung_deviation"]] == 0.0
    assert x[0, idx["has_bestellung_check"]] == 0.0
    assert y[0] == 1.0


def test_present_signals_are_passed_through_with_a_one_indicator() -> None:
    x, _ = rows_to_matrix([_row(ocr_confidence=0.75, bestellung_deviation=0.02)])

    idx = {name: i for i, name in enumerate(FEATURE_NAMES)}
    assert x[0, idx["ocr_confidence"]] == 0.75
    assert x[0, idx["has_ocr_confidence"]] == 1.0
    assert x[0, idx["bestellung_deviation"]] == 0.02
    assert x[0, idx["has_bestellung_check"]] == 1.0


def test_label_reflects_is_correct() -> None:
    _, y = rows_to_matrix([_row(is_correct=True), _row(is_correct=False)])
    assert list(y) == [1.0, 0.0]
