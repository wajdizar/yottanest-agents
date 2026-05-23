"""Schemas for retrieval planning and results."""

from pydantic import BaseModel, Field


class Query(BaseModel):
    """A single retrieval query."""

    query_id: str = Field(
        description="Unique identifier for this query"
    )
    question: str = Field(
        description="Natural language question to search for"
    )
    section_assignments: list[str] = Field(
        description="Section IDs this query is intended to serve"
    )
    priority: int = Field(
        description="Priority level (1=highest)",
        ge=1,
        le=5,
        default=3,
    )
    reasoning: str | None = Field(
        default=None,
        description="Why this query was generated",
    )


class QueryPlan(BaseModel):
    """Complete plan for retrieval queries."""

    queries: list[Query] = Field(
        description="List of queries to execute"
    )
    supports_followup: bool = Field(
        default=True,
        description="Whether the planner supports follow-up iterations",
    )
    iteration: int = Field(
        default=1,
        description="Current iteration number",
    )
    strategy_notes: str | None = Field(
        default=None,
        description="Notes on the overall retrieval strategy",
    )


class QueryResultItem(BaseModel):
    """A single result from a query."""

    doc_id: str = Field(
        description="Unique document identifier"
    )
    title: str = Field(
        description="Document title"
    )
    snippet: str = Field(
        description="Relevant excerpt from the document"
    )
    source: str = Field(
        description="Source system or database"
    )
    relevance_score: float = Field(
        description="Relevance score from retrieval system",
        ge=0.0,
        le=1.0,
    )
    doc_type: str | None = Field(
        default=None,
        description="Type of document",
    )
    date: str | None = Field(
        default=None,
        description="Document date if available",
    )
    url: str | None = Field(
        default=None,
        description="URL to the document if available",
    )
    metadata: dict | None = Field(
        default=None,
        description="Additional metadata from source",
    )


class QueryResults(BaseModel):
    """Results for a single query."""

    query_id: str = Field(
        description="ID of the query these results are for"
    )
    results: list[QueryResultItem] = Field(
        description="List of results for this query"
    )
    total_found: int = Field(
        description="Total number of matching documents"
    )
    truncated: bool = Field(
        default=False,
        description="Whether results were truncated",
    )


class Gap(BaseModel):
    """A gap identified in evidence coverage."""

    section_id: str = Field(
        description="Section with the gap"
    )
    requirement: str = Field(
        description="The requirement that is not satisfied"
    )
    gap_type: str = Field(
        description="Type of gap: 'missing' | 'partial' | 'weak'"
    )
    suggested_query: str | None = Field(
        default=None,
        description="Suggested follow-up query to fill the gap",
    )


class PreviousResultsSummary(BaseModel):
    """Summary of results from a previous iteration."""

    query_id: str = Field(
        description="ID of the query"
    )
    result_count: int = Field(
        description="Number of results returned"
    )
    useful_count: int = Field(
        description="Number of results deemed useful"
    )


class PreviousIteration(BaseModel):
    """Information about a previous retrieval iteration."""

    iteration: int = Field(
        description="The iteration number"
    )
    results_summary: list[PreviousResultsSummary] = Field(
        description="Summary of results from each query"
    )
    gaps_identified: list[Gap] = Field(
        description="Gaps identified after this iteration"
    )
