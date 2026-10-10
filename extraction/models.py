"""Pydantic schemas for extracted document fields and extraction results."""

from __future__ import annotations

from datetime import date
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field


class LieferscheinExtraction(BaseModel):
    ls_number: str
    order_number: str
    position_no: int
    date: date
    material_name: str
    quantity: float
    unit: str
    driver_name: str
    vehicle_plate: str
    signed: bool


class RechnungPositionExtraction(BaseModel):
    position_no: int
    material_name: str
    quantity: float
    unit: str
    unit_price: float
    total: float


class RechnungExtraction(BaseModel):
    re_number: str
    order_number: str
    date: date
    positions: list[RechnungPositionExtraction]
    total_amount: float


ExtractionT = TypeVar("ExtractionT", bound=BaseModel)


class FieldSignal(BaseModel):
    """Raw per-field uncertainty signal. Combined and calibrated later (step 4) -- kept raw here."""

    ocr_confidence: float | None = None
    token_logprob: float | None = None


class ExtractionResult(BaseModel, Generic[ExtractionT]):
    doc_id: str
    pipeline: Literal["A", "B"]
    fields: ExtractionT
    signals: dict[str, FieldSignal] = Field(default_factory=dict)
    latency_ms: float
