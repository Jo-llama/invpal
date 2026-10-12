"""Self-consistency signal: re-run pipeline A n extra times per Lieferschein and measure how
often each field agrees with the primary extraction.

gpt-5-mini rejects any `temperature` other than its default (1) -- see extraction/provider.py's
module docstring on the parallel `logprobs` restriction -- so these repeats rely on whatever
inherent sampling variance the model has at default settings, not a deliberately widened one.

Own tiny disk cache keyed by (doc_id, sample index), separate from CachedProvider's
content-hash cache: CachedProvider is built to make repeated calls idempotent (cost control),
which is the opposite of what resampling needs.
"""

from __future__ import annotations

from pathlib import Path

from extraction.models import ExtractionResult, LieferscheinExtraction
from extraction.provider import AzureDocIntelOpenAIProvider


def sample_lieferschein(
    provider: AzureDocIntelOpenAIProvider, image_path: Path, doc_id: str, n_samples: int, cache_dir: Path
) -> list[ExtractionResult[LieferscheinExtraction]]:
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    samples = []
    for i in range(n_samples):
        cache_path = cache_dir / f"{doc_id}_sample{i}.json"
        if cache_path.exists():
            samples.append(ExtractionResult[LieferscheinExtraction].model_validate_json(cache_path.read_text()))
            continue
        result = provider.extract_lieferschein(image_path, doc_id)
        cache_path.write_text(result.model_dump_json())
        samples.append(result)
    return samples
