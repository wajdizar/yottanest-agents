"""Consistency endpoint for checking cross-section consistency."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agents.base import AgentError
from app.harness.runners import run_consistency, arun_consistency
from app.logging import get_logger, get_trace_id
from app.schemas.draft import AssembledDraft
from app.schemas.evidence import EvidencePackage
from app.schemas.consistency import ConsistencyFlag
from app.schemas.errors import ErrorPayload, ErrorCodes


router = APIRouter(prefix="/consistency", tags=["consistency"])
logger = get_logger("endpoint.consistency")


class ConsistencyRequest(BaseModel):
    """Request body for consistency endpoint."""

    assembled_draft: AssembledDraft = Field(
        description="Assembled draft to check"
    )
    evidence_package: EvidencePackage = Field(
        description="Evidence package for reference"
    )


class ConsistencyResponse(BaseModel):
    """Response body for consistency endpoint."""

    flags: list[ConsistencyFlag] = Field(
        description="List of consistency issues found"
    )
    trace_id: str | None = None


@router.post(
    "",
    response_model=ConsistencyResponse,
    responses={
        400: {"model": ErrorPayload, "description": "Invalid request"},
        422: {"model": ErrorPayload, "description": "Consistency check failed"},
        502: {"model": ErrorPayload, "description": "LLM error"},
    },
)
async def check_consistency(request: ConsistencyRequest) -> ConsistencyResponse:
    """
    Check consistency across all sections in an assembled draft.

    Returns a list of consistency flags identifying issues such as:
    - Numeric conflicts (different values for same metric)
    - Unsourced claims (claims without evidence)
    - Framing conflicts (contradictory characterizations)
    - Terminology inconsistencies
    - Date conflicts
    - Entity mismatches
    - Logical contradictions

    An empty flags list indicates the draft is consistent.
    """
    trace_id = get_trace_id()
    logger.info(
        "consistency_request",
        section_count=len(request.assembled_draft.sections),
        total_claims=len(request.assembled_draft.all_claims),
    )

    try:
        flags = await arun_consistency(
            draft=request.assembled_draft,
            evidence_package=request.evidence_package,
        )

        logger.info(
            "consistency_success",
            flag_count=len(flags),
            error_count=sum(1 for f in flags if f.severity == "error"),
            warning_count=sum(1 for f in flags if f.severity == "warning"),
        )

        return ConsistencyResponse(flags=flags, trace_id=trace_id)

    except AgentError as e:
        logger.error(
            "consistency_agent_error", error=str(e), error_code=e.error_code
        )
        raise HTTPException(
            status_code=_error_code_to_status(e.error_code),
            detail=e.to_error_payload(trace_id).model_dump(),
        )
    except Exception as e:
        logger.error("consistency_unexpected_error", error=str(e))
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
    }:
        return 400
    elif error_code in {
        ErrorCodes.CONSISTENCY_CHECK_FAILED,
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
