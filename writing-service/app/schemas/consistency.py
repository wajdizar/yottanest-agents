"""Schemas for consistency checking."""

from typing import Literal

from pydantic import BaseModel, Field


FlagType = Literal[
    "numeric_conflict",
    "unsourced_claim",
    "framing_conflict",
    "terminology_inconsistency",
    "date_conflict",
    "entity_mismatch",
    "logical_contradiction",
]

FlagSeverity = Literal["error", "warning", "info"]


class ConsistencyFlag(BaseModel):
    """A flag raised by the consistency checker."""

    flag_id: str = Field(
        description="Unique identifier for this flag"
    )
    flag_type: FlagType = Field(
        description="Type of consistency issue"
    )
    severity: FlagSeverity = Field(
        description="Severity of the issue"
    )
    sections_involved: list[str] = Field(
        description="Section IDs where this issue appears"
    )
    description: str = Field(
        description="Human-readable description of the issue"
    )
    evidence: str | None = Field(
        default=None,
        description="Specific text or data showing the issue",
    )
    suggested_resolution: str | None = Field(
        default=None,
        description="Suggested fix for the issue",
    )
    claim_ids: list[str] = Field(
        default_factory=list,
        description="Claim IDs involved in this flag",
    )
