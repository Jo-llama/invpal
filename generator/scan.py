"""Converts rendered Lieferschein PDFs into degraded scan PNGs (clean/medium/bad
quality), via pdf2image + augraphy, with optional stamp/correction overlays.

Lieferscheine only: they are paper documents signed in the field and then
scanned/photographed, unlike Rechnungen which arrive as clean digital invoices.

Output: <out_dir>/rendered/img/<ls_number>.png
Labels: <out_dir>/labels/doc_quality.csv -- kept out of docs/ and rendered/.
"""

from __future__ import annotations

import csv
import hashlib
import random as py_random
from pathlib import Path

import cv2
import numpy as np
from augraphy import (
    AugraphyPipeline,
    Augmentation,
    Brightness,
    BleedThrough,
    DirtyDrum,
    DirtyRollers,
    Folding,
    Geometric,
    InkBleed,
    Jpeg,
    LowLightNoise,
    Markup,
    NoiseTexturize,
    ShadowCast,
)
from pdf2image import convert_from_path
from PIL import Image, ImageDraw, ImageFont

from .models import Dataset

DPI = 200
QUALITY_LEVELS = ("clean", "medium", "bad")
QUALITY_WEIGHTS = (0.60, 0.25, 0.15)
STAMP_PROBABILITY = 0.12
CORRECTION_PROBABILITY = 0.08

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

Phases = tuple[list[Augmentation], list[Augmentation], list[Augmentation]]


def _doc_seed(seed: int, ls_number: str, salt: str) -> int:
    """Deterministic 32-bit seed from (run seed, doc id, purpose) -- avoids
    Python's hash randomization, which would break reproducibility."""
    digest = hashlib.md5(f"{seed}-{ls_number}-{salt}".encode()).hexdigest()
    return int(digest, 16) % (2**31 - 1)


def _seed_rngs(seed: int) -> None:
    py_random.seed(seed)
    np.random.seed(seed)
    cv2.setRNGSeed(seed)


def _clean_phases() -> Phases:
    return (
        [],
        [],
        [
            Brightness(brightness_range=(0.96, 1.04), p=0.5),
            Jpeg(quality_range=(85, 95), p=0.6),
        ],
    )


def _medium_phases() -> Phases:
    return (
        [InkBleed(intensity_range=(0.2, 0.3), kernel_size=(3, 3), severity=(0.2, 0.3), p=0.4)],
        [
            DirtyRollers(line_width_range=(4, 8), p=0.3),
            NoiseTexturize(sigma_range=(2, 4), turbulence_range=(2, 3), p=0.3),
            BleedThrough(intensity_range=(0.05, 0.1), alpha=0.1, p=0.2),
        ],
        [
            Brightness(brightness_range=(0.9, 1.05), p=0.5),
            Geometric(rotate_range=(-2, 2), randomize=0, p=0.5),
            Jpeg(quality_range=(55, 80), p=0.6),
        ],
    )


def _bad_phases() -> Phases:
    return (
        [],
        [
            DirtyDrum(line_width_range=(1, 4), line_concentration=0.2, p=0.6),
            Folding(fold_count=3, fold_deviation=(2, 5), fold_angle_range=(-5, 5), p=0.5),
            ShadowCast(shadow_opacity_range=(0.2, 0.4), p=0.5),
        ],
        [
            LowLightNoise(num_photons_range=(150, 250), p=0.5),
            Geometric(rotate_range=(-6, 6), randomize=0, p=0.7),
            Jpeg(quality_range=(25, 50), p=0.8),
        ],
    )


_PHASE_BUILDERS = {"clean": _clean_phases, "medium": _medium_phases, "bad": _bad_phases}


def _correction_markup() -> Markup:
    return Markup(
        num_lines_range=(1, 2),
        markup_length_range=(0.2, 0.4),
        markup_thickness_range=(2, 3),
        markup_type="crossed",
        markup_ink="pen",
        markup_color=(200, 20, 20),
        single_word_mode=True,
        p=1,
    )


def _draw_stamp(image: np.ndarray, seed: int) -> np.ndarray:
    """Overlays a semi-transparent receiving stamp, rotated, in the upper-right
    region. Drawn before degradation so it gets degraded along with the page."""
    rng = py_random.Random(seed)
    h, w = image.shape[:2]
    pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB)).convert("RGBA")
    overlay = Image.new("RGBA", pil_image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    cx = rng.randint(int(w * 0.65), int(w * 0.85))
    cy = rng.randint(int(h * 0.08), int(h * 0.20))
    radius = rng.randint(70, 95)
    color = rng.choice([(190, 20, 20, 170), (20, 70, 160, 170)])

    draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline=color, width=4)
    font = ImageFont.truetype(FONT_PATH, size=18)
    draw.text((cx, cy), "WARENEINGANG", font=font, fill=color, anchor="mm")

    overlay = overlay.rotate(rng.uniform(-15, 15), resample=Image.BICUBIC, center=(cx, cy))
    composed = Image.alpha_composite(pil_image, overlay).convert("RGB")
    return cv2.cvtColor(np.array(composed), cv2.COLOR_RGB2BGR)


def _render_scan(pdf_path: Path, seed: int, quality: str, has_stamp: bool, has_correction: bool) -> np.ndarray:
    page = convert_from_path(pdf_path, dpi=DPI)[0]
    image = cv2.cvtColor(np.array(page), cv2.COLOR_RGB2BGR)

    if has_stamp:
        image = _draw_stamp(image, _doc_seed(seed, pdf_path.stem, "stamp"))

    ink_phase, paper_phase, post_phase = _PHASE_BUILDERS[quality]()
    if has_correction:
        ink_phase = [*ink_phase, _correction_markup()]
    pipeline = AugraphyPipeline(ink_phase=ink_phase, paper_phase=paper_phase, post_phase=post_phase)

    _seed_rngs(_doc_seed(seed, pdf_path.stem, "augraphy"))
    result = pipeline.augment(image)
    return result["output"]


def render_scans(dataset: Dataset, out_dir: Path, seed: int) -> None:
    out_dir = Path(out_dir)
    pdf_dir = out_dir / "rendered" / "pdf"
    img_dir = out_dir / "rendered" / "img"
    labels_dir = out_dir / "labels"
    img_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)

    assign_rng = py_random.Random(seed)
    rows = []
    for bundle in dataset.orders:
        for note in bundle.lieferscheine:
            quality = assign_rng.choices(QUALITY_LEVELS, weights=QUALITY_WEIGHTS, k=1)[0]
            has_stamp = assign_rng.random() < STAMP_PROBABILITY
            has_correction = assign_rng.random() < CORRECTION_PROBABILITY

            pdf_path = pdf_dir / f"{note.ls_number}.pdf"
            image = _render_scan(pdf_path, seed, quality, has_stamp, has_correction)
            cv2.imwrite(str(img_dir / f"{note.ls_number}.png"), image)

            rows.append(
                {
                    "ls_number": note.ls_number,
                    "quality_level": quality,
                    "has_stamp": has_stamp,
                    "has_correction": has_correction,
                }
            )

    _write_quality_csv(rows, labels_dir / "doc_quality.csv")


def _write_quality_csv(rows: list[dict], path: Path) -> None:
    fieldnames = ["ls_number", "quality_level", "has_stamp", "has_correction"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
