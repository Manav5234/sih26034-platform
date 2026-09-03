from __future__ import annotations

from datetime import date, datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel

from app.schemas.evidence import Evidence
from app.schemas.declaration import Declaration


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
    manufacture: Optional[date] = None
    best_before: Optional[date] = None
    use_by: Optional[date] = None


class CanonicalProduct(BaseModel):
    id: UUID
    identity: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    manufacturer: Optional[str] = None
    packer: Optional[str] = None
    importer: Optional[str] = None
    country_of_origin: Optional[str] = None
    quantity: Optional[Quantity] = None
    mrp: Optional[MRP] = None
    dates: Dates
    consumer_care: Optional[str] = None
    unit_sale_price: Optional[UnitSalePrice] = None
    barcode: Optional[Barcode] = None
    declarations: List[Declaration]
    evidence: List[Evidence]
    created_at: datetime
    updated_at: datetime
