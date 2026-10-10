from datetime import date

from .models import (
    ExtractionResult,
    FieldSignal,
    LieferscheinExtraction,
    RechnungExtraction,
    RechnungPositionExtraction,
)


def test_lieferschein_extraction_round_trip() -> None:
    fields = LieferscheinExtraction(
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
    result = ExtractionResult[LieferscheinExtraction](
        doc_id="LS-2024-0001",
        pipeline="A",
        fields=fields,
        signals={"quantity": FieldSignal(ocr_confidence=0.9, token_logprob=-0.1)},
        latency_ms=123.4,
    )

    restored = ExtractionResult[LieferscheinExtraction].model_validate_json(result.model_dump_json())

    assert restored.fields == fields
    assert restored.signals["quantity"].ocr_confidence == 0.9
    assert restored.pipeline == "A"


def test_rechnung_extraction_round_trip() -> None:
    fields = RechnungExtraction(
        re_number="RE-2024-0001",
        order_number="BST-2024-0001",
        date=date(2024, 5, 15),
        positions=[
            RechnungPositionExtraction(
                position_no=1,
                material_name="Kies 0/4",
                quantity=55.96,
                unit="m³",
                unit_price=113.51,
                total=6352.02,
            )
        ],
        total_amount=6352.02,
    )
    result = ExtractionResult[RechnungExtraction](doc_id="RE-2024-0001", pipeline="B", fields=fields, latency_ms=50.0)

    restored = ExtractionResult[RechnungExtraction].model_validate_json(result.model_dump_json())

    assert restored.fields == fields
    assert restored.signals == {}
