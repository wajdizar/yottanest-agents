"""Base agent class and utilities using DeerFlow's model factory."""

import time
from abc import ABC, abstractmethod
from typing import Any, TypeVar, Generic

from pydantic import BaseModel, ValidationError

from app.harness.openrouter_provider import get_model, get_model_name, ModelWeight
from app.logging import AgentLogger, get_logger
from app.schemas.errors import ErrorPayload, ErrorCodes

T = TypeVar("T", bound=BaseModel)


class AgentError(Exception):
    """Base exception for agent errors."""

    def __init__(
        self,
        message: str,
        error_code: str = ErrorCodes.INTERNAL_ERROR,
        details: dict[str, Any] | None = None,
        raw_output: str | None = None,
    ):
        super().__init__(message)
        self.error_code = error_code
        self.details = details or {}
        self.raw_output = raw_output

    def to_error_payload(self, trace_id: str | None = None) -> ErrorPayload:
        """Convert to ErrorPayload."""
        return ErrorPayload(
            error_code=self.error_code,
            message=str(self),
            details=self.details,
            trace_id=trace_id,
            retryable=self.error_code in {
                ErrorCodes.LLM_TIMEOUT,
                ErrorCodes.LLM_RATE_LIMIT,
            },
        )


class BaseAgent(ABC, Generic[T]):
    """
    Base class for all agents.

    Uses DeerFlow's model factory for model access, which provides:
    - Unified model configuration via config.yaml
    - Automatic tracing (LangSmith/Langfuse) when configured
    - Support for multiple providers (OpenAI, Anthropic, Ollama, etc.)

    Provides:
    - Structured output handling with Pydantic models
    - Logging with metrics
    - Error handling per spec 5.7
    """

    agent_name: str = "base_agent"
    model_weight: ModelWeight = "standard"
    output_schema: type[T]
    thinking_enabled: bool = False

    def __init__(self):
        self.logger = AgentLogger(self.agent_name)
        self._log = get_logger(self.agent_name)

    @abstractmethod
    def build_prompt(self, **kwargs: Any) -> str:
        """Build the prompt for this agent."""
        ...

    def invoke(self, **kwargs: Any) -> T:
        """
        Invoke the agent with structured output.

        Uses DeerFlow's model factory which automatically handles:
        - Model selection from config.yaml
        - Tracing callbacks (LangSmith/Langfuse)
        - Provider-specific settings

        Args:
            **kwargs: Input parameters for the agent.

        Returns:
            Validated output model.

        Raises:
            AgentError: If invocation fails.
        """
        # Get model from DeerFlow factory
        model = get_model(self.model_weight, thinking_enabled=self.thinking_enabled)
        model_name = get_model_name(self.model_weight)

        # Build prompt
        prompt = self.build_prompt(**kwargs)

        # Log start
        self.logger.log_invocation_start(
            model=model_name,
            input_summary=prompt[:200] + "..." if len(prompt) > 200 else prompt,
        )

        start_time = time.time()

        try:
            # Use structured output
            structured_model = model.with_structured_output(self.output_schema)
            result = structured_model.invoke(prompt)

            duration_ms = (time.time() - start_time) * 1000

            # Log success
            self.logger.log_invocation_complete(
                model=model_name,
                duration_ms=duration_ms,
                status="success",
            )

            return result

        except ValidationError as e:
            duration_ms = (time.time() - start_time) * 1000

            # Log structured output failure
            self.logger.log_structured_output_failure(
                model=model_name,
                raw_output="<validation_error>",
                error=str(e),
            )

            raise AgentError(
                message=f"Failed to parse structured output: {e}",
                error_code=ErrorCodes.LLM_INVALID_RESPONSE,
                details={"validation_errors": e.errors()},
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000

            # Log error
            self.logger.log_invocation_error(
                model=model_name,
                error=str(e),
                duration_ms=duration_ms,
            )

            # Check for specific error types
            error_str = str(e).lower()
            if "timeout" in error_str:
                error_code = ErrorCodes.LLM_TIMEOUT
            elif "rate" in error_str and "limit" in error_str:
                error_code = ErrorCodes.LLM_RATE_LIMIT
            else:
                error_code = ErrorCodes.LLM_ERROR

            raise AgentError(
                message=f"Agent invocation failed: {e}",
                error_code=error_code,
                details={"original_error": str(e)},
            )

    async def ainvoke(self, **kwargs: Any) -> T:
        """
        Async invoke the agent with structured output.

        Args:
            **kwargs: Input parameters for the agent.

        Returns:
            Validated output model.

        Raises:
            AgentError: If invocation fails.
        """
        # Get model from DeerFlow factory
        model = get_model(self.model_weight, thinking_enabled=self.thinking_enabled)
        model_name = get_model_name(self.model_weight)

        # Build prompt
        prompt = self.build_prompt(**kwargs)

        # Log start
        self.logger.log_invocation_start(
            model=model_name,
            input_summary=prompt[:200] + "..." if len(prompt) > 200 else prompt,
        )

        start_time = time.time()

        try:
            # Use structured output
            structured_model = model.with_structured_output(self.output_schema)
            result = await structured_model.ainvoke(prompt)

            duration_ms = (time.time() - start_time) * 1000

            # Log success
            self.logger.log_invocation_complete(
                model=model_name,
                duration_ms=duration_ms,
                status="success",
            )

            return result

        except ValidationError as e:
            duration_ms = (time.time() - start_time) * 1000

            self.logger.log_structured_output_failure(
                model=model_name,
                raw_output="<validation_error>",
                error=str(e),
            )

            raise AgentError(
                message=f"Failed to parse structured output: {e}",
                error_code=ErrorCodes.LLM_INVALID_RESPONSE,
                details={"validation_errors": e.errors()},
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000

            self.logger.log_invocation_error(
                model=model_name,
                error=str(e),
                duration_ms=duration_ms,
            )

            error_str = str(e).lower()
            if "timeout" in error_str:
                error_code = ErrorCodes.LLM_TIMEOUT
            elif "rate" in error_str and "limit" in error_str:
                error_code = ErrorCodes.LLM_RATE_LIMIT
            else:
                error_code = ErrorCodes.LLM_ERROR

            raise AgentError(
                message=f"Agent invocation failed: {e}",
                error_code=error_code,
                details={"original_error": str(e)},
            )
