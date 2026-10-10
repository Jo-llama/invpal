"""Picks the fixed golden set of rendered documents, shared by the extraction CLI and the eval
harness so both agree on exactly the same 20 docs.
"""

from __future__ import annotations

from pathlib import Path


def select_golden_set(data_dir: Path, n_docs: int) -> tuple[list[Path], list[Path]]:
    """Returns (lieferschein_paths, rechnung_paths), split evenly and picked by filename sort
    for reproducibility.
    """
    ls_dir = Path(data_dir) / "rendered" / "img"
    re_dir = Path(data_dir) / "rendered" / "pdf"
    n_ls = n_docs // 2
    ls_files = sorted(ls_dir.glob("LS-*.png"))[:n_ls]
    re_files = sorted(re_dir.glob("RE-*.pdf"))[: n_docs - len(ls_files)]
    return ls_files, re_files
