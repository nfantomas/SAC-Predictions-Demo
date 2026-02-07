from __future__ import annotations

import re
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, ConfigDict, field_validator


_YYYY_MM_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


IntentType = Literal[
    "constraint",
    "shock",
    "policy",
    "target",
    "mix_shift",
    "productivity",
    "attrition",
    "relocation",
    "other",
]
Driver = Literal["auto", "cost", "fte", "cost_target"]
Direction = Literal["increase", "decrease", "hold", "unknown"]
MagnitudeType = Literal["pct", "abs", "yoy_cap", "none"]
Severity = Literal["operational", "stress", "crisis"]
Confidence = Literal["low", "medium", "high"]


class Magnitude(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: MagnitudeType = Field(..., description="Magnitude type (percent, absolute, YoY cap, or none).")
    value: Optional[float] = Field(None, description="Magnitude value; null when type is none.")


class Timing(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: str = Field(..., description="Start month in YYYY-MM format.")
    duration_months: Optional[int] = Field(
        None, description="Duration in months, or null for permanent."
    )
    ramp_months: int = Field(..., description="Ramp duration in months.")

    @field_validator("start")
    @classmethod
    def _validate_start(cls, value: str) -> str:
        if not _YYYY_MM_RE.match(value):
            raise ValueError("start must be in YYYY-MM format.")
        return value

    @field_validator("duration_months", "ramp_months")
    @classmethod
    def _validate_months(cls, value: Optional[int]) -> Optional[int]:
        if value is None:
            return value
        if value < 0:
            raise ValueError("months must be >= 0.")
        return value


class Entities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    regions: Optional[List[str]] = Field(None, description="Affected regions, if specified.")
    population: Optional[Literal["global"]] = Field(
        None, description="Population scope (global or null)."
    )


class ScenarioIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["intent_v1"] = Field(..., description="Schema version identifier.")
    intent_type: IntentType = Field(..., description="Top-level intent classification.")
    driver: Driver = Field(..., description="Driver hint for scenario application.")
    direction: Direction = Field(..., description="Direction of change.")
    magnitude: Magnitude = Field(..., description="Magnitude details.")
    timing: Timing = Field(..., description="Timing details.")
    constraints: List[str] = Field(default_factory=list, description="Constraints or policies.")
    entities: Entities = Field(..., description="Entities and scope.")
    severity: Severity = Field(..., description="Scenario severity tier.")
    confidence: Confidence = Field(..., description="Interpreter confidence.")
    need_clarification: bool = Field(..., description="Whether clarification is required.")
    clarifying_question: Optional[str] = Field(
        None, description="Single clarifying question when needed."
    )

    @field_validator("clarifying_question")
    @classmethod
    def _validate_question(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value.strip():
            raise ValueError("clarifying_question must be non-empty when provided.")
        return value


def intent_schema_json() -> dict:
    return ScenarioIntent.model_json_schema()
