"""Disk cache for extraction provider calls, keyed by (provider, schema, document content hash).

Cost control: repeated runs/tests over the same rendered doc hit disk instead of the API.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from .models import ExtractionResult, LieferscheinExtraction, RechnungExtraction
from .provider import Provider


class CachedProvider:
    """Wraps a Provider, caching each extract_* result on disk."""

    def __init__(self, provider: Provider, cache_dir: Path) -> None:
        self._provider = provider
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, doc_path: Path, schema_name: str) -> Path:
        content_hash = hashlib.sha256(doc_path.read_bytes()).hexdigest()[:16]
        provider_name = type(self._provider).__name__
        return self._cache_dir / f"{provider_name}_{schema_name}_{content_hash}.json"

    def extract_lieferschein(self, image_path: Path, doc_id: str) -> ExtractionResult[LieferscheinExtraction]:
        cache_path = self._cache_path(image_path, "lieferschein")
        if cache_path.exists():
            return ExtractionResult[LieferscheinExtraction].model_validate_json(cache_path.read_text())
        result = self._provider.extract_lieferschein(image_path, doc_id)
        cache_path.write_text(result.model_dump_json())
        return result

    def extract_rechnung(self, pdf_path: Path, doc_id: str) -> ExtractionResult[RechnungExtraction]:
        cache_path = self._cache_path(pdf_path, "rechnung")
        if cache_path.exists():
            return ExtractionResult[RechnungExtraction].model_validate_json(cache_path.read_text())
        result = self._provider.extract_rechnung(pdf_path, doc_id)
        cache_path.write_text(result.model_dump_json())
        return result
