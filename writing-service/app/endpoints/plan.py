"""Plan endpoint for structure generation."""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agents.base import AgentError
from app.harness.runners import run_plan, arun_plan
from app.logging import get_logger, get_trace_id
from app.schemas.structure import FrozenStructure
from app.schemas.errors import ErrorPayload, ErrorCodes


router = APIRouter(prefix="/plan", tags=["plan"])
logger = get_logger("endpoint.plan")


class PlanRequest(BaseModel):
    """Request body for plan endpoint."""

    goal: str = Field(
        description="Description of what the report should accomplish",
        min_length=10,
    )
    input_spec: dict[str, Any] | None = Field(
        default=None,
        description="Optional partial structure to enrich",
    )


class PlanResponse(BaseModel):
    """Response body for plan endpoint."""

    structure: FrozenStructure
    trace_id: str | None = None


@router.post(
    "",
    response_model=PlanResponse,
    responses={
        400: {"model": ErrorPayload, "description": "Invalid request"},
        422: {"model": ErrorPayload, "description": "Structure generation failed"},
        502: {"model": ErrorPayload, "description": "LLM error"},
    },
)
async def create_plan(request: PlanRequest) -> PlanResponse:
    """
    Generate a report structure from a goal.

    This endpoint analyzes the goal and optional input specification
    to create a frozen structure that guides the writing process.
    """
    trace_id = get_trace_id()
    logger.info(
        "plan_request",
        goal_length=len(request.goal),
        has_input_spec=request.input_spec is not None,
    )

    try:
        structure = await arun_plan(
            goal=request.goal,
            input_spec=request.input_spec,
        )

        logger.info(
            "plan_success",
            section_count=len(structure.sections),
            report_type=structure.metadata.report_type,
        )

        return PlanResponse(structure=structure, trace_id=trace_id)

    except AgentError as e:
        logger.error("plan_agent_error", error=str(e), error_code=e.error_code)
        raise HTTPException(
            status_code=_error_code_to_status(e.error_code),
            detail=e.to_error_payload(trace_id).model_dump(),
        )
    except Exception as e:
        logger.error("plan_unexpected_error", error=str(e))
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
        ErrorCodes.MISSING_REQUIRED_FIELD,
    }:
        return 400
    elif error_code in {
        ErrorCodes.SECTION_NOT_FOUND,
        ErrorCodes.EVIDENCE_NOT_FOUND,
    }:
        return 404
    elif error_code in {
        ErrorCodes.STRUCTURE_GENERATION_FAILED,
        ErrorCodes.RETRIEVAL_FAILED,
        ErrorCodes.WRITING_FAILED,
    }:
        return 422
    elif error_code in {
        ErrorCodes.LLM_ERROR,
        ErrorCodes.LLM_TIMEOUT,
        ErrorCodes.LLM_RATE_LIMIT,
        ErrorCodes.LLM_INVALID_RESPONSE,
    }:
        return 502
    elif error_code in {
        ErrorCodes.OPERATION_TIMEOUT,
        ErrorCodes.SECTION_TIMEOUT,
        ErrorCodes.WRITE_TIMEOUT,
    }:
        return 504
    else:
        return 500
