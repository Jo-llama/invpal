"""CLI: python -m eval --extracted-dir data/extracted --data-dir data --out reports"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from extraction.golden_set import select_golden_set
from extraction.ground_truth import load_lieferschein_truth, load_material_names, load_rechnung_truth
from extraction.models import ExtractionResult, LieferscheinExtraction, RechnungExtraction

from .metrics import FieldComparison, aggregate, compare_lieferschein, compare_rechnung
from .report import build_report, render_markdown_table


def _load_quality_levels(data_dir: Path) -> dict[str, str]:
    path = Path(data_dir) / "labels" / "doc_quality.csv"
    with path.open(newline="", encoding="utf-8") as f:
        return {row["ls_number"]: row["quality_level"] for row in csv.DictReader(f)}


def _load_extraction_result(
    extracted_dir: Path, doc_id: str, pipeline: str, schema: type[LieferscheinExtraction] | type[RechnungExtraction]
):
    path = Path(extracted_dir) / f"{doc_id}_{pipeline}.json"
    if not path.exists():
        return None
    return ExtractionResult[schema].model_validate_json(path.read_text())


def collect_comparisons(extracted_dir: Path, data_dir: Path, n_docs: int) -> tuple[list[FieldComparison], int]:
    ls_files, re_files = select_golden_set(data_dir, n_docs)
    quality_levels = _load_quality_levels(data_dir)
    materials = load_material_names(data_dir)

    comparisons: list[FieldComparison] = []
    missing: list[str] = []

    for path in ls_files:
        doc_id = path.stem
        quality_level = quality_levels.get(doc_id, "unknown")
        true = load_lieferschein_truth(doc_id, data_dir, materials)
        for pipeline in ("A", "B"):
            result = _load_extraction_result(extracted_dir, doc_id, pipeline, LieferscheinExtraction)
            if result is None:
                missing.append(f"{doc_id}_{pipeline}")
                continue
            comparisons.extend(compare_lieferschein(pipeline, quality_level, result.fields, true))

    for path in re_files:
        doc_id = path.stem
        true = load_rechnung_truth(doc_id, data_dir, materials)
        for pipeline in ("A", "B"):
            result = _load_extraction_result(extracted_dir, doc_id, pipeline, RechnungExtraction)
            if result is None:
                missing.append(f"{doc_id}_{pipeline}")
                continue
            comparisons.extend(compare_rechnung(pipeline, "digital", result.fields, true))

    if missing:
        raise FileNotFoundError(
            "Missing extraction results for: " + ", ".join(missing) + ". Run `python -m extraction` first."
        )

    return comparisons, len(ls_files) + len(re_files)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="eval", description="Compare extraction results against ground truth")
    parser.add_argument("--extracted-dir", type=Path, default=Path("data/extracted"))
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=Path("reports"))
    parser.add_argument("--n-docs", type=int, default=20)
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args(argv)

    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    comparisons, n_docs = collect_comparisons(args.extracted_dir, args.data_dir, args.n_docs)
    aggregated = aggregate(comparisons)

    args.out.mkdir(parents=True, exist_ok=True)
    report = build_report(run_id, n_docs, aggregated)
    (args.out / f"eval_{run_id}.json").write_text(json.dumps(report, indent=2))

    table = render_markdown_table(aggregated)
    (args.out / f"eval_{run_id}.md").write_text(table + "\n")

    print(table)


if __name__ == "__main__":
    main()
