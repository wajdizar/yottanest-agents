"""Write endpoint for section writing with SSE streaming."""

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.harness.runners import run_write
from app.logging import get_logger, get_trace_id
from app.schemas.structure import FrozenStructure
from app.schemas.evidence import EvidencePackage
from app.sse import create_sse_response, serialize_write_event


router = APIRouter(prefix="/write", tags=["write"])
logger = get_logger("endpoint.write")


class WriteRequest(BaseModel):
    """Request body for write endpoint."""

    frozen_structure: FrozenStructure = Field(
        description="Frozen report structure"
    )
    evidence_package: EvidencePackage = Field(
        description="Evidence package with all evidence and assignments"
    )


@router.post(
    "",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "SSE stream of write events",
            "content": {"text/event-stream": {}},
        },
    },
)
async def write_report(request: WriteRequest, http_request: Request) -> StreamingResponse:
    """
    Write all sections and assemble into final draft.

    Returns an SSE stream with events:
    - section_started: A section began processing
    - section_step_complete: Writer/editor/checker step completed
    - section_complete: A section finished
    - section_retry: A section is being retried
    - assembling: Assembly phase started
    - complete: Final assembled draft
    - error: Error occurred

    The client should handle disconnection gracefully.
    """
    trace_id = get_trace_id()
    logger.info(
        "write_request",
        section_count=len(request.frozen_structure.sections),
        evidence_count=len(request.evidence_package.evidence_pool),
    )

    # Create event generator
    events = run_write(
        structure=request.frozen_structure,
        evidence_package=request.evidence_package,
    )

    # Return SSE response
    return create_sse_response(
        events=events,
        event_serializer=serialize_write_event,
        headers={"X-Trace-ID": trace_id or ""},
    )
