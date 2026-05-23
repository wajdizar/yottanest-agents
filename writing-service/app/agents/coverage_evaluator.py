"""Coverage Evaluator agent for assessing evidence coverage."""

import json
from datetime import date
from typing import Any

from pydantic import BaseModel, Field

from app.agents.base import BaseAgent, AgentError
from app.harness.openrouter_provider import ModelWeight
from app.logging import get_logger
from app.schemas.structure import FrozenStructure
from app.schemas.retrieval import QueryResults, Gap
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


logger = get_logger("coverage_evaluator")


class SharedEvidenceAssessment(BaseModel):
    """LLM output for shared evidence assessment."""

    evidence_id: str
    section_ids: list[str]
    canonical_interpretation: str


class RequirementCoverage(BaseModel):
    """LLM output for requirement coverage assessment."""

    requirement: str
    status: str = Field(description="One of: satisfied, partial, missing")
    evidence_ids: list[str] = Field(default_factory=list)
    missing_aspects: list[str] = Field(default_factory=list)


class CoverageAssessment(BaseModel):
    """LLM output for full coverage assessment."""

    section_id: str
    requirement_coverages: list[RequirementCoverage]
    shared_evidence: list[SharedEvidenceAssessment] = Field(default_factory=list)


class FullCoverageAssessment(BaseModel):
    """Complete coverage assessment output."""

    section_assessments: list[CoverageAssessment]
    overall_status: str = Field(description="One of: complete, needs_followup")


COVERAGE_EVALUATOR_PROMPT = """You are a coverage evaluation specialist. Assess how well the retrieved evidence covers the report requirements.

## Report Structure

```json
{structure_json}
```

## Evidence Pool

```json
{evidence_json}
```

## Section Bundles (Evidence Assignments)

```json
{bundles_json}
```

## Your Task

For each section, evaluate coverage of each requirement:

1. **Satisfied**: Evidence fully addresses the requirement
2. **Partial**: Evidence partially addresses it - note what's missing
3. **Missing**: No relevant evidence found

Also identify shared evidence (used in 2+ sections) and provide canonical interpretations.

## Output

Provide a FullCoverageAssessment with:
- section_assessments: Assessment per section
- overall_status: "complete" if all requirements satisfied, "needs_followup" otherwise"""


class CoverageEvaluatorAgent(BaseAgent[FullCoverageAssessment]):
    """
    Hybrid agent that evaluates evidence coverage.

    Uses Python for deduplication and bundle assignment.
    Uses LLM for judgment on coverage quality and interpretations.
    """

    agent_name = "coverage_evaluator"
    model_weight: ModelWeight = "heavy"
    output_schema = FullCoverageAssessment

    def build_prompt(self, **kwargs: Any) -> str:
        """Build the coverage evaluator prompt."""
        structure: FrozenStructure = kwargs["structure"]
        evidence_pool: list[EvidenceItem] = kwargs["evidence_pool"]
        bundles: list[SectionBundle] = kwargs["bundles"]

        structure_json = json.dumps(
            {
                "sections": [
                    {
                        "section_id": s.section_id,
                        "title": s.title,
                        "requirements": s.requirements,
                        "must_include": s.must_include,
                    }
                    for s in structure.sections
                ]
            },
            indent=2,
        )

        evidence_json = json.dumps(
            [
                {
                    "evidence_id": e.evidence_id,
                    "content": e.content[:500] + "..."
                    if len(e.content) > 500
                    else e.content,
                    "title": e.title,
                    "doc_type": e.doc_type,
                }
                for e in evidence_pool
            ],
            indent=2,
        )

        bundles_json = json.dumps(
            [{"section_id": b.section_id, "evidence_ids": b.evidence_ids} for b in bundles],
            indent=2,
        )

        return COVERAGE_EVALUATOR_PROMPT.format(
            structure_json=structure_json,
            evidence_json=evidence_json,
            bundles_json=bundles_json,
        )


def deduplicate_results(
    query_results: list[QueryResults],
) -> tuple[list[EvidenceItem], dict[str, list[str]]]:
    """
    Deduplicate query results and convert to evidence items.

    Returns:
        Tuple of (evidence_pool, doc_id_to_query_ids mapping)
    """
    seen_doc_ids: set[str] = set()
    evidence_pool: list[EvidenceItem] = []
    doc_id_to_query_ids: dict[str, list[str]] = {}
    doc_id_to_evidence_id: dict[str, str] = {}

    evidence_counter = 1

    for qr in query_results:
        for result in qr.results:
            if result.doc_id not in seen_doc_ids:
                # New document
                seen_doc_ids.add(result.doc_id)
                evidence_id = f"ev_{evidence_counter:03d}"
                evidence_counter += 1

                doc_id_to_evidence_id[result.doc_id] = evidence_id
                doc_id_to_query_ids[result.doc_id] = [qr.query_id]

                evidence_pool.append(
                    EvidenceItem(
                        evidence_id=evidence_id,
                        content=result.snippet,
                        source=EvidenceSource(
                            system=result.source,
                            doc_id=result.doc_id,
                            url=result.url,
                        ),
                        provenance=EvidenceProvenance(
                            query_ids=[qr.query_id],
                            retrieval_date=date.today().isoformat(),
                            relevance_scores={qr.query_id: result.relevance_score},
                        ),
                        doc_type=result.doc_type,
                        date=result.date,
                        title=result.title,
                        confidence=result.relevance_score,
                    )
                )
            else:
                # Existing document - update provenance
                doc_id_to_query_ids[result.doc_id].append(qr.query_id)
                evidence_id = doc_id_to_evidence_id[result.doc_id]

                # Find and update the evidence item
                for item in evidence_pool:
                    if item.evidence_id == evidence_id:
                        if qr.query_id not in item.provenance.query_ids:
                            item.provenance.query_ids.append(qr.query_id)
                        item.provenance.relevance_scores[qr.query_id] = (
                            result.relevance_score
                        )
                        break

    return evidence_pool, doc_id_to_query_ids


def assign_bundles(
    evidence_pool: list[EvidenceItem],
    query_results: list[QueryResults],
    query_to_sections: dict[str, list[str]],
) -> list[SectionBundle]:
    """
    Assign evidence to section bundles based on query assignments.
    """
    section_evidence: dict[str, set[str]] = {}

    # Map evidence to sections via queries
    for item in evidence_pool:
        for query_id in item.provenance.query_ids:
            if query_id in query_to_sections:
                for section_id in query_to_sections[query_id]:
                    if section_id not in section_evidence:
                        section_evidence[section_id] = set()
                    section_evidence[section_id].add(item.evidence_id)

    return [
        SectionBundle(
            section_id=section_id,
            evidence_ids=list(evidence_ids),
            requirement_coverage={},  # Filled by LLM evaluation
        )
        for section_id, evidence_ids in section_evidence.items()
    ]


def build_shared_registry(
    evidence_pool: list[EvidenceItem],
    bundles: list[SectionBundle],
    assessment: FullCoverageAssessment,
) -> list[SharedEvidence]:
    """Build shared evidence registry from LLM assessment."""
    shared_registry: list[SharedEvidence] = []

    # First find evidence in multiple bundles
    evidence_to_sections: dict[str, set[str]] = {}
    for bundle in bundles:
        for eid in bundle.evidence_ids:
            if eid not in evidence_to_sections:
                evidence_to_sections[eid] = set()
            evidence_to_sections[eid].add(bundle.section_id)

    # Use LLM interpretations where available
    llm_interpretations: dict[str, str] = {}
    for section_assessment in assessment.section_assessments:
        for shared in section_assessment.shared_evidence:
            llm_interpretations[shared.evidence_id] = shared.canonical_interpretation

    for eid, sections in evidence_to_sections.items():
        if len(sections) >= 2:
            shared_registry.append(
                SharedEvidence(
                    evidence_id=eid,
                    section_ids=list(sections),
                    canonical_interpretation=llm_interpretations.get(
                        eid, "Evidence used across multiple sections."
                    ),
                )
            )

    return shared_registry


def build_gap_reports(
    structure: FrozenStructure,
    assessment: FullCoverageAssessment,
) -> list[GapReport]:
    """Build gap reports from LLM assessment."""
    gap_reports: list[GapReport] = []

    for section_assessment in assessment.section_assessments:
        satisfied: list[str] = []
        partial: list[PartialCoverage] = []
        missing: list[str] = []

        for req_cov in section_assessment.requirement_coverages:
            if req_cov.status == "satisfied":
                satisfied.append(req_cov.requirement)
            elif req_cov.status == "partial":
                partial.append(
                    PartialCoverage(
                        requirement=req_cov.requirement,
                        coverage_level="partial",
                        available_evidence_ids=req_cov.evidence_ids,
                        missing_aspects=req_cov.missing_aspects,
                    )
                )
            else:  # missing
                missing.append(req_cov.requirement)

        gap_reports.append(
            GapReport(
                section_id=section_assessment.section_id,
                satisfied_requirements=satisfied,
                partial_coverage=partial,
                missing_requirements=missing,
            )
        )

    return gap_reports


def build_gaps_for_followup(gap_reports: list[GapReport]) -> list[Gap]:
    """Extract gaps that need follow-up queries."""
    gaps: list[Gap] = []

    for report in gap_reports:
        for missing in report.missing_requirements:
            gaps.append(
                Gap(
                    section_id=report.section_id,
                    requirement=missing,
                    gap_type="missing",
                )
            )
        for partial in report.partial_coverage:
            gaps.append(
                Gap(
                    section_id=report.section_id,
                    requirement=partial.requirement,
                    gap_type="partial",
                )
            )

    return gaps


class CoverageEvaluator:
    """
    Hybrid coverage evaluator combining Python logic and LLM judgment.
    """

    def __init__(self):
        self._agent = CoverageEvaluatorAgent()

    def evaluate(
        self,
        structure: FrozenStructure,
        query_results: list[QueryResults],
        query_to_sections: dict[str, list[str]],
        iteration: int = 1,
        max_iterations: int = 3,
    ) -> EvidencePackage:
        """
        Evaluate coverage and build evidence package.

        Args:
            structure: Report structure
            query_results: Results from queries
            query_to_sections: Mapping of query_id to section_ids
            iteration: Current iteration number
            max_iterations: Maximum allowed iterations

        Returns:
            Complete evidence package
        """
        # Step 1: Deduplicate results (Python)
        evidence_pool, doc_id_to_query_ids = deduplicate_results(query_results)
        logger.info(
            "deduplication_complete",
            total_results=sum(len(qr.results) for qr in query_results),
            unique_evidence=len(evidence_pool),
        )

        # Step 2: Assign bundles (Python)
        bundles = assign_bundles(evidence_pool, query_results, query_to_sections)
        logger.info(
            "bundle_assignment_complete",
            bundle_count=len(bundles),
        )

        # Step 3: LLM evaluation
        assessment = self._agent.invoke(
            structure=structure,
            evidence_pool=evidence_pool,
            bundles=bundles,
        )

        # Step 4: Build shared registry
        shared_registry = build_shared_registry(evidence_pool, bundles, assessment)
        logger.info(
            "shared_registry_built",
            shared_evidence_count=len(shared_registry),
        )

        # Step 5: Build gap reports
        gap_reports = build_gap_reports(structure, assessment)

        # Step 6: Determine if follow-up needed
        needs_followup = (
            assessment.overall_status == "needs_followup"
            and iteration < max_iterations
        )

        return EvidencePackage(
            evidence_pool=evidence_pool,
            section_bundles=bundles,
            shared_registry=shared_registry,
            gap_reports=gap_reports,
            retrieval_iterations=iteration,
            needs_followup=needs_followup,
        )


# Module-level singleton
_coverage_evaluator: CoverageEvaluator | None = None


def get_coverage_evaluator() -> CoverageEvaluator:
    """Get the coverage evaluator singleton."""
    global _coverage_evaluator
    if _coverage_evaluator is None:
        _coverage_evaluator = CoverageEvaluator()
    return _coverage_evaluator
