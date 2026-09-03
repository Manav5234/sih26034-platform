from __future__ import annotations

from pydantic import BaseModel
from uuid import UUID


class BBox(BaseModel):
    x: float
    y: float
    width: float
    height: float
