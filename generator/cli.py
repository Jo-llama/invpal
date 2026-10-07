"""CLI: python -m generator --n-orders 50 --seed 42 --out data/"""

from __future__ import annotations

import argparse
from pathlib import Path

from .generate import generate_dataset
from .writer import write_dataset


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="generator", description="Generate synthetic InvPal documents")
    parser.add_argument("--n-orders", type=int, default=50, help="Number of Bestellungen to generate")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--out", type=Path, default=Path("data"), help="Output directory")
    args = parser.parse_args(argv)

    dataset = generate_dataset(n_orders=args.n_orders, seed=args.seed)
    write_dataset(dataset, args.out)

    print(
        f"Generated {len(dataset.orders)} Bestellungen "
        f"({len(dataset.discrepancies)} with a planted discrepancy)\n"
        f"  docs:   {args.out / 'docs'}\n"
        f"  labels: {args.out / 'labels' / 'discrepancies.csv'}"
    )


if __name__ == "__main__":
    main()
