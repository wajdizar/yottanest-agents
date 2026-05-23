"""Section Writer agent for drafting report sections."""

import json
from typing import Any

from app.agents.base import BaseAgent
from app.harness.openrouter_provider import ModelWeight
from app.schemas.structure import SectionSpec, ReportMetadata
from app.schemas.evidence import EvidenceItem, SharedEvidence
from app.schemas.draft import SectionDraft
from app.schemas.feedback import Feedback


SECTION_WRITER_PROMPT = """You are a compliance report writer. Your task is to write a section of a compliance report.

## Report Context

**Report Type**: {report_type}
**Subject**: {subject_name} ({subject_type})
**Audience**: {audience}
**Tone**: {tone}

{global_instructions}

## Section to Write

**Section ID**: {section_id}
**Title**: {title}
**Purpose**: {purpose}

**Requirements** (must be addressed):
{requirements}

**Must Include** (mandatory elements):
{must_include}

**Target Word Count**: {target_words} words (±20% acceptable)

## Available Evidence

{evidence_section}

## Shared Evidence Context

{shared_evidence_section}

{revision_section}

## Writing Guidelines

1. **Evidence-Based**: Every factual claim must cite evidence from the bundle
2. **Claims**: Identify 3-6 key claims, each with evidence_ids
3. **Structure**: Use clear paragraphs with logical flow
4. **Tone**: Match the specified tone (formal/technical/executive)
5. **Word Count**: Stay within ±20% of target
6. **Completeness**: Address all requirements and must_include items

## Output

Provide a SectionDraft with:
- metadata: section_id, title, word_count, target_words
- content: The prose content
- claims: List of claims with evidence_ids
- checker_status: "pending" (will be updated by checker)
{changelog_instruction}"""


class SectionWriterAgent(BaseAgent[SectionDraft]):
    """
    Agent that writes report sections.

    Uses standard model for quality writing.
    Supports both write mode (fresh) and revise mode (with feedback).
    """

    agent_name = "section_writer"
    model_weight: ModelWeight = "standard"
    output_schema = SectionDraft

    def build_prompt(self, **kwargs: Any) -> str:
        """Build the section writer prompt."""
        section: SectionSpec = kwargs["section"]
        evidence: list[EvidenceItem] = kwargs["evidence"]
        metadata: ReportMetadata = kwargs["metadata"]
        shared_evidence: list[SharedEvidence] = kwargs.get("shared_evidence", [])
        original_draft: SectionDraft | None = kwargs.get("original_draft")
        feedback: Feedback | None = kwargs.get("feedback")
        global_instructions: str | None = kwargs.get("global_instructions")

        # Format requirements
        requirements = "\n".join(f"- {req}" for req in section.requirements)
        must_include = "\n".join(f"- {item}" for item in section.must_include)

        # Format evidence
        evidence_items = []
        for e in evidence:
            evidence_items.append(
                f"[{e.evidence_id}] {e.title or 'Untitled'}\n"
                f"Source: {e.source.system}\n"
                f"Content: {e.content}"
            )
        evidence_section = "\n\n---\n\n".join(evidence_items) if evidence_items else "(No evidence available)"

        # Format shared evidence
        if shared_evidence:
            shared_items = []
            for se in shared_evidence:
                shared_items.append(
                    f"[{se.evidence_id}] Used in sections: {', '.join(se.section_ids)}\n"
                    f"Interpretation: {se.canonical_interpretation}"
                )
            shared_evidence_section = "\n\n".join(shared_items)
        else:
            shared_evidence_section = "(No shared evidence for this section)"

        # Revision mode
        if original_draft and feedback:
            revision_section = f"""## Revision Instructions

**Original Draft**:
```
{original_draft.content}
```

**Feedback Type**: {feedback.feedback_type}
**Instructions**: {feedback.instructions}

{"**New Evidence Added**: " + ", ".join(feedback.new_evidence_ids) if feedback.augmented_evidence else ""}

Revise the section according to feedback. Document changes in changelog."""
            changelog_instruction = "- changelog: List of changes made during revision"
        else:
            revision_section = "(Write mode - create new section from scratch)"
            changelog_instruction = ""

        # Global instructions
        if global_instructions:
            global_instructions_section = f"**Global Instructions**: {global_instructions}"
        else:
            global_instructions_section = ""

        return SECTION_WRITER_PROMPT.format(
            report_type=metadata.report_type,
            subject_name=metadata.subject_name,
            subject_type=metadata.subject_type,
            audience=metadata.audience,
            tone=metadata.tone,
            global_instructions=global_instructions_section,
            section_id=section.section_id,
            title=section.title,
            purpose=section.purpose,
            requirements=requirements,
            must_include=must_include,
            target_words=section.target_words,
            evidence_section=evidence_section,
            shared_evidence_section=shared_evidence_section,
            revision_section=revision_section,
            changelog_instruction=changelog_instruction,
        )


# Module-level singleton
_section_writer: SectionWriterAgent | None = None


def get_section_writer() -> SectionWriterAgent:
    """Get the section writer agent singleton."""
    global _section_writer
    if _section_writer is None:
        _section_writer = SectionWriterAgent()
    return _section_writer
