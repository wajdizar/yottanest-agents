"""Revise endpoint for section revision with SSE streaming."""

import asyncio
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.harness.runners import run_revise
from app.logging import get_logger, get_trace_id
from app.schemas.structure import FrozenStructure
from app.schemas.evidence import EvidencePackage
from app.schemas.draft import SectionDraft
from app.schemas.feedback import Feedback
from app.schemas.errors import ErrorCodes
from app.sse import format_sse_event, format_sse_comment


router = APIRouter(prefix="/revise", tags=["revise"])
logger = get_logger("endpoint.revise")


class ReviseRequest(BaseModel):
    """Request body for revise endpoint."""

    section_id: str = Field(
        description="Section ID to revise"
    )
    original_draft: SectionDraft = Field(
        description="Original section draft"
    )
    frozen_structure: FrozenStructure = Field(
        description="Frozen report structure"
    )
    evidence_package: EvidencePackage = Field(
        description="Evidence package"
    )
    feedback: Feedback = Field(
        description="Revision feedback"
    )


async def _revise_stream(
    section_id: str,
    original_draft: SectionDraft,
    structure: FrozenStructure,
    evidence_package: EvidencePackage,
    feedback: Feedback,
):
    """Generate SSE events for revision."""
    event_counter = 0

    def make_event(event_type: str, data: dict[str, Any]) -> str:
        nonlocal event_counter
        event_counter += 1
        return format_sse_event(event_type, data, str(event_counter))

    try:
        # Emit start event
        yield make_event("revision_started", {
            "section_id": section_id,
            "feedback_type": feedback.feedback_type,
        })

        # Run revision
        revised_draft = await run_revise(
            section_id=section_id,
            original_draft=original_draft,
            structure=structure,
            evidence_package=evidence_package,
            feedback=feedback,
        )

        # Emit complete event
        yield make_event("complete", {
            "revised_draft": revised_draft.model_dump(),
            "changelog": revised_draft.changelog,
        })

    except Exception as e:
        logger.error("revise_stream_error", error=str(e), section_id=section_id)
        yield make_event("error", {
            "error_code": ErrorCodes.WRITING_FAILED,
            "message": str(e),
            "section_id": section_id,
        })


@router.post(
    "",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "SSE stream of revision events",
            "content": {"text/event-stream": {}},
        },
    },
)
async def revise_section(request: ReviseRequest, http_request: Request) -> StreamingResponse:
    """
    Revise a section based on feedback.

    Returns an SSE stream with events:
    - revision_started: Revision began
    - complete: Revised draft with changelog
    - error: Error occurred

    The revised draft includes a changelog documenting changes made.
    """
    trace_id = get_trace_id()
    logger.info(
        "revise_request",
        section_id=request.section_id,
        feedback_type=request.feedback.feedback_type,
        augmented_evidence=request.feedback.augmented_evidence,
    )

    return StreamingResponse(
        _revise_stream(
            section_id=request.section_id,
            original_draft=request.original_draft,
            structure=request.frozen_structure,
            evidence_package=request.evidence_package,
            feedback=request.feedback,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Trace-ID": trace_id or "",
        },
    )
