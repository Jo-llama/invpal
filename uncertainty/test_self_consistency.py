from datetime import date
from pathlib import Path

from extraction.models import ExtractionResult, LieferscheinExtraction

from .self_consistency import sample_lieferschein


def _fields(seed: int) -> LieferscheinExtraction:
    return LieferscheinExtraction(
        ls_number="LS-1", order_number="BST-1", position_no=1, date=date(2024, 1, 1),
        material_name="Kies", quantity=float(seed), unit="t", driver_name="X", vehicle_plate="Y", signed=True,
    )


class _CountingFakeProvider:
    def __init__(self) -> None:
        self.calls = 0

    def extract_lieferschein(self, image_path, doc_id):
        self.calls += 1
        return ExtractionResult[LieferscheinExtraction](
            doc_id=doc_id, pipeline="A", fields=_fields(self.calls), signals={}, latency_ms=1.0
        )


def test_sample_lieferschein_calls_provider_n_times(tmp_path: Path) -> None:
    provider = _CountingFakeProvider()

    samples = sample_lieferschein(provider, tmp_path / "doc.png", "LS-1", n_samples=3, cache_dir=tmp_path / "cache")

    assert len(samples) == 3
    assert provider.calls == 3
    assert [s.fields.quantity for s in samples] == [1.0, 2.0, 3.0]


def test_sample_lieferschein_reuses_its_own_cache_on_a_second_call(tmp_path: Path) -> None:
    provider = _CountingFakeProvider()
    cache_dir = tmp_path / "cache"

    sample_lieferschein(provider, tmp_path / "doc.png", "LS-1", n_samples=2, cache_dir=cache_dir)
    provider.calls = 0
    samples = sample_lieferschein(provider, tmp_path / "doc.png", "LS-1", n_samples=2, cache_dir=cache_dir)

    assert provider.calls == 0
    assert len(samples) == 2
