"""Schemas for error responses."""

from typing import Any

from pydantic import BaseModel, Field


class ErrorPayload(BaseModel):
    """Standard error response payload."""

    error_code: str = Field(
        description="Machine-readable error code"
    )
    message: str = Field(
        description="Human-readable error message"
    )
    details: dict[str, Any] | None = Field(
        default=None,
        description="Additional error details",
    )
    trace_id: str | None = Field(
        default=None,
        description="Request trace ID for debugging",
    )
    retryable: bool = Field(
        default=False,
        description="Whether the request can be retried",
    )


# Standard error codes
class ErrorCodes:
    """Standard error codes for the writing service."""

    # Validation errors (400)
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_STRUCTURE = "INVALID_STRUCTURE"
    INVALID_EVIDENCE = "INVALID_EVIDENCE"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"

    # Resource errors (404)
    SECTION_NOT_FOUND = "SECTION_NOT_FOUND"
    EVIDENCE_NOT_FOUND = "EVIDENCE_NOT_FOUND"

    # Processing errors (422)
    STRUCTURE_GENERATION_FAILED = "STRUCTURE_GENERATION_FAILED"
    RETRIEVAL_FAILED = "RETRIEVAL_FAILED"
    EVALUATION_FAILED = "EVALUATION_FAILED"
    WRITING_FAILED = "WRITING_FAILED"
    ASSEMBLY_FAILED = "ASSEMBLY_FAILED"
    CONSISTENCY_CHECK_FAILED = "CONSISTENCY_CHECK_FAILED"

    # LLM errors (502)
    LLM_ERROR = "LLM_ERROR"
    LLM_TIMEOUT = "LLM_TIMEOUT"
    LLM_RATE_LIMIT = "LLM_RATE_LIMIT"
    LLM_INVALID_RESPONSE = "LLM_INVALID_RESPONSE"

    # Internal errors (500)
    INTERNAL_ERROR = "INTERNAL_ERROR"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"

    # Timeout errors (504)
    OPERATION_TIMEOUT = "OPERATION_TIMEOUT"
    SECTION_TIMEOUT = "SECTION_TIMEOUT"
    WRITE_TIMEOUT = "WRITE_TIMEOUT"
