"""CLI: python -m uncertainty [--target-precision 0.99] [--skip-self-consistency]"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from extraction.provider import AzureConfig, AzureDocIntelOpenAIProvider

from .dataset import build_rows
from .evaluate import (
    doc_level_auto_approval,
    expected_calibration_error,
    find_threshold_for_precision,
    per_field_confidence_summary,
    precision_at_threshold,
    reliability_diagram,
)

KNOWN_BROKEN_FIELDS = {"date", "signed"}
from .model import fit
from .split import split_by_bestellung


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="uncertainty", description="Calibrate field-level confidence and find the auto-approval threshold"
    )
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--extracted-dir", type=Path, default=Path("data/extracted_training"))
    parser.add_argument("--self-consistency-dir", type=Path, default=Path("data/cache/self_consistency"))
    parser.add_argument("--n-self-consistency", type=int, default=2)
    parser.add_argument("--target-precision", type=float, default=0.99)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=Path("reports"))
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--skip-self-consistency", action="store_true")
    args = parser.parse_args(argv)

    live_provider = None
    if not args.skip_self_consistency:
        live_provider = AzureDocIntelOpenAIProvider(AzureConfig.from_env())

    rows = build_rows(
        args.data_dir,
        args.extracted_dir,
        live_provider_a=live_provider,
        self_consistency_dir=args.self_consistency_dir,
        n_self_consistency=args.n_self_consistency,
    )

    split = split_by_bestellung(rows, seed=args.seed)
    model = fit(split.train, split.calib)

    test_confidences = model.predict(split.test)
    test_correct = np.array([1.0 if r.is_correct else 0.0 for r in split.test])

    ece = expected_calibration_error(test_confidences, test_correct)

    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    args.out.mkdir(parents=True, exist_ok=True)
    reliability_path = args.out / f"reliability_{run_id}.png"
    reliability_diagram(test_confidences, test_correct, reliability_path)

    threshold = find_threshold_for_precision(test_confidences, test_correct, args.target_precision)
    if threshold is None:
        headline = f"Target precision {args.target_precision:.0%} not reachable on the test split."
        achieved_precision = field_rate = None
        doc_result = None
    else:
        achieved_precision, field_rate = precision_at_threshold(test_confidences, test_correct, threshold)
        doc_result = doc_level_auto_approval(split.test, test_confidences, threshold)
        headline = f"At {args.target_precision:.0%} precision, {doc_result.auto_approval_rate:.0%} of Lieferscheine auto-approved."

    field_confidence = per_field_confidence_summary(split.test, test_confidences)

    # Sensitivity check, not the headline: date (systematic misparse, step 2/3) and signed
    # (pipeline A structurally can't see it) are known-broken independent of calibration quality.
    # Shows whether 0% auto-approval is "the pipeline needs these two fixed" or "nothing clears."
    core_pairs = [(r, c) for r, c in zip(split.test, test_confidences) if r.field not in KNOWN_BROKEN_FIELDS]
    core_rows = [r for r, _ in core_pairs]
    core_confidences = np.array([c for _, c in core_pairs])
    core_correct = np.array([1.0 if r.is_correct else 0.0 for r in core_rows])
    core_threshold = find_threshold_for_precision(core_confidences, core_correct, args.target_precision)
    if core_threshold is not None:
        core_doc_result = doc_level_auto_approval(core_rows, core_confidences, core_threshold)
    else:
        core_doc_result = None

    report = {
        "run_id": run_id,
        "seed": args.seed,
        "n_rows": {"train": len(split.train), "calib": len(split.calib), "test": len(split.test)},
        "n_bestellungen": {
            "train": len({r.bestellung_id for r in split.train}),
            "calib": len({r.bestellung_id for r in split.calib}),
            "test": len({r.bestellung_id for r in split.test}),
        },
        "ece": ece,
        "target_precision": args.target_precision,
        "threshold": threshold,
        "achieved_field_precision": achieved_precision,
        "field_auto_approval_rate": field_rate,
        "doc_level": {
            "n_docs": doc_result.n_docs if doc_result else None,
            "n_auto_approved": doc_result.n_auto_approved if doc_result else None,
            "auto_approval_rate": doc_result.auto_approval_rate if doc_result else None,
        },
        "headline": headline,
        "reliability_diagram": reliability_path.name,
        "per_field_confidence_test": field_confidence,
        "sensitivity_excl_known_broken_fields": {
            "note": (
                "Diagnostic, not the headline: excludes 'date' (systematic misparse, see steps 2/3) "
                "and 'signed' (pipeline A can't see the image) to show whether 0% auto-approval is "
                "driven by those two known issues or reflects the whole pipeline."
            ),
            "excluded_fields": sorted(KNOWN_BROKEN_FIELDS),
            "threshold": core_threshold,
            "doc_level": {
                "n_docs": core_doc_result.n_docs if core_doc_result else None,
                "n_auto_approved": core_doc_result.n_auto_approved if core_doc_result else None,
                "auto_approval_rate": core_doc_result.auto_approval_rate if core_doc_result else None,
            },
        },
    }
    (args.out / f"uncertainty_{run_id}.json").write_text(json.dumps(report, indent=2))

    md_lines = [
        f"# Uncertainty layer -- run {run_id}",
        "",
        f"**{headline}**",
        "",
        f"- Rows: train {len(split.train)}, calib {len(split.calib)}, test {len(split.test)}",
        f"- Bestellungen: train {report['n_bestellungen']['train']}, "
        f"calib {report['n_bestellungen']['calib']}, test {report['n_bestellungen']['test']}",
        f"- ECE (test split): {ece:.4f}",
    ]
    if threshold is not None:
        md_lines += [
            f"- Threshold: {threshold:.4f}",
            f"- Field precision at threshold: {achieved_precision:.2%}",
            f"- Field auto-approval rate at threshold: {field_rate:.2%}",
        ]
    md_lines += [
        "",
        "## Per-field confidence (test split)",
        "",
        "| field | n | min | max | mean |",
        "|---|---|---|---|---|",
    ]
    md_lines += [
        f"| {field} | {s['n']} | {s['min']:.3f} | {s['max']:.3f} | {s['mean']:.3f} |"
        for field, s in field_confidence.items()
    ]
    md_lines += [
        "",
        "## Sensitivity: excluding `date` and `signed`",
        "",
        report["sensitivity_excl_known_broken_fields"]["note"],
        "",
        f"- Doc-level auto-approval, core fields only: "
        f"{report['sensitivity_excl_known_broken_fields']['doc_level']['auto_approval_rate']}",
        "",
        f"- Reliability diagram: {reliability_path.name}",
    ]
    (args.out / f"uncertainty_{run_id}.md").write_text("\n".join(md_lines) + "\n")

    print(headline)
    print(f"ECE: {ece:.4f}")


if __name__ == "__main__":
    main()
