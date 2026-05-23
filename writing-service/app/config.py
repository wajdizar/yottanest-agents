"""Configuration settings for the Writing Service.

Integrates with DeerFlow's configuration system.
"""

import sys
from functools import lru_cache
from pathlib import Path
from typing import Literal, Any

from pydantic import BaseModel, Field

# Add DeerFlow backend to path for imports
DEER_FLOW_ROOT = Path(__file__).parent.parent.parent.parent
DEER_FLOW_BACKEND = DEER_FLOW_ROOT / "backend"
if str(DEER_FLOW_BACKEND) not in sys.path:
    sys.path.insert(0, str(DEER_FLOW_BACKEND))

# Import DeerFlow config after path setup
from deerflow.config import get_app_config
from deerflow.config.app_config import AppConfig


class WritingServiceConfig(BaseModel):
    """Writing service specific configuration."""

    # Model tiers
    model_heavy: str = Field(
        default="ollama-yi-34b",
        description="Model for heavyweight tasks (planner, assembler, consistency)",
    )
    model_standard: str = Field(
        default="ollama-qwen2.5",
        description="Model for standard tasks (writer)",
    )
    model_light: str = Field(
        default="ollama-qwen2.5",
        description="Model for lightweight tasks (editor, checker)",
    )

    # Timeouts (seconds)
    write_timeout: int = Field(
        default=600,
        description="Timeout for entire write operation",
    )
    section_timeout: int = Field(
        default=120,
        description="Timeout for single section write",
    )
    llm_call_timeout: int = Field(
        default=60,
        description="Timeout for individual LLM calls",
    )

    # Retry Configuration
    section_checker_max_retries: int = Field(
        default=2,
        description="Maximum retries for section checker failures",
    )
    retrieval_max_iterations: int = Field(
        default=3,
        description="Maximum retrieval iterations",
    )


def get_writing_service_config() -> WritingServiceConfig:
    """Get writing service configuration from DeerFlow config."""
    app_config = get_app_config()

    # Get writing_service section from config
    writing_config = getattr(app_config, "writing_service", None)

    if writing_config is None:
        # Try to get from raw config data
        try:
            raw_config = app_config.model_dump()
            writing_config = raw_config.get("writing_service", {})
        except Exception:
            writing_config = {}

    if isinstance(writing_config, dict):
        return WritingServiceConfig(**writing_config)
    elif isinstance(writing_config, WritingServiceConfig):
        return writing_config
    else:
        return WritingServiceConfig()


def get_deerflow_config() -> AppConfig:
    """Get the full DeerFlow application config."""
    return get_app_config()


# Legacy settings class for backward compatibility
class Settings(BaseModel):
    """Legacy settings class - use get_writing_service_config() instead."""

    # Model Configuration (mapped from DeerFlow config)
    llm_model_heavy: str = "ollama-yi-34b"
    llm_model_standard: str = "ollama-qwen2.5"
    llm_model_light: str = "ollama-qwen2.5"

    # Timeouts (seconds)
    write_timeout_seconds: int = 600
    section_timeout_seconds: int = 120
    llm_call_timeout_seconds: int = 60

    # Retry Configuration
    section_checker_max_retries: int = 2
    retrieval_max_iterations: int = 3

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "console"] = "json"

    # Server
    host: str = "0.0.0.0"
    port: int = 8500


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance mapped from DeerFlow config."""
    ws_config = get_writing_service_config()

    return Settings(
        llm_model_heavy=ws_config.model_heavy,
        llm_model_standard=ws_config.model_standard,
        llm_model_light=ws_config.model_light,
        write_timeout_seconds=ws_config.write_timeout,
        section_timeout_seconds=ws_config.section_timeout,
        llm_call_timeout_seconds=ws_config.llm_call_timeout,
        section_checker_max_retries=ws_config.section_checker_max_retries,
        retrieval_max_iterations=ws_config.retrieval_max_iterations,
    )


def clear_settings_cache() -> None:
    """Clear the settings cache."""
    get_settings.cache_clear()
