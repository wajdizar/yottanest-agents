"""Retrieve endpoints for query planning and evaluation."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agents.base import AgentError
from app.harness.runners import run_retrieve_plan, run_retrieve_evaluate
from app.logging import get_logger, get_trace_id
from app.schemas.structure import FrozenStructure
from app.schemas.retrieval import QueryPlan, QueryResults, PreviousIteration
from app.schemas.evidence import EvidencePackage
from app.schemas.errors import ErrorPayload, ErrorCodes


router = APIRouter(prefix="/retrieve", tags=["retrieve"])
logger = get_logger("endpoint.retrieve")


class RetrievePlanRequest(BaseModel):
    """Request body for retrieve/plan endpoint."""

    structure: FrozenStructure = Field(
        description="Frozen report structure"
    )
    previous_iteration: PreviousIteration | None = Field(
        default=None,
        description="Optional previous iteration info for follow-up queries",
    )


class RetrievePlanResponse(BaseModel):
    """Response body for retrieve/plan endpoint."""

    query_plan: QueryPlan
    trace_id: str | None = None


class RetrieveEvaluateRequest(BaseModel):
    """Request body for retrieve/evaluate endpoint."""

    structure: FrozenStructure = Field(
        description="Frozen report structure"
    )
    query_results: list[QueryResults] = Field(
        description="Results from executing queries"
    )
    query_plan: QueryPlan = Field(
        description="The query plan that was executed"
    )
    iteration: int = Field(
        default=1,
        description="Current iteration number",
        ge=1,
    )


class RetrieveEvaluateResponse(BaseModel):
    """Response body for retrieve/evaluate endpoint."""

    evidence_package: EvidencePackage
    trace_id: str | None = None


@router.post(
    "/plan",
    response_model=RetrievePlanResponse,
    responses={
        400: {"model": ErrorPayload, "description": "Invalid request"},
        422: {"model": ErrorPayload, "description": "Planning failed"},
        502: {"model": ErrorPayload, "description": "LLM error"},
    },
)
async def create_retrieve_plan(request: RetrievePlanRequest) -> RetrievePlanResponse:
    """
    Generate retrieval queries for a report structure.

    This endpoint analyzes the structure and generates natural language
    queries to find relevant evidence from the knowledge base.
    """
    trace_id = get_trace_id()
    logger.info(
        "retrieve_plan_request",
        section_count=len(request.structure.sections),
        is_followup=request.previous_iteration is not None,
    )

    try:
        # Note: Using sync version as LangChain structured output is sync
        query_plan = run_retrieve_plan(
            structure=request.structure,
            previous_iteration=request.previous_iteration,
        )

        logger.info(
            "retrieve_plan_success",
            query_count=len(query_plan.queries),
            iteration=query_plan.iteration,
        )

        return RetrievePlanResponse(query_plan=query_plan, trace_id=trace_id)

    except AgentError as e:
        logger.error("retrieve_plan_agent_error", error=str(e), error_code=e.error_code)
        raise HTTPException(
            status_code=_error_code_to_status(e.error_code),
            detail=e.to_error_payload(trace_id).model_dump(),
        )
    except Exception as e:
        logger.error("retrieve_plan_unexpected_error", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=ErrorPayload(
                error_code=ErrorCodes.INTERNAL_ERROR,
                message=str(e),
                trace_id=trace_id,
            ).model_dump(),
        )


@router.post(
    "/evaluate",
    response_model=RetrieveEvaluateResponse,
    responses={
        400: {"model": ErrorPayload, "description": "Invalid request"},
        422: {"model": ErrorPayload, "description": "Evaluation failed"},
        502: {"model": ErrorPayload, "description": "LLM error"},
    },
)
async def evaluate_retrieve_results(
    request: RetrieveEvaluateRequest,
) -> RetrieveEvaluateResponse:
    """
    Evaluate query results and build evidence package.

    This endpoint processes query results, deduplicates evidence,
    assigns it to sections, and evaluates coverage.
    """
    trace_id = get_trace_id()
    logger.info(
        "retrieve_evaluate_request",
        result_count=len(request.query_results),
        iteration=request.iteration,
    )

    try:
        evidence_package = run_retrieve_evaluate(
            structure=request.structure,
            query_results=request.query_results,
            query_plan=request.query_plan,
            iteration=request.iteration,
        )

        logger.info(
            "retrieve_evaluate_success",
            evidence_count=len(evidence_package.evidence_pool),
            needs_followup=evidence_package.needs_followup,
        )

        return RetrieveEvaluateResponse(
            evidence_package=evidence_package,
            trace_id=trace_id,
        )

    except AgentError as e:
        logger.error(
            "retrieve_evaluate_agent_error", error=str(e), error_code=e.error_code
        )
        raise HTTPException(
            status_code=_error_code_to_status(e.error_code),
            detail=e.to_error_payload(trace_id).model_dump(),
        )
    except Exception as e:
        logger.error("retrieve_evaluate_unexpected_error", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=ErrorPayload(
                error_code=ErrorCodes.INTERNAL_ERROR,
                message=str(e),
                trace_id=trace_id,
            ).model_dump(),
        )


def _error_code_to_status(error_code: str) -> int:
    """Map error code to HTTP status."""
    if error_code in {
        ErrorCodes.VALIDATION_ERROR,
        ErrorCodes.INVALID_STRUCTURE,
        ErrorCodes.INVALID_EVIDENCE,
    }:
        return 400
    elif error_code in {
        ErrorCodes.RETRIEVAL_FAILED,
        ErrorCodes.EVALUATION_FAILED,
    }:
        return 422
    elif error_code in {
        ErrorCodes.LLM_ERROR,
        ErrorCodes.LLM_TIMEOUT,
        ErrorCodes.LLM_RATE_LIMIT,
        ErrorCodes.LLM_INVALID_RESPONSE,
    }:
        return 502
    else:
        return 500
