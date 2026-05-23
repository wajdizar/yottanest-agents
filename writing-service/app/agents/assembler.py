"""Assembler agent for combining sections into final draft."""

import json
from typing import Any

from app.agents.base import BaseAgent
from app.harness.openrouter_provider import ModelWeight
from app.schemas.structure import FrozenStructure
from app.schemas.evidence import EvidenceItem
from app.schemas.draft import SectionDraft, AssembledDraft


ASSEMBLER_PROMPT = """You are a report assembly specialist. Your task is to combine individual sections into a cohesive final document.

## Report Structure

**Report Type**: {report_type}
**Subject**: {subject_name}
**Sections in Order**: {section_order}

**Terminology Definitions**:
{terminology}

## Sections to Assemble

{sections_content}

## Evidence Pool Summary

{evidence_summary}

## Assembly Tasks

1. **Section Ordering**: Arrange sections in logical order per structure

2. **Transitions**: Write transition paragraphs between consecutive sections:
   - Bridge the ending of one section to the beginning of the next
   - Create narrative flow
   - Keep transitions concise (1-2 sentences)

3. **Citations**: Compile all evidence references:
   - Assign citation IDs [1], [2], etc.
   - Map evidence_id to citation_id
   - Format source text for each citation

4. **Coherence Check**: Identify any issues:
   - terminology_drift: Same concept described differently
   - inconsistency: Conflicting information
   - redundancy: Repeated information across sections

5. **Word Count**: Calculate total word count

## Output

Provide an AssembledDraft with:
- sections: List of SectionDraft (unchanged from input)
- transitions: Transition between each consecutive section pair
- citations: Complete citation list with formatted source_text
- coherence_notes: Any coherence issues identified
- total_word_count: Sum of all section word counts"""


class AssemblerAgent(BaseAgent[AssembledDraft]):
    """
    Agent that assembles sections into final draft.

    Uses heavyweight model for coherence analysis.
    """

    agent_name = "assembler"
    model_weight: ModelWeight = "heavy"
    output_schema = AssembledDraft

    def build_prompt(self, **kwargs: Any) -> str:
        """Build the assembler prompt."""
        sections: list[SectionDraft] = kwargs["sections"]
        structure: FrozenStructure = kwargs["structure"]
        evidence_pool: list[EvidenceItem] = kwargs["evidence_pool"]

        # Section order
        section_order = ", ".join(
            f"{s.section_id}: {s.title}" for s in structure.sections
        )

        # Terminology
        if structure.terminology:
            terminology = "\n".join(
                f"- **{term}**: {definition}"
                for term, definition in structure.terminology.items()
            )
        else:
            terminology = "(No terminology defined)"

        # Format sections content
        sections_content = []
        for draft in sections:
            claims_text = "\n".join(
                f"  - [{c.claim_id}] {c.statement} (evidence: {', '.join(c.evidence_ids)})"
                for c in draft.claims
            )
            sections_content.append(
                f"### {draft.metadata.section_id}: {draft.metadata.title}\n"
                f"**Word Count**: {draft.metadata.word_count}\n"
                f"**Checker Status**: {draft.checker_status}\n\n"
                f"**Content**:\n{draft.content}\n\n"
                f"**Claims**:\n{claims_text}"
            )
        sections_text = "\n\n---\n\n".join(sections_content)

        # Evidence summary
        evidence_summary = "\n".join(
            f"- [{e.evidence_id}] {e.title or 'Untitled'} ({e.source.system})"
            for e in evidence_pool
        )

        return ASSEMBLER_PROMPT.format(
            report_type=structure.metadata.report_type,
            subject_name=structure.metadata.subject_name,
            section_order=section_order,
            terminology=terminology,
            sections_content=sections_text,
            evidence_summary=evidence_summary,
        )


# Module-level singleton
_assembler: AssemblerAgent | None = None


def get_assembler() -> AssemblerAgent:
    """Get the assembler agent singleton."""
    global _assembler
    if _assembler is None:
        _assembler = AssemblerAgent()
    return _assembler
