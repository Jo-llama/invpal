"""Pydantic models for all master data, documents and discrepancy records."""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel


class Unit(str, Enum):
    TONNE = "t"
    CUBIC_METER = "m³"
    KILOGRAM = "kg"
    PIECE = "Stk"


class MaterialCategory(str, Enum):
    SCHUETTGUT = "Schüttgut"
    BETON = "Beton"
    ASPHALT = "Asphalt"
    STAHL = "Stahl"
    FERTIGTEIL = "Fertigteil"


class MaterialItem(BaseModel):
    id: str
    name: str
    unit: Unit
    category: MaterialCategory
    price_min: float
    price_max: float


class Supplier(BaseModel):
    id: str
    name: str
    street: str
    zip_code: str
    city: str
    phone: str
    email: str
    ust_id: str


class ConstructionCompany(BaseModel):
    id: str
    name: str
    street: str
    zip_code: str
    city: str
    phone: str
    email: str


class Baustelle(BaseModel):
    id: str
    name: str
    street: str
    zip_code: str
    city: str
    company_id: str


class MasterData(BaseModel):
    suppliers: list[Supplier]
    companies: list[ConstructionCompany]
    baustellen: list[Baustelle]
    materials: list[MaterialItem]


class Bestellposition(BaseModel):
    position_no: int
    material_id: str
    quantity: float
    unit: Unit
    unit_price: float


class Bestellung(BaseModel):
    id: str
    order_number: str
    date: date
    supplier_id: str
    company_id: str
    baustelle_id: str
    positions: list[Bestellposition]


class Lieferschein(BaseModel):
    id: str
    ls_number: str
    order_number_ref: str
    bestellung_id: str
    position_no: int
    date: date
    material_id: str
    quantity: float
    unit: Unit
    signed: bool
    driver_name: str
    vehicle_plate: str


class RechnungsPosition(BaseModel):
    position_no: int
    material_id: str
    quantity: float
    unit: Unit
    unit_price: float
    total: float


class Rechnung(BaseModel):
    id: str
    re_number: str
    order_number_ref: str
    bestellung_id: str
    date: date
    positions: list[RechnungsPosition]
    total_amount: float


class DiscrepancyType(str, Enum):
    QTY_MISMATCH = "QTY_MISMATCH"
    MISSING_SIGNATURE = "MISSING_SIGNATURE"
    WRONG_ORDER_REF = "WRONG_ORDER_REF"
    DUPLICATE_NOTE = "DUPLICATE_NOTE"
    UNIT_MISMATCH = "UNIT_MISMATCH"
    PRICE_DEVIATION = "PRICE_DEVIATION"


class Discrepancy(BaseModel):
    bestellung_id: str
    order_number: str
    type: DiscrepancyType
    document_type: str
    document_id: str
    field: str
    expected_value: str
    actual_value: str
    description: str


class OrderBundle(BaseModel):
    bestellung: Bestellung
    lieferscheine: list[Lieferschein]
    rechnung: Rechnung


class Dataset(BaseModel):
    master_data: MasterData
    orders: list[OrderBundle]
    discrepancies: list[Discrepancy]
