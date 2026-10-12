import random

from .dataset import Row
from .model import fit


def _synthetic_rows(n: int, seed: int) -> list[Row]:
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        ocr_confidence = rng.uniform(0, 1)
        # ground truth is correlated with ocr_confidence but noisy, so calibration has real work to do
        is_correct = rng.random() < ocr_confidence
        rows.append(
            Row(
                bestellung_id=f"BST-{i % 20:04d}", doc_id=f"LS-{i:04d}", pipeline="A", field="quantity",
                is_correct=is_correct, ocr_confidence=ocr_confidence, token_logprob=None,
                pipeline_agreement=rng.random() < 0.9, bestellung_deviation=None, self_consistency_rate=None,
            )
        )
    return rows


def test_predict_returns_probabilities_in_unit_interval() -> None:
    train_rows = _synthetic_rows(200, seed=1)
    calib_rows = _synthetic_rows(100, seed=2)
    test_rows = _synthetic_rows(50, seed=3)

    model = fit(train_rows, calib_rows)
    predictions = model.predict(test_rows)

    assert predictions.min() >= 0.0
    assert predictions.max() <= 1.0
    assert len(predictions) == len(test_rows)


def test_higher_ocr_confidence_rows_get_higher_predicted_confidence() -> None:
    train_rows = _synthetic_rows(300, seed=10)
    calib_rows = _synthetic_rows(150, seed=11)
    model = fit(train_rows, calib_rows)

    low = Row(
        bestellung_id="BST-x", doc_id="LS-low", pipeline="A", field="quantity",
        is_correct=True, ocr_confidence=0.1, token_logprob=None,
        pipeline_agreement=True, bestellung_deviation=None, self_consistency_rate=None,
    )
    high = low.__class__(**{**low.__dict__, "ocr_confidence": 0.95})

    predictions = model.predict([low, high])

    assert predictions[1] > predictions[0]
