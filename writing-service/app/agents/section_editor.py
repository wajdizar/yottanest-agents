"""Section Editor agent for refining section prose."""

from typing import Any

from app.agents.base import BaseAgent
from app.harness.openrouter_provider import ModelWeight
from app.schemas.draft import SectionDraft


SECTION_EDITOR_PROMPT = """You are a professional editor for compliance reports. Your task is to refine the prose of a section while preserving its factual content.

## Section to Edit

**Section ID**: {section_id}
**Title**: {title}
**Target Word Count**: {target_words} words

**Current Content**:
```
{content}
```

**Current Claims** (DO NOT MODIFY):
{claims}

## Editing Guidelines

1. **Preserve Facts**: Do NOT change, add, or remove any factual claims
2. **Improve Flow**: Enhance transitions between paragraphs
3. **Clarity**: Simplify complex sentences while maintaining precision
4. **Tone**: Ensure consistent formal/professional tone
5. **Redundancy**: Remove unnecessary repetition
6. **Grammar**: Fix any grammatical issues
7. **Word Count**: Keep within ±20% of target ({min_words}-{max_words} words)

## Important Constraints

- The claims list must remain EXACTLY the same
- Do not add new information not in the original
- Do not remove any required information
- Maintain all evidence references

## Output

Provide a SectionDraft with:
- metadata: Same section_id, title, updated word_count, same target_words
- content: Edited prose
- claims: UNCHANGED from input
- checker_status: "pending"
- checker_notes: Empty list"""


class SectionEditorAgent(BaseAgent[SectionDraft]):
    """
    Agent that edits section prose for clarity and flow.

    Uses light model for efficiency.
    Does NOT modify claims or factual content.
    """

    agent_name = "section_editor"
    model_weight: ModelWeight = "light"
    output_schema = SectionDraft

    def build_prompt(self, **kwargs: Any) -> str:
        """Build the section editor prompt."""
        draft: SectionDraft = kwargs["draft"]

        # Format claims
        claims_text = "\n".join(
            f"- [{c.claim_id}] {c.statement} (evidence: {', '.join(c.evidence_ids)})"
            for c in draft.claims
        )

        # Calculate word count bounds
        target = draft.metadata.target_words
        min_words = int(target * 0.8)
        max_words = int(target * 1.2)

        return SECTION_EDITOR_PROMPT.format(
            section_id=draft.metadata.section_id,
            title=draft.metadata.title,
            target_words=target,
            content=draft.content,
            claims=claims_text,
            min_words=min_words,
            max_words=max_words,
        )


# Module-level singleton
_section_editor: SectionEditorAgent | None = None


def get_section_editor() -> SectionEditorAgent:
    """Get the section editor agent singleton."""
    global _section_editor
    if _section_editor is None:
        _section_editor = SectionEditorAgent()
    return _section_editor
