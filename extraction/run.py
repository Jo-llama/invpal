"""CLI: python -m extraction --n-docs 20 --provider azure|mock"""

from __future__ import annotations

import argparse
from pathlib import Path

from .cache import CachedProvider
from .provider import AzureConfig, AzureDocIntelOpenAIProvider, MockProvider, VisionOnlyProvider


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="extraction", description="Run pipelines A and B over rendered documents")
    parser.add_argument("--n-docs", type=int, default=20, help="Total documents to process (split across LS/RE)")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=Path("data/extracted"))
    parser.add_argument("--cache-dir", type=Path, default=Path("data/cache/extraction"))
    parser.add_argument("--provider", choices=["azure", "mock"], default="azure")
    args = parser.parse_args(argv)

    ls_dir = args.data_dir / "rendered" / "img"
    re_dir = args.data_dir / "rendered" / "pdf"
    n_ls = args.n_docs // 2
    ls_files = sorted(ls_dir.glob("LS-*.png"))[:n_ls]
    re_files = sorted(re_dir.glob("RE-*.pdf"))[: args.n_docs - len(ls_files)]

    if args.provider == "mock":
        base_a: object = MockProvider(data_dir=args.data_dir, pipeline="A")
        base_b: object = MockProvider(data_dir=args.data_dir, pipeline="B")
    else:
        config = AzureConfig.from_env()
        base_a = AzureDocIntelOpenAIProvider(config)
        base_b = VisionOnlyProvider(config)

    provider_a = CachedProvider(base_a, args.cache_dir / "pipeline_a")
    provider_b = CachedProvider(base_b, args.cache_dir / "pipeline_b")

    args.out.mkdir(parents=True, exist_ok=True)
    n_results = 0
    for path in ls_files:
        doc_id = path.stem
        for label, provider in (("A", provider_a), ("B", provider_b)):
            result = provider.extract_lieferschein(path, doc_id)
            (args.out / f"{doc_id}_{label}.json").write_text(result.model_dump_json(indent=2))
            n_results += 1
    for path in re_files:
        doc_id = path.stem
        for label, provider in (("A", provider_a), ("B", provider_b)):
            result = provider.extract_rechnung(path, doc_id)
            (args.out / f"{doc_id}_{label}.json").write_text(result.model_dump_json(indent=2))
            n_results += 1

    print(
        f"Extracted {n_results} results ({args.provider} provider) from "
        f"{len(ls_files)} Lieferscheine + {len(re_files)} Rechnungen -> {args.out}"
    )


if __name__ == "__main__":
    main()
