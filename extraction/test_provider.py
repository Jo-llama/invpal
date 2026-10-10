from pathlib import Path

import pytest

from generator.generate import generate_dataset
from generator.models import Dataset
from generator.writer import write_dataset

from .provider import MockProvider


@pytest.fixture(scope="module")
def dataset_dir(tmp_path_factory) -> tuple[Dataset, Path]:
    dataset = generate_dataset(n_orders=5, seed=1)
    out_dir = tmp_path_factory.mktemp("extraction_data")
    write_dataset(dataset, out_dir)
    return dataset, out_dir


def test_mock_provider_extracts_lieferschein(dataset_dir: tuple[Dataset, Path]) -> None:
    dataset, out_dir = dataset_dir
    note = dataset.orders[0].lieferscheine[0]
    material_name = next(m.name for m in dataset.master_data.materials if m.id == note.material_id)

    provider = MockProvider(data_dir=out_dir)
    result = provider.extract_lieferschein(Path("unused.png"), note.ls_number)

    assert result.doc_id == note.ls_number
    assert result.pipeline == "A"
    assert result.fields.ls_number == note.ls_number
    assert result.fields.order_number == note.order_number_ref
    assert result.fields.material_name == material_name
    assert result.fields.quantity == note.quantity
    assert result.fields.signed == note.signed
    assert result.signals["quantity"].ocr_confidence is not None


def test_mock_provider_extracts_rechnung(dataset_dir: tuple[Dataset, Path]) -> None:
    dataset, out_dir = dataset_dir
    rechnung = dataset.orders[0].rechnung

    provider = MockProvider(data_dir=out_dir)
    result = provider.extract_rechnung(Path("unused.pdf"), rechnung.re_number)

    assert result.doc_id == rechnung.re_number
    assert result.fields.re_number == rechnung.re_number
    assert result.fields.total_amount == rechnung.total_amount
    assert len(result.fields.positions) == len(rechnung.positions)
    assert result.fields.positions[0].position_no == rechnung.positions[0].position_no


def test_mock_provider_pipeline_label_is_configurable(dataset_dir: tuple[Dataset, Path]) -> None:
    dataset, out_dir = dataset_dir
    note = dataset.orders[0].lieferscheine[0]

    provider = MockProvider(data_dir=out_dir, pipeline="B")
    result = provider.extract_lieferschein(Path("unused.png"), note.ls_number)

    assert result.pipeline == "B"
