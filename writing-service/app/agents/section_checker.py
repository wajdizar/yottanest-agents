"""Section Checker agent for validating section quality."""

from typing import Any

from app.agents.base import BaseAgent
from app.harness.openrouter_provider import ModelWeight
from app.schemas.structure import SectionSpec
from app.schemas.evidence import EvidenceItem
from app.schemas.draft import SectionDraft


SECTION_CHECKER_PROMPT = """You are a quality assurance specialist for compliance reports. Evaluate this section against requirements.

## Section Specification

**Section ID**: {section_id}
**Title**: {title}
**Purpose**: {purpose}

**Requirements**:
{requirements}

**Must Include**:
{must_include}

**Target Word Count**: {target_words} words (acceptable range: {min_words}-{max_words})

## Section Draft

**Actual Word Count**: {actual_word_count}

**Content**:
```
{content}
```

**Claims Made**:
{claims}

## Available Evidence IDs

{evidence_ids}

## Validation Checklist

Check each item and note any issues:

1. **Must Include Items**: Are all must_include elements present?
2. **Requirements Coverage**: Are all requirements addressed?
3. **Word Count**: Is it within ±20% of target?
4. **Claim Support**: Does every claim reference valid evidence IDs?
5. **Unsupported Claims**: Are there claims without evidence?
6. **Factual Accuracy**: Do claims match the evidence content?

## Status Determination

- **pass**: All checks pass, no significant issues
- **warning**: Minor issues (e.g., slightly outside word count, minor coverage gaps)
- **fail**: Major issues (missing must_include, unsupported claims, major requirements missed)

## Output

Provide a SectionDraft with:
- metadata: Same as input
- content: Same as input
- claims: Same as input
- checker_status: "pass" | "warning" | "fail"
- checker_notes: List of specific issues found (empty if pass)"""


class SectionCheckerAgent(BaseAgent[SectionDraft]):
    """
    Agent that validates section quality.

    Uses light model for efficiency.
    Returns status: pass | warning | fail.
    """

    agent_name = "section_checker"
    model_weight: ModelWeight = "light"
    output_schema = SectionDraft

    def build_prompt(self, **kwargs: Any) -> str:
        """Build the section checker prompt."""
        draft: SectionDraft = kwargs["draft"]
        section: SectionSpec = kwargs["section"]
        evidence: list[EvidenceItem] = kwargs["evidence"]

        # Format requirements
        requirements = "\n".join(f"- {req}" for req in section.requirements)
        must_include = "\n".join(f"- {item}" for item in section.must_include)

        # Format claims
        claims_text = "\n".join(
            f"- [{c.claim_id}] {c.statement} (evidence: {', '.join(c.evidence_ids)})"
            for c in draft.claims
        )

        # Evidence IDs
        evidence_ids = ", ".join(e.evidence_id for e in evidence)

        # Word count bounds
        target = section.target_words
        min_words = int(target * 0.8)
        max_words = int(target * 1.2)

        return SECTION_CHECKER_PROMPT.format(
            section_id=section.section_id,
            title=section.title,
            purpose=section.purpose,
            requirements=requirements,
            must_include=must_include,
            target_words=target,
            min_words=min_words,
            max_words=max_words,
            actual_word_count=draft.metadata.word_count,
            content=draft.content,
            claims=claims_text,
            evidence_ids=evidence_ids,
        )


# Module-level singleton
_section_checker: SectionCheckerAgent | None = None


def get_section_checker() -> SectionCheckerAgent:
    """Get the section checker agent singleton."""
    global _section_checker
    if _section_checker is None:
        _section_checker = SectionCheckerAgent()
    return _section_checker
