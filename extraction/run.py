"""CLI: python -m extraction --n-docs 20 --provider azure|mock"""

from __future__ import annotations

import argparse
from pathlib import Path

from .cache import CachedProvider
from .golden_set import select_golden_set
from .provider import AzureConfig, AzureDocIntelOpenAIProvider, MockProvider, VisionOnlyProvider
from .training_set import select_training_set


def run_extraction(
    ls_files: list[Path], re_files: list[Path], provider_a: CachedProvider, provider_b: CachedProvider, out_dir: Path
) -> int:
    """Runs both pipelines over the given docs, writing `{doc_id}_{A,B}.json` into out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    n_results = 0
    for path in ls_files:
        doc_id = path.stem
        for label, provider in (("A", provider_a), ("B", provider_b)):
            result = provider.extract_lieferschein(path, doc_id)
            (out_dir / f"{doc_id}_{label}.json").write_text(result.model_dump_json(indent=2))
            n_results += 1
    for path in re_files:
        doc_id = path.stem
        for label, provider in (("A", provider_a), ("B", provider_b)):
            result = provider.extract_rechnung(path, doc_id)
            (out_dir / f"{doc_id}_{label}.json").write_text(result.model_dump_json(indent=2))
            n_results += 1
    return n_results


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="extraction", description="Run pipelines A and B over rendered documents")
    parser.add_argument("--n-docs", type=int, default=20, help="Total documents to process (golden set only)")
    parser.add_argument(
        "--set",
        choices=["golden", "training"],
        default="golden",
        help="golden: fixed 20-doc eval set (step 3). training: 1 LS + 1 RE per Bestellung (step 4).",
    )
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=Path("data/extracted"))
    parser.add_argument("--cache-dir", type=Path, default=Path("data/cache/extraction"))
    parser.add_argument("--provider", choices=["azure", "mock"], default="azure")
    args = parser.parse_args(argv)

    if args.set == "training":
        ls_files, re_files = select_training_set(args.data_dir)
    else:
        ls_files, re_files = select_golden_set(args.data_dir, args.n_docs)

    if args.provider == "mock":
        base_a: object = MockProvider(data_dir=args.data_dir, pipeline="A")
        base_b: object = MockProvider(data_dir=args.data_dir, pipeline="B")
    else:
        config = AzureConfig.from_env()
        base_a = AzureDocIntelOpenAIProvider(config)
        base_b = VisionOnlyProvider(config)

    provider_a = CachedProvider(base_a, args.cache_dir / "pipeline_a")
    provider_b = CachedProvider(base_b, args.cache_dir / "pipeline_b")

    n_results = run_extraction(ls_files, re_files, provider_a, provider_b, args.out)

    print(
        f"Extracted {n_results} results ({args.provider} provider, {args.set} set) from "
        f"{len(ls_files)} Lieferscheine + {len(re_files)} Rechnungen -> {args.out}"
    )


if __name__ == "__main__":
    main()
