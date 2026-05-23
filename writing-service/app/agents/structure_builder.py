"""Structure Builder agent for generating report structure."""

from typing import Any

from app.agents.base import BaseAgent
from app.harness.openrouter_provider import ModelWeight
from app.schemas.structure import FrozenStructure


STRUCTURE_BUILDER_PROMPT = """You are a report structure architect. Your task is to design a comprehensive structure for a compliance/risk report.

## Input

**Goal**: {goal}

{input_spec_section}

## Your Task

Create a frozen structure that will guide the writing of this report. The structure must:

1. **Metadata**: Define report metadata including:
   - report_type: One of: compliance_profile, risk_assessment, due_diligence, investigation_report, monitoring_alert, transaction_analysis, entity_profile, network_analysis
   - subject_name: The entity being analyzed
   - subject_type: company, individual, transaction, etc.
   - jurisdiction: Primary regulatory jurisdiction if applicable
   - purpose: Clear statement of report purpose
   - audience: Who will read this report
   - tone: formal, technical, or executive-summary

2. **Sections**: Design 3-8 sections, each with:
   - section_id: Unique ID (e.g., sec_01, sec_02)
   - title: Clear, descriptive title
   - purpose: What this section accomplishes
   - requirements: Specific items that must be covered (3-6 per section)
   - must_include: Mandatory elements (1-3 per section)
   - target_words: Appropriate word count (typically 200-500 per section)
   - depends_on: List of section_ids that must be written first
   - evidence_types: Types of evidence relevant to this section

3. **Dependencies**: Set depends_on to create a logical flow. Earlier sections that establish context should be written before sections that synthesize or conclude.

4. **Global Instructions**: Add any cross-cutting instructions for writers.

5. **Terminology**: Define key terms that must be used consistently.

## Guidelines

- Structure should be logical and flow naturally
- Each section should have a clear, distinct purpose
- Requirements should be specific and verifiable
- Word counts should be realistic for the content required
- Dependencies should create parallelism where possible (sections without dependencies can be written simultaneously)

## Output

Provide the complete FrozenStructure with all required fields."""


class StructureBuilderAgent(BaseAgent[FrozenStructure]):
    """
    Agent that generates report structure from a goal.

    Uses heavyweight model for complex reasoning.
    """

    agent_name = "structure_builder"
    model_weight: ModelWeight = "heavy"
    output_schema = FrozenStructure

    def build_prompt(self, **kwargs: Any) -> str:
        """Build the structure builder prompt."""
        goal = kwargs.get("goal", "")
        input_spec = kwargs.get("input_spec")

        # Format input_spec section if provided
        if input_spec:
            input_spec_section = f"""**Partial Input Specification** (enrich and complete this):
```json
{input_spec}
```

Use this as a starting point but enhance it with:
- Missing sections if needed
- More specific requirements
- Appropriate dependencies
- Realistic word counts"""
        else:
            input_spec_section = "(No partial specification provided - create structure from scratch)"

        return STRUCTURE_BUILDER_PROMPT.format(
            goal=goal,
            input_spec_section=input_spec_section,
        )


# Module-level singleton
_structure_builder: StructureBuilderAgent | None = None


def get_structure_builder() -> StructureBuilderAgent:
    """Get the structure builder agent singleton."""
    global _structure_builder
    if _structure_builder is None:
        _structure_builder = StructureBuilderAgent()
    return _structure_builder
