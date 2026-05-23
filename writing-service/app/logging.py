"""Structured logging setup for the Writing Service.

Compatible with DeerFlow's logging system.
"""

import logging
import sys
from contextvars import ContextVar
from typing import Any
from uuid import uuid4

import structlog

# Context variable for trace ID propagation
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")


def get_trace_id() -> str:
    """Get the current trace ID."""
    return trace_id_var.get()


def set_trace_id(trace_id: str | None = None) -> str:
    """Set or generate a new trace ID."""
    if trace_id is None:
        trace_id = str(uuid4())
    trace_id_var.set(trace_id)
    return trace_id


def add_trace_id(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Add trace_id to all log entries."""
    trace_id = get_trace_id()
    if trace_id:
        event_dict["trace_id"] = trace_id
    return event_dict


def setup_logging(log_level: str = "INFO", log_format: str = "json") -> None:
    """Configure structured logging.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_format: Output format ("json" or "console")
    """
    import os

    # Allow environment override
    log_level = os.environ.get("LOG_LEVEL", log_level).upper()
    log_format = os.environ.get("LOG_FORMAT", log_format).lower()

    # Shared processors
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        add_trace_id,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if log_format == "json":
        # JSON format for production
        structlog.configure(
            processors=[
                *shared_processors,
                structlog.processors.format_exc_info,
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(
                getattr(logging, log_level)
            ),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )
    else:
        # Console format for development
        structlog.configure(
            processors=[
                *shared_processors,
                structlog.dev.ConsoleRenderer(colors=True),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(
                getattr(logging, log_level)
            ),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )

    # Configure standard library logging to use structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level),
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a logger instance."""
    return structlog.get_logger(name)


class AgentLogger:
    """Logger for agent invocations with structured metrics."""

    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.logger = get_logger(agent_name)

    def log_invocation_start(
        self,
        model: str,
        input_summary: str | None = None,
    ) -> None:
        """Log the start of an agent invocation."""
        self.logger.info(
            "agent_invocation_start",
            agent_name=self.agent_name,
            model=model,
            input_summary=input_summary,
        )

    def log_invocation_complete(
        self,
        model: str,
        duration_ms: float,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        status: str = "success",
    ) -> None:
        """Log the completion of an agent invocation."""
        self.logger.info(
            "agent_invocation_complete",
            agent_name=self.agent_name,
            model=model,
            duration_ms=duration_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            status=status,
        )

    def log_invocation_error(
        self,
        model: str,
        error: str,
        duration_ms: float | None = None,
        raw_output: str | None = None,
    ) -> None:
        """Log an error during agent invocation."""
        self.logger.error(
            "agent_invocation_error",
            agent_name=self.agent_name,
            model=model,
            error=error,
            duration_ms=duration_ms,
            raw_output=raw_output,
        )

    def log_structured_output_failure(
        self,
        model: str,
        raw_output: str,
        error: str,
    ) -> None:
        """Log a failure to parse structured output."""
        self.logger.error(
            "structured_output_failure",
            agent_name=self.agent_name,
            model=model,
            raw_output=raw_output,
            error=error,
        )
