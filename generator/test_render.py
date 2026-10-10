from pathlib import Path

import pdfplumber
import pytest

from .generate import generate_dataset
from .models import Dataset, DiscrepancyType
from .render import format_date, format_number, render_dataset

# Same leak check as test_writer.py: a rendered document must never spell out
# the name of the discrepancy mechanism, even though it legitimately carries
# the *altered* value (e.g. a wrong quantity) that makes it a discrepancy.
LEAK_MARKERS = [t.value for t in DiscrepancyType] + ["discrepancy", "discrepancies"]

# n_orders=15 at seed=42 already covers all 5 suppliers and plants >=1
# discrepancy; kept small because every test below renders real PDFs.
N_ORDERS = 15
SEED = 42


@pytest.fixture(scope="module")
def rendered(tmp_path_factory) -> tuple[Dataset, Path]:
    dataset = generate_dataset(n_orders=N_ORDERS, seed=SEED)
    out_dir = tmp_path_factory.mktemp("rendered")
    render_dataset(dataset, out_dir)
    return dataset, out_dir / "rendered" / "pdf"


def _pdf_text(path: Path) -> str:
    with pdfplumber.open(path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def test_render_creates_a_pdf_per_lieferschein_and_rechnung(rendered):
    dataset, pdf_dir = rendered
    assert pdf_dir.is_dir()

    expected_ls = {note.ls_number for bundle in dataset.orders for note in bundle.lieferscheine}
    expected_re = {bundle.rechnung.re_number for bundle in dataset.orders}

    actual_pdfs = {p.stem for p in pdf_dir.glob("*.pdf")}
    assert expected_ls <= actual_pdfs
    assert expected_re <= actual_pdfs


def test_all_five_supplier_layouts_render_lieferschein_key_values(rendered):
    dataset, pdf_dir = rendered

    materials_by_id = {m.id: m for m in dataset.master_data.materials}
    baustellen_by_id = {b.id: b for b in dataset.master_data.baustellen}

    suppliers_seen = set()
    for bundle in dataset.orders:
        suppliers_seen.add(bundle.bestellung.supplier_id)
        baustelle = baustellen_by_id[bundle.bestellung.baustelle_id]

        for note in bundle.lieferscheine:
            material = materials_by_id[note.material_id]
            text = _pdf_text(pdf_dir / f"{note.ls_number}.pdf")

            assert note.ls_number in text
            assert bundle.bestellung.order_number in text
            assert format_date(note.date) in text
            assert baustelle.name in text
            assert note.vehicle_plate in text
            assert note.driver_name in text
            assert material.name in text
            assert format_number(note.quantity) in text
            assert note.unit.value in text

    # Every one of the 5 suppliers (and thus every layout) was actually exercised.
    assert len(suppliers_seen) == 5


def test_all_five_supplier_layouts_render_rechnung_key_values(rendered):
    dataset, pdf_dir = rendered
    materials_by_id = {m.id: m for m in dataset.master_data.materials}

    for bundle in dataset.orders:
        rechnung = bundle.rechnung
        text = _pdf_text(pdf_dir / f"{rechnung.re_number}.pdf")

        assert rechnung.re_number in text
        assert bundle.bestellung.order_number in text
        assert format_date(rechnung.date) in text
        assert format_number(rechnung.total_amount) in text

        for position in rechnung.positions:
            material = materials_by_id[position.material_id]
            assert material.name in text
            assert format_number(position.quantity) in text
            assert format_number(position.unit_price) in text
            assert format_number(position.total) in text


def test_rendered_pdfs_never_leak_a_discrepancy_label(rendered):
    dataset, pdf_dir = rendered
    assert len(dataset.discrepancies) > 0  # make sure this run actually exercises injection

    for path in pdf_dir.glob("*.pdf"):
        text = _pdf_text(path).lower()
        for marker in LEAK_MARKERS:
            assert marker.lower() not in text, f"{path} leaks discrepancy marker {marker!r}"
