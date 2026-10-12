from .dataset import Row
from .split import split_by_bestellung


def _rows_for(bestellung_ids: list[str]) -> list[Row]:
    rows = []
    for i, bestellung_id in enumerate(bestellung_ids):
        for field in ("quantity", "unit"):
            rows.append(
                Row(
                    bestellung_id=bestellung_id, doc_id=f"LS-{i}", pipeline="A", field=field,
                    is_correct=True, ocr_confidence=0.9, token_logprob=None,
                    pipeline_agreement=True, bestellung_deviation=None, self_consistency_rate=None,
                )
            )
    return rows


def test_split_never_puts_the_same_bestellung_in_two_splits() -> None:
    rows = _rows_for([f"BST-{i:04d}" for i in range(30)])

    split = split_by_bestellung(rows, seed=1)

    train_ids = {r.bestellung_id for r in split.train}
    calib_ids = {r.bestellung_id for r in split.calib}
    test_ids = {r.bestellung_id for r in split.test}

    assert train_ids.isdisjoint(calib_ids)
    assert train_ids.isdisjoint(test_ids)
    assert calib_ids.isdisjoint(test_ids)
    assert train_ids | calib_ids | test_ids == {r.bestellung_id for r in rows}


def test_split_is_deterministic_given_a_seed() -> None:
    rows = _rows_for([f"BST-{i:04d}" for i in range(20)])

    split_1 = split_by_bestellung(rows, seed=42)
    split_2 = split_by_bestellung(rows, seed=42)

    assert [r.doc_id for r in split_1.train] == [r.doc_id for r in split_2.train]
    assert [r.doc_id for r in split_1.test] == [r.doc_id for r in split_2.test]


def test_split_respects_approximate_fractions() -> None:
    rows = _rows_for([f"BST-{i:04d}" for i in range(100)])

    split = split_by_bestellung(rows, seed=3, train_frac=0.6, calib_frac=0.2)

    n_train = len({r.bestellung_id for r in split.train})
    n_calib = len({r.bestellung_id for r in split.calib})
    n_test = len({r.bestellung_id for r in split.test})

    assert n_train == 60
    assert n_calib == 20
    assert n_test == 20
