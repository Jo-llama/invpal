import pytest

from extraction.models import ExtractionResult, FieldSignal, LieferscheinExtraction
from generator.generate import generate_dataset
from generator.writer import write_dataset

from .dataset import build_rows


def _write_result(extracted_dir, doc_id: str, pipeline: str, fields: LieferscheinExtraction, signals=None) -> None:
    result = ExtractionResult[LieferscheinExtraction](
        doc_id=doc_id, pipeline=pipeline, fields=fields, signals=signals or {}, latency_ms=100.0
    )
    (extracted_dir / f"{doc_id}_{pipeline}.json").write_text(result.model_dump_json())


def test_build_rows_joins_truth_signals_and_bestellung_cross_check(tmp_path) -> None:
    dataset = generate_dataset(n_orders=2, seed=7)
    data_dir = tmp_path / "data"
    write_dataset(dataset, data_dir)

    ls_dir = data_dir / "rendered" / "img"
    ls_dir.mkdir(parents=True, exist_ok=True)
    for bundle in dataset.orders:
        for note in bundle.lieferscheine:
            (ls_dir / f"{note.ls_number}.png").touch()

    bundle = dataset.orders[0]
    note = bundle.lieferscheine[0]
    material_name = next(m.name for m in dataset.master_data.materials if m.id == note.material_id)
    position = next(p for p in bundle.bestellung.positions if p.position_no == note.position_no)

    extracted_dir = tmp_path / "extracted"
    extracted_dir.mkdir()

    correct_fields = LieferscheinExtraction(
        ls_number=note.ls_number, order_number=note.order_number_ref, position_no=note.position_no,
        date=note.date, material_name=material_name, quantity=note.quantity, unit=note.unit.value,
        driver_name=note.driver_name, vehicle_plate=note.vehicle_plate, signed=note.signed,
    )
    wrong_quantity_fields = correct_fields.model_copy(update={"quantity": note.quantity + 9999})

    _write_result(extracted_dir, note.ls_number, "A", correct_fields, {"quantity": FieldSignal(ocr_confidence=0.9)})
    _write_result(extracted_dir, note.ls_number, "B", wrong_quantity_fields)

    rows = build_rows(data_dir, extracted_dir)

    assert len(rows) == 2 * len(LieferscheinExtraction.model_fields)

    quantity_a = next(r for r in rows if r.doc_id == note.ls_number and r.pipeline == "A" and r.field == "quantity")
    quantity_b = next(r for r in rows if r.doc_id == note.ls_number and r.pipeline == "B" and r.field == "quantity")

    assert quantity_a.is_correct is True
    assert quantity_a.ocr_confidence == 0.9
    assert quantity_a.pipeline_agreement is False
    assert quantity_a.bestellung_deviation == pytest.approx((note.quantity - position.quantity) / position.quantity)
    assert quantity_a.self_consistency_rate is None

    assert quantity_b.is_correct is False
    assert quantity_b.ocr_confidence is None
    assert quantity_b.pipeline_agreement is False
