from pathlib import Path

from .generate import generate_dataset
from .models import DiscrepancyType
from .writer import write_dataset

# Strings that would leak a planted discrepancy into a document the
# extraction pipeline reads. Checked case-insensitively.
LEAK_MARKERS = [t.value for t in DiscrepancyType] + ["discrepancy", "discrepancies"]


def test_writer_creates_expected_layout(tmp_path: Path):
    dataset = generate_dataset(n_orders=20, seed=42)
    write_dataset(dataset, tmp_path)

    assert (tmp_path / "master_data.json").is_file()
    assert (tmp_path / "labels" / "discrepancies.csv").is_file()
    assert (tmp_path / "docs" / "orders").is_dir()
    assert (tmp_path / "docs" / "delivery_notes").is_dir()
    assert (tmp_path / "docs" / "invoices").is_dir()

    assert list((tmp_path / "docs" / "orders").glob("*.json"))
    assert list((tmp_path / "docs" / "delivery_notes").glob("*.json"))
    assert list((tmp_path / "docs" / "invoices").glob("*.json"))


def test_docs_directory_never_leaks_a_discrepancy_label(tmp_path: Path):
    dataset = generate_dataset(n_orders=200, seed=42)
    assert len(dataset.discrepancies) > 0  # make sure this run actually exercises injection
    write_dataset(dataset, tmp_path)

    docs_dir = tmp_path / "docs"
    for path in docs_dir.rglob("*"):
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8").lower()
        for marker in LEAK_MARKERS:
            assert marker.lower() not in content, f"{path} leaks discrepancy marker {marker!r}"


def test_labels_file_is_outside_docs_directory(tmp_path: Path):
    dataset = generate_dataset(n_orders=20, seed=42)
    write_dataset(dataset, tmp_path)

    docs_files = {p.name for p in (tmp_path / "docs").rglob("*") if p.is_file()}
    assert "discrepancies.csv" not in docs_files
