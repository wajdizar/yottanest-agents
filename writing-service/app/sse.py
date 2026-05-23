"""SSE (Server-Sent Events) helpers."""

import asyncio
import json
from typing import Any, AsyncIterator, Callable, TypeVar

from starlette.responses import StreamingResponse

from app.logging import get_logger


logger = get_logger("sse")

T = TypeVar("T")


def format_sse_event(
    event_type: str,
    data: dict[str, Any],
    event_id: str | None = None,
) -> str:
    """
    Format data as an SSE event.

    Args:
        event_type: Event type name
        data: Event data (will be JSON encoded)
        event_id: Optional event ID

    Returns:
        Formatted SSE event string
    """
    lines = []

    if event_id:
        lines.append(f"id: {event_id}")

    lines.append(f"event: {event_type}")
    lines.append(f"data: {json.dumps(data)}")
    lines.append("")  # Empty line to end event

    return "\n".join(lines) + "\n"


def format_sse_comment(comment: str) -> str:
    """Format a comment (heartbeat)."""
    return f": {comment}\n\n"


async def stream_to_sse(
    events: AsyncIterator[Any],
    event_serializer: Callable[[Any], tuple[str, dict[str, Any]]],
    heartbeat_interval: float = 15.0,
) -> AsyncIterator[str]:
    """
    Convert an async iterator of events to SSE format.

    Args:
        events: Async iterator of events
        event_serializer: Function to convert event to (event_type, data) tuple
        heartbeat_interval: Seconds between heartbeat comments

    Yields:
        SSE formatted strings
    """
    event_counter = 0
    last_heartbeat = asyncio.get_event_loop().time()

    async def heartbeat_check() -> str | None:
        """Check if heartbeat needed."""
        nonlocal last_heartbeat
        now = asyncio.get_event_loop().time()
        if now - last_heartbeat >= heartbeat_interval:
            last_heartbeat = now
            return format_sse_comment("heartbeat")
        return None

    try:
        async for event in events:
            # Check for heartbeat
            heartbeat = await heartbeat_check()
            if heartbeat:
                yield heartbeat

            # Serialize and yield event
            try:
                event_type, data = event_serializer(event)
                event_counter += 1
                yield format_sse_event(
                    event_type=event_type,
                    data=data,
                    event_id=str(event_counter),
                )
            except Exception as e:
                logger.error("sse_serialization_error", error=str(e))
                yield format_sse_event(
                    event_type="error",
                    data={"error": "serialization_error", "message": str(e)},
                )

    except asyncio.CancelledError:
        logger.info("sse_stream_cancelled")
        raise
    except Exception as e:
        logger.error("sse_stream_error", error=str(e))
        yield format_sse_event(
            event_type="error",
            data={"error": "stream_error", "message": str(e)},
        )


def create_sse_response(
    events: AsyncIterator[Any],
    event_serializer: Callable[[Any], tuple[str, dict[str, Any]]],
    headers: dict[str, str] | None = None,
) -> StreamingResponse:
    """
    Create a StreamingResponse for SSE.

    Args:
        events: Async iterator of events
        event_serializer: Function to convert event to (event_type, data) tuple
        headers: Additional headers

    Returns:
        StreamingResponse configured for SSE
    """
    default_headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",  # Disable nginx buffering
    }

    if headers:
        default_headers.update(headers)

    return StreamingResponse(
        stream_to_sse(events, event_serializer),
        media_type="text/event-stream",
        headers=default_headers,
    )


# Event serializers for write events


def serialize_write_event(event: Any) -> tuple[str, dict[str, Any]]:
    """Serialize a write event to SSE format."""
    from app.harness.runners import (
        SectionStartedEvent,
        SectionStepCompleteEvent,
        SectionCompleteEvent,
        SectionRetryEvent,
        AssemblingEvent,
        WriteCompleteEvent,
        WriteErrorEvent,
    )

    if isinstance(event, SectionStartedEvent):
        return ("section_started", {
            "section_id": event.section_id,
            "title": event.title,
        })
    elif isinstance(event, SectionStepCompleteEvent):
        return ("section_step_complete", {
            "section_id": event.section_id,
            "step": event.step,
            "status": event.status,
        })
    elif isinstance(event, SectionCompleteEvent):
        return ("section_complete", {
            "section_id": event.section_id,
            "draft": event.draft.model_dump(),
        })
    elif isinstance(event, SectionRetryEvent):
        return ("section_retry", {
            "section_id": event.section_id,
            "retry_count": event.retry_count,
            "reason": event.reason,
        })
    elif isinstance(event, AssemblingEvent):
        return ("assembling", {})
    elif isinstance(event, WriteCompleteEvent):
        return ("complete", {
            "draft": event.draft.model_dump(),
        })
    elif isinstance(event, WriteErrorEvent):
        return ("error", {
            "error_code": event.error_code,
            "message": event.message,
            "section_id": event.section_id,
        })
    else:
        return ("unknown", {"type": type(event).__name__})
