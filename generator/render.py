"""Renders Lieferscheine and Rechnungen to PDF, using one of 5 supplier-specific
Jinja2 layouts per document type (field order, label wording, table vs free
layout all differ), via WeasyPrint.

Output: <out_dir>/rendered/pdf/<doc_id>.pdf
"""

from __future__ import annotations

import random
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML

from .business_logic import BULK_UNITS
from .models import Baustelle, Dataset, Lieferschein, MaterialItem, OrderBundle, Rechnung, Supplier

TEMPLATES_DIR = Path(__file__).parent / "templates"

LS_TEMPLATES = ["ls_layout_1.html", "ls_layout_2.html", "ls_layout_3.html", "ls_layout_4.html", "ls_layout_5.html"]
RE_TEMPLATES = ["re_layout_1.html", "re_layout_2.html", "re_layout_3.html", "re_layout_4.html", "re_layout_5.html"]

_env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(["html"]),
)


def format_number(value: float, decimals: int = 2) -> str:
    """German-style decimal formatting: 1234.5 -> "1.234,50"."""
    integer_part, _, decimal_part = f"{value:,.{decimals}f}".partition(".")
    return f"{integer_part.replace(',', '.')},{decimal_part}"


def format_date(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def _layout_index(supplier_id: str) -> int:
    n = int(supplier_id.rsplit("-", 1)[1])
    return (n - 1) % len(LS_TEMPLATES)


def _weighing_block(note: Lieferschein) -> dict[str, float] | None:
    if note.unit not in BULK_UNITS:
        return None
    rng = random.Random(f"wiegeschein-{note.ls_number}")
    netto = note.quantity
    tara = round(netto * rng.uniform(0.15, 0.25), 2)
    return {"brutto": round(netto + tara, 2), "tara": tara, "netto": netto}


def _signature_path(ls_number: str) -> str:
    rng = random.Random(f"signature-{ls_number}")
    x, y = rng.uniform(5, 15), rng.uniform(10, 30)
    points = [(x, y)]
    for _ in range(5):
        x += rng.uniform(15, 30)
        y = rng.uniform(5, 35)
        points.append((x, y))
    start = f"M {points[0][0]:.1f},{points[0][1]:.1f}"
    rest = " ".join(f"L {px:.1f},{py:.1f}" for px, py in points[1:])
    return f"{start} {rest}"


def _render_lieferschein(
    note: Lieferschein,
    bestellung: OrderBundle,
    supplier: Supplier,
    baustelle: Baustelle,
    material: MaterialItem,
    layout_index: int,
) -> str:
    template = _env.get_template(LS_TEMPLATES[layout_index])
    return template.render(
        note=note,
        bestellung=bestellung.bestellung,
        supplier=supplier,
        baustelle=baustelle,
        material=material,
        weighing=_weighing_block(note),
        signature_path=_signature_path(note.ls_number) if note.signed else None,
        format_number=format_number,
        format_date=format_date,
    )


def _render_rechnung(
    rechnung: Rechnung,
    bestellung: OrderBundle,
    supplier: Supplier,
    materials_by_id: dict[str, MaterialItem],
    layout_index: int,
) -> str:
    template = _env.get_template(RE_TEMPLATES[layout_index])
    positions = [
        {
            "position_no": p.position_no,
            "material_name": materials_by_id[p.material_id].name,
            "quantity": p.quantity,
            "unit": p.unit.value,
            "unit_price": p.unit_price,
            "total": p.total,
        }
        for p in rechnung.positions
    ]
    return template.render(
        rechnung=rechnung,
        bestellung=bestellung.bestellung,
        supplier=supplier,
        positions=positions,
        format_number=format_number,
        format_date=format_date,
    )


def render_dataset(dataset: Dataset, out_dir: Path) -> None:
    pdf_dir = Path(out_dir) / "rendered" / "pdf"
    pdf_dir.mkdir(parents=True, exist_ok=True)

    suppliers_by_id = {s.id: s for s in dataset.master_data.suppliers}
    baustellen_by_id = {b.id: b for b in dataset.master_data.baustellen}
    materials_by_id = {m.id: m for m in dataset.master_data.materials}

    for bundle in dataset.orders:
        supplier = suppliers_by_id[bundle.bestellung.supplier_id]
        baustelle = baustellen_by_id[bundle.bestellung.baustelle_id]
        layout_index = _layout_index(supplier.id)

        for note in bundle.lieferscheine:
            material = materials_by_id[note.material_id]
            html = _render_lieferschein(note, bundle, supplier, baustelle, material, layout_index)
            HTML(string=html).write_pdf(pdf_dir / f"{note.ls_number}.pdf")

        rechnung_html = _render_rechnung(bundle.rechnung, bundle, supplier, materials_by_id, layout_index)
        HTML(string=rechnung_html).write_pdf(pdf_dir / f"{bundle.rechnung.re_number}.pdf")
