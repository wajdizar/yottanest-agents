"""Pydantic schemas for the Writing Service."""

from app.schemas.structure import (
    FrozenStructure,
    SectionSpec,
    ReportMetadata,
)
from app.schemas.retrieval import (
    Query,
    QueryPlan,
    QueryResults,
    QueryResultItem,
    PreviousIteration,
    PreviousResultsSummary,
    Gap,
)
from app.schemas.evidence import (
    EvidenceItem,
    EvidenceSource,
    EvidenceProvenance,
    SectionBundle,
    SharedEvidence,
    PartialCoverage,
    GapReport,
    EvidencePackage,
)
from app.schemas.draft import (
    Claim,
    SectionMetadata,
    SectionDraft,
    Transition,
    Citation,
    CoherenceNote,
    AssembledDraft,
)
from app.schemas.feedback import Feedback
from app.schemas.consistency import ConsistencyFlag
from app.schemas.errors import ErrorPayload

__all__ = [
    # Structure
    "FrozenStructure",
    "SectionSpec",
    "ReportMetadata",
    # Retrieval
    "Query",
    "QueryPlan",
    "QueryResults",
    "QueryResultItem",
    "PreviousIteration",
    "PreviousResultsSummary",
    "Gap",
    # Evidence
    "EvidenceItem",
    "EvidenceSource",
    "EvidenceProvenance",
    "SectionBundle",
    "SharedEvidence",
    "PartialCoverage",
    "GapReport",
    "EvidencePackage",
    # Draft
    "Claim",
    "SectionMetadata",
    "SectionDraft",
    "Transition",
    "Citation",
    "CoherenceNote",
    "AssembledDraft",
    # Feedback
    "Feedback",
    # Consistency
    "ConsistencyFlag",
    # Errors
    "ErrorPayload",
]
