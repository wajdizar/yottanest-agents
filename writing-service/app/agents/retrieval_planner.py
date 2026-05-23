"""Retrieval Planner agent for generating search queries."""

import json
from typing import Any

from app.agents.base import BaseAgent
from app.harness.openrouter_provider import ModelWeight
from app.schemas.structure import FrozenStructure
from app.schemas.retrieval import QueryPlan, PreviousIteration


RETRIEVAL_PLANNER_PROMPT = """You are a retrieval planning specialist. Your task is to generate search queries that will find evidence for a compliance report.

## Report Structure

```json
{structure_json}
```

{previous_iteration_section}

## Your Task

Generate a QueryPlan with search queries to find evidence for this report.

### Query Guidelines

1. **Natural Language Questions**: Each query should be a natural language question that a search system can answer.

2. **Section Assignments**: Assign each query to one or more sections that will use the results.

3. **Priority**: Set priority 1-5 (1=highest) based on importance to the report.

4. **Coverage**: Ensure queries cover all section requirements, especially must_include items.

5. **Specificity**: Be specific about what you're looking for:
   - Bad: "company information"
   - Good: "What is the corporate registration number and incorporation date for [Company]?"

6. **Avoid Redundancy**: Don't create multiple queries for the same information.

{mode_instructions}

## Output

Provide a QueryPlan with:
- queries: List of Query objects
- supports_followup: true (this planner supports iterations)
- iteration: {iteration}
- strategy_notes: Brief explanation of your approach"""


INITIAL_MODE_INSTRUCTIONS = """### Initial Mode

This is iteration 1. Generate comprehensive queries covering all sections:
- 2-4 queries per section on average
- Cover all requirements and must_include items
- Include queries for shared evidence (useful across sections)
- Total typically 8-15 queries"""


FOLLOWUP_MODE_INSTRUCTIONS = """### Follow-up Mode

Previous iteration identified gaps. Focus on:
- Filling identified gaps
- Alternative queries for weak/missing coverage
- Do NOT repeat successful queries

Gaps to address:
{gaps_json}

Keep query count smaller (3-6 queries) targeting specific gaps."""


class RetrievalPlannerAgent(BaseAgent[QueryPlan]):
    """
    Agent that generates retrieval queries from report structure.

    Uses heavyweight model for strategic planning.
    """

    agent_name = "retrieval_planner"
    model_weight: ModelWeight = "heavy"
    output_schema = QueryPlan

    def build_prompt(self, **kwargs: Any) -> str:
        """Build the retrieval planner prompt."""
        structure: FrozenStructure = kwargs["structure"]
        previous_iteration: PreviousIteration | None = kwargs.get("previous_iteration")

        structure_json = structure.model_dump_json(indent=2)

        if previous_iteration:
            # Follow-up mode
            iteration = previous_iteration.iteration + 1
            previous_iteration_section = f"""## Previous Iteration Results

Iteration {previous_iteration.iteration} completed. Results summary:
```json
{json.dumps([s.model_dump() for s in previous_iteration.results_summary], indent=2)}
```"""
            gaps_json = json.dumps(
                [g.model_dump() for g in previous_iteration.gaps_identified], indent=2
            )
            mode_instructions = FOLLOWUP_MODE_INSTRUCTIONS.format(gaps_json=gaps_json)
        else:
            # Initial mode
            iteration = 1
            previous_iteration_section = "(Initial iteration - no previous results)"
            mode_instructions = INITIAL_MODE_INSTRUCTIONS

        return RETRIEVAL_PLANNER_PROMPT.format(
            structure_json=structure_json,
            previous_iteration_section=previous_iteration_section,
            mode_instructions=mode_instructions,
            iteration=iteration,
        )


# Module-level singleton
_retrieval_planner: RetrievalPlannerAgent | None = None


def get_retrieval_planner() -> RetrievalPlannerAgent:
    """Get the retrieval planner agent singleton."""
    global _retrieval_planner
    if _retrieval_planner is None:
        _retrieval_planner = RetrievalPlannerAgent()
    return _retrieval_planner
