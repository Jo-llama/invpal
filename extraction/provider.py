"""Extraction providers: pipeline A (Document Intelligence + LLM), pipeline B (vision-only),
and a deterministic mock for tests.

Both real pipelines ask the LLM for structured output matching the target schema directly
(``chat.completions.parse``), and keep two raw per-field uncertainty signals for step 4 to
combine/calibrate later: Document Intelligence word confidence (pipeline A only) and the LLM's
own token logprobs (both pipelines, when the deployed model supports the ``logprobs`` request
parameter -- gpt-5-mini does not, so ``token_logprob`` signals are currently always None; the
plumbing stays in place for a model/API version that does). Signal attribution is a best-effort
text-match against the model's own JSON output, not a guaranteed exact mapping -- fine as a
*raw* signal for now.
"""

from __future__ import annotations

import base64
import io
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv
from openai import AzureOpenAI
from pdf2image import convert_from_path
from PIL import Image
from pydantic import BaseModel

from .models import (
    ExtractionResult,
    ExtractionT,
    FieldSignal,
    LieferscheinExtraction,
    RechnungExtraction,
    RechnungPositionExtraction,
)

SYSTEM_PROMPT_LIEFERSCHEIN = (
    "You extract structured data from a German construction delivery note (Lieferschein). "
    "Return exactly the fields of the schema, using the values as printed on the document."
)
SYSTEM_PROMPT_RECHNUNG = (
    "You extract structured data from a German construction invoice (Rechnung). "
    "Return exactly the fields of the schema, using the values as printed on the document."
)


class Provider(Protocol):
    def extract_lieferschein(self, image_path: Path, doc_id: str) -> ExtractionResult[LieferscheinExtraction]: ...

    def extract_rechnung(self, pdf_path: Path, doc_id: str) -> ExtractionResult[RechnungExtraction]: ...


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


@dataclass
class AzureConfig:
    di_endpoint: str
    di_key: str
    oai_endpoint: str
    oai_key: str
    oai_deployment: str
    oai_api_version: str

    @classmethod
    def from_env(cls) -> AzureConfig:
        load_dotenv()
        return cls(
            di_endpoint=_require_env("AZURE_DOCUMENTINTELLIGENCE_ENDPOINT"),
            di_key=_require_env("AZURE_DOCUMENTINTELLIGENCE_KEY"),
            oai_endpoint=_require_env("AZURE_OPENAI_ENDPOINT"),
            oai_key=_require_env("AZURE_OPENAI_KEY"),
            oai_deployment=_require_env("AZURE_OPENAI_DEPLOYMENT"),
            oai_api_version=_require_env("AZURE_OPENAI_API_VERSION"),
        )


def _token_spans(tokens: list) -> list[tuple[int, int, float]]:
    """Reconstructs character offsets for each output token from its raw bytes."""
    spans = []
    pos = 0
    for t in tokens:
        text = bytes(t.bytes).decode("utf-8", errors="ignore") if t.bytes else t.token
        start, end = pos, pos + len(text)
        spans.append((start, end, t.logprob))
        pos = end
    return spans


def _field_logprobs(raw_json: str, spans: list[tuple[int, int, float]], field_names: list[str]) -> dict[str, float]:
    signals: dict[str, float] = {}
    for name in field_names:
        match = re.search(rf'"{name}"\s*:\s*("(?:[^"\\]|\\.)*"|[^,{{}}\[\]]+)', raw_json)
        if not match:
            continue
        value_start, value_end = match.span(1)
        overlapping = [lp for (s, e, lp) in spans if e > value_start and s < value_end]
        if overlapping:
            signals[name] = sum(overlapping) / len(overlapping)
    return signals


def _ocr_field_confidence(fields: BaseModel, words: list[tuple[str, float]]) -> dict[str, float]:
    word_confidence: dict[str, float] = {}
    for word, confidence in words:
        key = word.strip().lower()
        if key and key not in word_confidence:
            word_confidence[key] = confidence

    signals: dict[str, float] = {}
    for name, value in fields.model_dump(mode="json").items():
        if isinstance(value, list):
            continue
        tokens = str(value).split()
        matched = [word_confidence[tok.lower()] for tok in tokens if tok.lower() in word_confidence]
        if matched:
            signals[name] = sum(matched) / len(matched)
    return signals


def _scalar_field_names(fields: BaseModel) -> list[str]:
    return [name for name, value in fields.model_dump(mode="json").items() if not isinstance(value, list)]


_DI_MAX_BYTES = 4 * 1024 * 1024  # Document Intelligence free-tier (F0) request size cap


def _shrink_for_document_intelligence(doc_path: Path) -> bytes:
    """Degraded scans can exceed the DI free-tier size cap; re-encode as JPEG until it fits."""
    data = doc_path.read_bytes()
    if len(data) <= _DI_MAX_BYTES or doc_path.suffix.lower() == ".pdf":
        return data

    image = Image.open(io.BytesIO(data)).convert("RGB")
    quality, scale = 85, 1.0
    while True:
        resized = image if scale == 1.0 else image.resize((int(image.width * scale), int(image.height * scale)))
        buf = io.BytesIO()
        resized.save(buf, format="JPEG", quality=quality)
        data = buf.getvalue()
        if len(data) <= _DI_MAX_BYTES or (quality <= 40 and scale <= 0.5):
            return data
        if quality > 40:
            quality -= 15
        else:
            scale *= 0.8


class AzureDocIntelOpenAIProvider:
    """Pipeline A: Azure Document Intelligence (layout) -> Azure OpenAI structured output."""

    def __init__(self, config: AzureConfig | None = None) -> None:
        self._config = config or AzureConfig.from_env()
        self._di = DocumentIntelligenceClient(self._config.di_endpoint, AzureKeyCredential(self._config.di_key))
        self._oai = AzureOpenAI(
            azure_endpoint=self._config.oai_endpoint,
            api_key=self._config.oai_key,
            api_version=self._config.oai_api_version,
        )

    def _analyze(self, doc_path: Path) -> tuple[str, list[tuple[str, float]]]:
        body = _shrink_for_document_intelligence(doc_path)
        poller = self._di.begin_analyze_document("prebuilt-layout", body=io.BytesIO(body))
        result = poller.result()
        words = [(w.content, w.confidence) for page in result.pages for w in (page.words or [])]
        return result.content or "", words

    def _complete(self, system_prompt: str, document_text: str, schema: type[ExtractionT]):
        start = time.monotonic()
        completion = self._oai.chat.completions.parse(
            model=self._config.oai_deployment,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Document text:\n\n{document_text}"},
            ],
            response_format=schema,
        )
        latency_ms = (time.monotonic() - start) * 1000
        choice = completion.choices[0]
        tokens = choice.logprobs.content if choice.logprobs else []
        return choice.message.parsed, choice.message.content or "", tokens, latency_ms

    def extract_lieferschein(self, image_path: Path, doc_id: str) -> ExtractionResult[LieferscheinExtraction]:
        document_text, words = self._analyze(image_path)
        parsed, raw_text, tokens, latency_ms = self._complete(
            SYSTEM_PROMPT_LIEFERSCHEIN, document_text, LieferscheinExtraction
        )
        ocr = _ocr_field_confidence(parsed, words)
        logprobs = _field_logprobs(raw_text, _token_spans(tokens), _scalar_field_names(parsed))
        signals = {
            name: FieldSignal(ocr_confidence=ocr.get(name), token_logprob=logprobs.get(name))
            for name in _scalar_field_names(parsed)
        }
        return ExtractionResult[LieferscheinExtraction](
            doc_id=doc_id, pipeline="A", fields=parsed, signals=signals, latency_ms=latency_ms
        )

    def extract_rechnung(self, pdf_path: Path, doc_id: str) -> ExtractionResult[RechnungExtraction]:
        document_text, words = self._analyze(pdf_path)
        parsed, raw_text, tokens, latency_ms = self._complete(SYSTEM_PROMPT_RECHNUNG, document_text, RechnungExtraction)
        ocr = _ocr_field_confidence(parsed, words)
        logprobs = _field_logprobs(raw_text, _token_spans(tokens), _scalar_field_names(parsed))
        signals = {
            name: FieldSignal(ocr_confidence=ocr.get(name), token_logprob=logprobs.get(name))
            for name in _scalar_field_names(parsed)
        }
        return ExtractionResult[RechnungExtraction](
            doc_id=doc_id, pipeline="A", fields=parsed, signals=signals, latency_ms=latency_ms
        )


class VisionOnlyProvider:
    """Pipeline B: vision model only, no OCR step -- baseline to compare pipeline A against."""

    def __init__(self, config: AzureConfig | None = None) -> None:
        self._config = config or AzureConfig.from_env()
        self._oai = AzureOpenAI(
            azure_endpoint=self._config.oai_endpoint,
            api_key=self._config.oai_key,
            api_version=self._config.oai_api_version,
        )

    def _image_bytes(self, doc_path: Path) -> bytes:
        if doc_path.suffix.lower() == ".pdf":
            page = convert_from_path(str(doc_path), dpi=150)[0]
            buf = io.BytesIO()
            page.save(buf, format="PNG")
            return buf.getvalue()
        return doc_path.read_bytes()

    def _complete(self, system_prompt: str, image_bytes: bytes, schema: type[ExtractionT]):
        b64 = base64.b64encode(image_bytes).decode("ascii")
        start = time.monotonic()
        completion = self._oai.chat.completions.parse(
            model=self._config.oai_deployment,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Extract the fields from this document image."},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    ],
                },
            ],
            response_format=schema,
        )
        latency_ms = (time.monotonic() - start) * 1000
        choice = completion.choices[0]
        tokens = choice.logprobs.content if choice.logprobs else []
        return choice.message.parsed, choice.message.content or "", tokens, latency_ms

    def extract_lieferschein(self, image_path: Path, doc_id: str) -> ExtractionResult[LieferscheinExtraction]:
        parsed, raw_text, tokens, latency_ms = self._complete(
            SYSTEM_PROMPT_LIEFERSCHEIN, self._image_bytes(image_path), LieferscheinExtraction
        )
        logprobs = _field_logprobs(raw_text, _token_spans(tokens), _scalar_field_names(parsed))
        signals = {name: FieldSignal(token_logprob=logprobs.get(name)) for name in _scalar_field_names(parsed)}
        return ExtractionResult[LieferscheinExtraction](
            doc_id=doc_id, pipeline="B", fields=parsed, signals=signals, latency_ms=latency_ms
        )

    def extract_rechnung(self, pdf_path: Path, doc_id: str) -> ExtractionResult[RechnungExtraction]:
        parsed, raw_text, tokens, latency_ms = self._complete(
            SYSTEM_PROMPT_RECHNUNG, self._image_bytes(pdf_path), RechnungExtraction
        )
        logprobs = _field_logprobs(raw_text, _token_spans(tokens), _scalar_field_names(parsed))
        signals = {name: FieldSignal(token_logprob=logprobs.get(name)) for name in _scalar_field_names(parsed)}
        return ExtractionResult[RechnungExtraction](
            doc_id=doc_id, pipeline="B", fields=parsed, signals=signals, latency_ms=latency_ms
        )


class MockProvider:
    """Deterministic provider for tests: reads the generator's own ground truth, no network calls."""

    def __init__(self, data_dir: Path = Path("data"), pipeline: str = "A") -> None:
        self._data_dir = Path(data_dir)
        self._pipeline = pipeline
        master_data = json.loads((self._data_dir / "master_data.json").read_text())
        self._materials = {m["id"]: m["name"] for m in master_data["materials"]}

    def extract_lieferschein(self, image_path: Path, doc_id: str) -> ExtractionResult[LieferscheinExtraction]:
        truth = json.loads((self._data_dir / "docs" / "delivery_notes" / f"{doc_id}.json").read_text())
        fields = LieferscheinExtraction(
            ls_number=truth["ls_number"],
            order_number=truth["order_number_ref"],
            position_no=truth["position_no"],
            date=truth["date"],
            material_name=self._materials[truth["material_id"]],
            quantity=truth["quantity"],
            unit=truth["unit"],
            driver_name=truth["driver_name"],
            vehicle_plate=truth["vehicle_plate"],
            signed=truth["signed"],
        )
        signals = {
            name: FieldSignal(ocr_confidence=0.95, token_logprob=-0.05) for name in LieferscheinExtraction.model_fields
        }
        return ExtractionResult[LieferscheinExtraction](
            doc_id=doc_id, pipeline=self._pipeline, fields=fields, signals=signals, latency_ms=0.0
        )

    def extract_rechnung(self, pdf_path: Path, doc_id: str) -> ExtractionResult[RechnungExtraction]:
        truth = json.loads((self._data_dir / "docs" / "invoices" / f"{doc_id}.json").read_text())
        positions = [
            RechnungPositionExtraction(
                position_no=p["position_no"],
                material_name=self._materials[p["material_id"]],
                quantity=p["quantity"],
                unit=p["unit"],
                unit_price=p["unit_price"],
                total=p["total"],
            )
            for p in truth["positions"]
        ]
        fields = RechnungExtraction(
            re_number=truth["re_number"],
            order_number=truth["order_number_ref"],
            date=truth["date"],
            positions=positions,
            total_amount=truth["total_amount"],
        )
        signals = {
            name: FieldSignal(ocr_confidence=0.95, token_logprob=-0.05)
            for name in RechnungExtraction.model_fields
            if name != "positions"
        }
        return ExtractionResult[RechnungExtraction](
            doc_id=doc_id, pipeline=self._pipeline, fields=fields, signals=signals, latency_ms=0.0
        )
