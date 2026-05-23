"""Schemas for evidence packaging."""

from pydantic import BaseModel, Field


class EvidenceSource(BaseModel):
    """Source information for an evidence item."""

    system: str = Field(
        description="Source system name"
    )
    doc_id: str = Field(
        description="Document ID in source system"
    )
    url: str | None = Field(
        default=None,
        description="URL to source if available",
    )


class EvidenceProvenance(BaseModel):
    """Provenance information for evidence."""

    query_ids: list[str] = Field(
        description="Query IDs that retrieved this evidence"
    )
    retrieval_date: str = Field(
        description="ISO date when evidence was retrieved"
    )
    relevance_scores: dict[str, float] = Field(
        default_factory=dict,
        description="Relevance score per query ID",
    )


class EvidenceItem(BaseModel):
    """A single piece of evidence."""

    evidence_id: str = Field(
        description="Unique identifier for this evidence item"
    )
    content: str = Field(
        description="The actual content/excerpt"
    )
    source: EvidenceSource = Field(
        description="Source information"
    )
    provenance: EvidenceProvenance = Field(
        description="How this evidence was obtained"
    )
    doc_type: str | None = Field(
        default=None,
        description="Type of document",
    )
    date: str | None = Field(
        default=None,
        description="Date of the document/evidence",
    )
    title: str | None = Field(
        default=None,
        description="Title of the source document",
    )
    confidence: float = Field(
        default=1.0,
        description="Confidence in this evidence",
        ge=0.0,
        le=1.0,
    )


class SharedEvidence(BaseModel):
    """Evidence that is shared across multiple sections."""

    evidence_id: str = Field(
        description="ID of the shared evidence item"
    )
    section_ids: list[str] = Field(
        description="Sections that use this evidence"
    )
    canonical_interpretation: str = Field(
        description="Agreed interpretation across sections"
    )


class SectionBundle(BaseModel):
    """Evidence bundle for a specific section."""

    section_id: str = Field(
        description="The section this bundle is for"
    )
    evidence_ids: list[str] = Field(
        description="IDs of evidence items in this bundle"
    )
    requirement_coverage: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Mapping of requirement -> evidence_ids that address it",
    )


class PartialCoverage(BaseModel):
    """Description of partial coverage for a requirement."""

    requirement: str = Field(
        description="The requirement"
    )
    coverage_level: str = Field(
        description="Level of coverage: 'partial' | 'weak'"
    )
    available_evidence_ids: list[str] = Field(
        description="Evidence IDs that partially cover this"
    )
    missing_aspects: list[str] = Field(
        description="What aspects are not covered"
    )


class GapReport(BaseModel):
    """Report of coverage gaps for a section."""

    section_id: str = Field(
        description="Section ID"
    )
    satisfied_requirements: list[str] = Field(
        description="Requirements fully satisfied"
    )
    partial_coverage: list[PartialCoverage] = Field(
        description="Requirements with partial coverage"
    )
    missing_requirements: list[str] = Field(
        description="Requirements with no coverage"
    )

    @property
    def is_complete(self) -> bool:
        """Check if all requirements are satisfied."""
        return (
            len(self.partial_coverage) == 0 and len(self.missing_requirements) == 0
        )


class EvidencePackage(BaseModel):
    """Complete evidence package for the writing phase."""

    evidence_pool: list[EvidenceItem] = Field(
        description="All evidence items"
    )
    section_bundles: list[SectionBundle] = Field(
        description="Per-section evidence assignments"
    )
    shared_registry: list[SharedEvidence] = Field(
        default_factory=list,
        description="Evidence shared across sections",
    )
    gap_reports: list[GapReport] = Field(
        default_factory=list,
        description="Coverage gap reports per section",
    )
    retrieval_iterations: int = Field(
        default=1,
        description="Number of retrieval iterations performed",
    )
    needs_followup: bool = Field(
        default=False,
        description="Whether more retrieval is recommended",
    )

    def get_evidence(self, evidence_id: str) -> EvidenceItem | None:
        """Get an evidence item by ID."""
        for item in self.evidence_pool:
            if item.evidence_id == evidence_id:
                return item
        return None

    def get_section_bundle(self, section_id: str) -> SectionBundle | None:
        """Get the evidence bundle for a section."""
        for bundle in self.section_bundles:
            if bundle.section_id == section_id:
                return bundle
        return None

    def get_evidence_for_section(self, section_id: str) -> list[EvidenceItem]:
        """Get all evidence items for a section."""
        bundle = self.get_section_bundle(section_id)
        if not bundle:
            return []
        return [
            item
            for item in self.evidence_pool
            if item.evidence_id in bundle.evidence_ids
        ]
