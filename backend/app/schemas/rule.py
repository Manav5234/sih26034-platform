from __future__ import annotations

from datetime import date
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel


class Rule(BaseModel):
    rule_id: str
    source_document: str
    clause: str
    applicability: str
    required_declaration: str
    validation_conditions: Any
    measurement_requirements: Optional[Any] = None
    exceptions: List[str]
    effective_date: date
    evidence_requirements: List[str]


class RuleSet(BaseModel):
    id: UUID
    source: str
    rule_version: str
    effective_from: date
    effective_to: Optional[date] = None
    jurisdiction: str
    rules: List[Rule]
