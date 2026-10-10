from pathlib import Path

import pytest

from .generate import generate_dataset
from .models import Dataset
from .render import render_dataset
from .scan import QUALITY_LEVELS, QUALITY_WEIGHTS, render_scans

N_ORDERS = 15
SEED = 42
DISTRIBUTION_TOLERANCE = 0.12  # percentage points, as a fraction


@pytest.fixture(scope="module")
def scanned(tmp_path_factory) -> tuple[Dataset, Path]:
    dataset = generate_dataset(n_orders=N_ORDERS, seed=SEED)
    out_dir = tmp_path_factory.mktemp("scanned")
    render_dataset(dataset, out_dir)
    render_scans(dataset, out_dir, seed=SEED)
    return dataset, out_dir


def _all_ls_numbers(dataset: Dataset) -> list[str]:
    return [note.ls_number for bundle in dataset.orders for note in bundle.lieferscheine]


def test_scan_creates_a_png_per_lieferschein(scanned):
    dataset, out_dir = scanned
    img_dir = out_dir / "rendered" / "img"
    assert img_dir.is_dir()

    expected = {f"{ls}.png" for ls in _all_ls_numbers(dataset)}
    actual = {p.name for p in img_dir.glob("*.png")}
    assert expected <= actual


def test_scan_skips_rechnungen(scanned):
    dataset, out_dir = scanned
    img_dir = out_dir / "rendered" / "img"
    expected_re = {f"{bundle.rechnung.re_number}.png" for bundle in dataset.orders}
    actual = {p.name for p in img_dir.glob("*.png")}
    assert expected_re.isdisjoint(actual)


def test_quality_level_distribution_matches_target_weights(scanned):
    dataset, out_dir = scanned
    csv_path = out_dir / "labels" / "doc_quality.csv"
    assert csv_path.is_file()

    import csv

    with csv_path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    total = len(rows)
    assert total == len(_all_ls_numbers(dataset))

    counts = {level: 0 for level in QUALITY_LEVELS}
    for row in rows:
        assert row["quality_level"] in QUALITY_LEVELS
        counts[row["quality_level"]] += 1

    for level, target_weight in zip(QUALITY_LEVELS, QUALITY_WEIGHTS):
        actual_fraction = counts[level] / total
        assert abs(actual_fraction - target_weight) <= DISTRIBUTION_TOLERANCE, (
            f"{level}: expected ~{target_weight:.0%}, got {actual_fraction:.0%} ({counts[level]}/{total})"
        )


def test_quality_labels_stay_out_of_docs_and_rendered(scanned):
    _, out_dir = scanned
    markers = [*QUALITY_LEVELS, "quality"]

    for directory in (out_dir / "docs", out_dir / "rendered"):
        for path in directory.rglob("*"):
            if not path.is_file() or path.suffix in {".png", ".pdf"}:
                continue
            content = path.read_text(encoding="utf-8").lower()
            for marker in markers:
                assert marker not in content, f"{path} leaks quality marker {marker!r}"


def test_doc_quality_csv_lives_only_in_labels(scanned):
    _, out_dir = scanned
    assert not list((out_dir / "docs").rglob("doc_quality.csv"))
    assert not list((out_dir / "rendered").rglob("doc_quality.csv"))
    assert (out_dir / "labels" / "doc_quality.csv").is_file()
