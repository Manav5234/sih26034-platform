from __future__ import annotations

from pydantic import BaseModel


class BBox(BaseModel):
    x: float
    y: float
    width: float
    height: float
