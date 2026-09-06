from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel

from app.schemas.declaration import Declaration
from app.schemas.evidence import Evidence


class Quantity(BaseModel):
    value: float
    unit: str


class MRP(BaseModel):
    amount: float
    currency: str


class UnitSalePrice(BaseModel):
    amount: float
    currency: str


class Barcode(BaseModel):
    code: str
    format: str


class Dates(BaseModel):
    manufacture: date | None = None
    best_before: date | None = None
    use_by: date | None = None


class CanonicalProduct(BaseModel):
    id: UUID
    identity: str | None = None
    brand: str | None = None
    category: str | None = None
    manufacturer: str | None = None
    packer: str | None = None
    importer: str | None = None
    country_of_origin: str | None = None
    quantity: Quantity | None = None
    mrp: MRP | None = None
    dates: Dates
    consumer_care: str | None = None
    unit_sale_price: UnitSalePrice | None = None
    barcode: Barcode | None = None
    declarations: list[Declaration]
    evidence: list[Evidence]
    created_at: datetime
    updated_at: datetime
