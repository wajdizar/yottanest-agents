"""Schemas for draft content."""

from typing import Literal

from pydantic import BaseModel, Field


CheckerStatus = Literal["pass", "warning", "fail", "timeout", "pending"]


class Claim(BaseModel):
    """A factual claim made in the draft."""

    claim_id: str = Field(
        description="Unique identifier for this claim"
    )
    statement: str = Field(
        description="The claim statement"
    )
    evidence_ids: list[str] = Field(
        description="Evidence IDs supporting this claim"
    )
    confidence: float = Field(
        default=1.0,
        description="Confidence in this claim",
        ge=0.0,
        le=1.0,
    )


class SectionMetadata(BaseModel):
    """Metadata about a section draft."""

    section_id: str = Field(
        description="Section identifier"
    )
    title: str = Field(
        description="Section title"
    )
    word_count: int = Field(
        description="Word count of the section"
    )
    target_words: int = Field(
        description="Target word count"
    )
    retry_count: int = Field(
        default=0,
        description="Number of retries for this section",
    )


class SectionDraft(BaseModel):
    """Draft content for a single section."""

    metadata: SectionMetadata = Field(
        description="Section metadata"
    )
    content: str = Field(
        description="The prose content of the section"
    )
    claims: list[Claim] = Field(
        description="Factual claims made in this section",
        default_factory=list,
    )
    checker_status: CheckerStatus = Field(
        default="pending",
        description="Status from the section checker",
    )
    checker_notes: list[str] = Field(
        default_factory=list,
        description="Notes from the section checker",
    )
    changelog: list[str] = Field(
        default_factory=list,
        description="Changes made during revision",
    )

    @property
    def word_count_delta(self) -> int:
        """Difference between actual and target word count."""
        return self.metadata.word_count - self.metadata.target_words

    @property
    def word_count_within_tolerance(self) -> bool:
        """Check if word count is within ±20% of target."""
        tolerance = self.metadata.target_words * 0.2
        return abs(self.word_count_delta) <= tolerance


class Transition(BaseModel):
    """Transition text between sections."""

    from_section_id: str = Field(
        description="ID of the preceding section"
    )
    to_section_id: str = Field(
        description="ID of the following section"
    )
    transition_text: str = Field(
        description="The transition paragraph or sentence"
    )


class Citation(BaseModel):
    """A citation in the assembled draft."""

    citation_id: str = Field(
        description="Unique citation identifier (e.g., '[1]')"
    )
    evidence_id: str = Field(
        description="ID of the evidence being cited"
    )
    source_text: str = Field(
        description="Formatted citation text"
    )
    used_in_sections: list[str] = Field(
        description="Section IDs where this citation appears"
    )


class CoherenceNote(BaseModel):
    """Note about cross-section coherence."""

    note_type: str = Field(
        description="Type: 'terminology_drift' | 'inconsistency' | 'redundancy'"
    )
    sections_involved: list[str] = Field(
        description="Sections involved in this note"
    )
    description: str = Field(
        description="Description of the coherence issue or note"
    )
    severity: str = Field(
        default="info",
        description="Severity: 'info' | 'warning' | 'error'",
    )


class AssembledDraft(BaseModel):
    """Complete assembled draft with all sections."""

    sections: list[SectionDraft] = Field(
        description="All section drafts in order"
    )
    transitions: list[Transition] = Field(
        description="Transitions between sections",
        default_factory=list,
    )
    citations: list[Citation] = Field(
        description="Compiled citations",
        default_factory=list,
    )
    coherence_notes: list[CoherenceNote] = Field(
        description="Notes about cross-section coherence",
        default_factory=list,
    )
    total_word_count: int = Field(
        description="Total word count across all sections"
    )

    def get_section(self, section_id: str) -> SectionDraft | None:
        """Get a section draft by ID."""
        for section in self.sections:
            if section.metadata.section_id == section_id:
                return section
        return None

    @property
    def all_claims(self) -> list[Claim]:
        """Get all claims from all sections."""
        claims = []
        for section in self.sections:
            claims.extend(section.claims)
        return claims

    @property
    def has_failures(self) -> bool:
        """Check if any section has a failure status."""
        return any(s.checker_status == "fail" for s in self.sections)

    @property
    def has_timeouts(self) -> bool:
        """Check if any section has a timeout status."""
        return any(s.checker_status == "timeout" for s in self.sections)
