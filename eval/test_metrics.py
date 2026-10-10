from datetime import date

from extraction.models import LieferscheinExtraction, RechnungExtraction, RechnungPositionExtraction

from .metrics import aggregate, compare_lieferschein, compare_rechnung


def _lieferschein(**overrides) -> LieferscheinExtraction:
    base = dict(
        ls_number="LS-2024-0001",
        order_number="BST-2024-0001",
        position_no=1,
        date=date(2024, 5, 15),
        material_name="Kies 0/4",
        quantity=32.75,
        unit="m³",
        driver_name="Ivan Junk",
        vehicle_plate="ES-A-4559",
        signed=True,
    )
    base.update(overrides)
    return LieferscheinExtraction(**base)


def test_compare_lieferschein_exact_match_on_all_fields() -> None:
    true = _lieferschein()
    predicted = _lieferschein()

    comparisons = compare_lieferschein("A", "clean", predicted, true)

    assert len(comparisons) == len(LieferscheinExtraction.model_fields)
    assert all(c.exact_match and c.normalized_match for c in comparisons)


def test_compare_lieferschein_unit_formatting_mismatch_is_normalized_only() -> None:
    true = _lieferschein(unit="m³")
    predicted = _lieferschein(unit="m3")

    comparisons = compare_lieferschein("A", "clean", predicted, true)
    unit_comparison = next(c for c in comparisons if c.field == "unit")

    assert unit_comparison.exact_match is False
    assert unit_comparison.normalized_match is True


def test_compare_lieferschein_substantive_mismatch_fails_both() -> None:
    true = _lieferschein(material_name="Kies 0/4")
    predicted = _lieferschein(material_name="Sand 0/2")

    comparisons = compare_lieferschein("A", "clean", predicted, true)
    material_comparison = next(c for c in comparisons if c.field == "material_name")

    assert material_comparison.exact_match is False
    assert material_comparison.normalized_match is False


def _rechnung(positions: list[RechnungPositionExtraction]) -> RechnungExtraction:
    return RechnungExtraction(
        re_number="RE-2024-0001",
        order_number="BST-2024-0001",
        date=date(2024, 5, 15),
        positions=positions,
        total_amount=6352.02,
    )


def test_compare_rechnung_matches_positions_by_position_no() -> None:
    true = _rechnung(
        [RechnungPositionExtraction(position_no=1, material_name="Kies 0/4", quantity=55.96, unit="m³", unit_price=113.51, total=6352.02)]
    )
    predicted = _rechnung(
        [RechnungPositionExtraction(position_no=1, material_name="Kies 0/4", quantity=55.96, unit="m3", unit_price=113.51, total=6352.02)]
    )

    comparisons = compare_rechnung("B", "digital", predicted, true)
    unit_comparison = next(c for c in comparisons if c.field == "positions.unit")

    assert unit_comparison.exact_match is False
    assert unit_comparison.normalized_match is True


def test_compare_rechnung_missing_position_counts_as_mismatch() -> None:
    true = _rechnung(
        [RechnungPositionExtraction(position_no=1, material_name="Kies 0/4", quantity=55.96, unit="m³", unit_price=113.51, total=6352.02)]
    )
    predicted = _rechnung([])

    comparisons = compare_rechnung("A", "digital", predicted, true)

    assert len(comparisons) > 0
    assert all(not c.exact_match and not c.normalized_match for c in comparisons if c.field.startswith("positions."))


def test_aggregate_computes_accuracy_per_bucket() -> None:
    true = _lieferschein()
    predicted_a_good = _lieferschein()
    predicted_a_bad = _lieferschein(quantity=1.0)

    comparisons = compare_lieferschein("A", "clean", predicted_a_good, true) + compare_lieferschein(
        "A", "clean", predicted_a_bad, true
    )

    aggregated = aggregate(comparisons)
    quantity_bucket = next(a for a in aggregated if a.field == "quantity")

    assert quantity_bucket.n == 2
    assert quantity_bucket.exact_accuracy == 0.5
    assert quantity_bucket.normalized_accuracy == 0.5
