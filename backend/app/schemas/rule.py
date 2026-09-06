from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class Rule(BaseModel):
    rule_id: str
    source_document: str
    clause: str
    applicability: str
    required_declaration: str
    validation_conditions: Any
    measurement_requirements: Any | None = None
    exceptions: list[str]
    effective_date: date
    evidence_requirements: list[str]


class RuleSet(BaseModel):
    id: UUID
    source: str
    rule_version: str
    effective_from: date
    effective_to: date | None = None
    jurisdiction: str
    rules: list[Rule]
