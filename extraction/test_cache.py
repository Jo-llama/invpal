from pathlib import Path

from generator.generate import generate_dataset
from generator.writer import write_dataset

from .cache import CachedProvider
from .provider import MockProvider


class CountingProvider:
    """Wraps a Provider and counts calls, to prove the cache avoids re-invoking it."""

    def __init__(self, inner: MockProvider) -> None:
        self._inner = inner
        self.calls = 0

    def extract_lieferschein(self, image_path: Path, doc_id: str):
        self.calls += 1
        return self._inner.extract_lieferschein(image_path, doc_id)

    def extract_rechnung(self, pdf_path: Path, doc_id: str):
        self.calls += 1
        return self._inner.extract_rechnung(pdf_path, doc_id)


def test_cached_provider_only_calls_inner_provider_once(tmp_path) -> None:
    dataset = generate_dataset(n_orders=3, seed=2)
    data_dir = tmp_path / "data"
    write_dataset(dataset, data_dir)
    note = dataset.orders[0].lieferscheine[0]

    doc_path = tmp_path / f"{note.ls_number}.png"
    doc_path.write_bytes(b"fake-image-bytes")

    counting = CountingProvider(MockProvider(data_dir=data_dir))
    cached = CachedProvider(counting, cache_dir=tmp_path / "cache")

    first = cached.extract_lieferschein(doc_path, note.ls_number)
    second = cached.extract_lieferschein(doc_path, note.ls_number)

    assert counting.calls == 1
    assert first == second


def test_cached_provider_cache_is_specific_to_document_content(tmp_path) -> None:
    dataset = generate_dataset(n_orders=3, seed=3)
    data_dir = tmp_path / "data"
    write_dataset(dataset, data_dir)
    note = dataset.orders[0].lieferscheine[0]

    doc_path_a = tmp_path / "a.png"
    doc_path_a.write_bytes(b"version-a")
    doc_path_b = tmp_path / "b.png"
    doc_path_b.write_bytes(b"version-b")

    counting = CountingProvider(MockProvider(data_dir=data_dir))
    cached = CachedProvider(counting, cache_dir=tmp_path / "cache")

    cached.extract_lieferschein(doc_path_a, note.ls_number)
    cached.extract_lieferschein(doc_path_b, note.ls_number)

    assert counting.calls == 2
