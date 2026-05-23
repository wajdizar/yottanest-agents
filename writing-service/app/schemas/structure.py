"""Schemas for report structure."""

from typing import Literal

from pydantic import BaseModel, Field


ReportType = Literal[
    "compliance_profile",
    "risk_assessment",
    "due_diligence",
    "investigation_report",
    "monitoring_alert",
    "transaction_analysis",
    "entity_profile",
    "network_analysis",
]


class SectionSpec(BaseModel):
    """Specification for a single section in the report structure."""

    section_id: str = Field(
        description="Unique identifier for this section (e.g., 'sec_01')"
    )
    title: str = Field(description="Display title for the section")
    purpose: str = Field(description="What this section aims to accomplish")
    requirements: list[str] = Field(
        description="Specific requirements that must be addressed",
        default_factory=list,
    )
    must_include: list[str] = Field(
        description="Mandatory elements to include",
        default_factory=list,
    )
    target_words: int = Field(
        description="Target word count for this section",
        ge=50,
        le=5000,
    )
    depends_on: list[str] = Field(
        description="Section IDs that must be written before this one",
        default_factory=list,
    )
    evidence_types: list[str] = Field(
        description="Types of evidence relevant to this section",
        default_factory=list,
    )


class ReportMetadata(BaseModel):
    """Metadata about the report being generated."""

    report_type: ReportType = Field(
        description="Type of report being generated"
    )
    subject_name: str = Field(
        description="Name of the subject entity"
    )
    subject_type: str = Field(
        description="Type of subject (e.g., 'company', 'individual', 'transaction')"
    )
    jurisdiction: str | None = Field(
        default=None,
        description="Primary jurisdiction for regulatory context",
    )
    purpose: str = Field(
        description="Overall purpose of this report"
    )
    audience: str = Field(
        description="Intended audience for the report",
        default="compliance team",
    )
    tone: str = Field(
        description="Desired tone (e.g., 'formal', 'technical', 'executive-summary')",
        default="formal",
    )
    date_generated: str | None = Field(
        default=None,
        description="ISO date when report was generated",
    )


class FrozenStructure(BaseModel):
    """
    Complete frozen structure for a report.

    Once generated, this structure is immutable and drives all subsequent
    phases of the writing pipeline.
    """

    metadata: ReportMetadata = Field(
        description="Report metadata"
    )
    sections: list[SectionSpec] = Field(
        description="Ordered list of sections to generate",
        min_length=1,
    )
    global_instructions: str | None = Field(
        default=None,
        description="Instructions that apply across all sections",
    )
    terminology: dict[str, str] = Field(
        default_factory=dict,
        description="Term definitions for consistent usage across sections",
    )

    def get_section(self, section_id: str) -> SectionSpec | None:
        """Get a section by its ID."""
        for section in self.sections:
            if section.section_id == section_id:
                return section
        return None

    def get_dependency_order(self) -> list[list[str]]:
        """
        Get sections grouped by dependency order.

        Returns a list of lists, where each inner list contains section IDs
        that can be processed in parallel (no dependencies on each other).
        """
        processed: set[str] = set()
        result: list[list[str]] = []
        remaining = {s.section_id for s in self.sections}

        while remaining:
            # Find sections whose dependencies are all processed
            ready = []
            for section in self.sections:
                if section.section_id in remaining:
                    deps = set(section.depends_on)
                    if deps.issubset(processed):
                        ready.append(section.section_id)

            if not ready:
                # Circular dependency or invalid depends_on references
                # Include remaining sections to avoid infinite loop
                ready = list(remaining)

            result.append(ready)
            for sid in ready:
                processed.add(sid)
                remaining.discard(sid)

        return result
