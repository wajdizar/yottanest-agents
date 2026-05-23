"""Consistency Checker agent for validating cross-section consistency."""

from typing import Any

from pydantic import BaseModel, Field

from app.agents.base import BaseAgent
from app.harness.openrouter_provider import ModelWeight
from app.schemas.draft import AssembledDraft
from app.schemas.evidence import EvidencePackage
from app.schemas.consistency import ConsistencyFlag


class ConsistencyCheckResult(BaseModel):
    """Output schema for consistency checker."""

    flags: list[ConsistencyFlag] = Field(
        default_factory=list,
        description="List of consistency issues found"
    )
    summary: str = Field(
        description="Brief summary of consistency check results"
    )


CONSISTENCY_CHECKER_PROMPT = """You are a consistency auditor for compliance reports. Your task is to identify inconsistencies across sections.

## Assembled Draft

{draft_content}

## Evidence Pool

{evidence_content}

## Consistency Checks

Examine the draft for these issues:

### 1. Numeric Conflicts
- Same metric with different values across sections
- Dates that don't align
- Percentages that don't sum correctly

### 2. Unsourced Claims
- Factual statements without evidence_id references
- Claims that reference non-existent evidence

### 3. Framing Conflicts
- Same entity described with contradictory characterizations
- Conflicting risk assessments
- Inconsistent conclusions

### 4. Terminology Inconsistencies
- Same concept with different names
- Acronyms used inconsistently
- Definitions that conflict

### 5. Date Conflicts
- Timeline inconsistencies
- Events in wrong order

### 6. Entity Mismatches
- Names spelled differently
- Wrong entity attributes

### 7. Logical Contradictions
- Conclusions that conflict with evidence
- Statements that contradict each other

## Output

Provide a ConsistencyCheckResult with:
- flags: List of ConsistencyFlag for each issue found
  - flag_id: Unique ID (f_001, f_002, etc.)
  - flag_type: One of the types above
  - severity: error | warning | info
  - sections_involved: Which sections have the issue
  - description: Clear description of the issue
  - evidence: Specific text showing the problem
  - suggested_resolution: How to fix it
  - claim_ids: Related claim IDs if applicable

- summary: Brief overall assessment

If no issues found, return empty flags list with summary indicating clean check."""


class ConsistencyCheckerAgent(BaseAgent[ConsistencyCheckResult]):
    """
    Agent that checks consistency across assembled draft.

    Uses heavyweight model for thorough analysis.
    """

    agent_name = "consistency_checker"
    model_weight: ModelWeight = "heavy"
    output_schema = ConsistencyCheckResult

    def build_prompt(self, **kwargs: Any) -> str:
        """Build the consistency checker prompt."""
        draft: AssembledDraft = kwargs["draft"]
        evidence_package: EvidencePackage = kwargs["evidence_package"]

        # Format draft content
        draft_sections = []
        for section in draft.sections:
            claims_text = "\n".join(
                f"    [{c.claim_id}] {c.statement} → evidence: {c.evidence_ids}"
                for c in section.claims
            )
            draft_sections.append(
                f"## {section.metadata.section_id}: {section.metadata.title}\n\n"
                f"{section.content}\n\n"
                f"**Claims**:\n{claims_text}"
            )
        draft_content = "\n\n---\n\n".join(draft_sections)

        # Format evidence
        evidence_items = []
        for e in evidence_package.evidence_pool:
            evidence_items.append(
                f"[{e.evidence_id}] {e.title or 'Untitled'}\n"
                f"Content: {e.content[:300]}..."
                if len(e.content) > 300
                else f"[{e.evidence_id}] {e.title or 'Untitled'}\n"
                f"Content: {e.content}"
            )
        evidence_content = "\n\n".join(evidence_items)

        return CONSISTENCY_CHECKER_PROMPT.format(
            draft_content=draft_content,
            evidence_content=evidence_content,
        )


# Module-level singleton
_consistency_checker: ConsistencyCheckerAgent | None = None


def get_consistency_checker() -> ConsistencyCheckerAgent:
    """Get the consistency checker agent singleton."""
    global _consistency_checker
    if _consistency_checker is None:
        _consistency_checker = ConsistencyCheckerAgent()
    return _consistency_checker
