"""Schemas for feedback."""

from pydantic import BaseModel, Field


class Feedback(BaseModel):
    """Feedback for revision."""

    section_id: str = Field(
        description="Section ID this feedback is for"
    )
    feedback_type: str = Field(
        description="Type: 'content' | 'style' | 'factual' | 'structural'"
    )
    instructions: str = Field(
        description="Specific instructions for revision"
    )
    augmented_evidence: bool = Field(
        default=False,
        description="Whether new evidence was added",
    )
    new_evidence_ids: list[str] = Field(
        default_factory=list,
        description="IDs of newly added evidence",
    )
    priority: int = Field(
        default=3,
        description="Priority level (1=highest)",
        ge=1,
        le=5,
    )
