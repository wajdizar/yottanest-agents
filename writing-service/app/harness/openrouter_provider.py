"""Model provider using DeerFlow's model factory.

This module provides model access through DeerFlow's unified model system,
which supports multiple providers configured in config.yaml.
"""

import sys
from functools import lru_cache
from pathlib import Path
from typing import Literal

from langchain.chat_models.base import BaseChatModel

# Add DeerFlow backend to path for imports
DEER_FLOW_ROOT = Path(__file__).parent.parent.parent.parent.parent
DEER_FLOW_BACKEND = DEER_FLOW_ROOT / "backend"
if str(DEER_FLOW_BACKEND) not in sys.path:
    sys.path.insert(0, str(DEER_FLOW_BACKEND))

# Import DeerFlow model factory
from deerflow.models import create_chat_model
from deerflow.config import get_app_config

from app.config import get_writing_service_config

ModelWeight = Literal["heavy", "standard", "light"]


def get_model(weight: ModelWeight = "standard", thinking_enabled: bool = False) -> BaseChatModel:
    """
    Get a LangChain chat model from DeerFlow's model factory.

    Args:
        weight: Model tier to use:
            - "heavy": For complex reasoning tasks (planner, assembler, consistency)
            - "standard": For primary writing tasks (writer)
            - "light": For quick tasks (editor, checker)
        thinking_enabled: Whether to enable extended thinking mode.

    Returns:
        Configured BaseChatModel instance from DeerFlow.
    """
    ws_config = get_writing_service_config()

    model_map = {
        "heavy": ws_config.model_heavy,
        "standard": ws_config.model_standard,
        "light": ws_config.model_light,
    }

    model_name = model_map[weight]

    # Use DeerFlow's model factory
    # attach_tracing=True enables LangSmith/Langfuse if configured
    return create_chat_model(
        name=model_name,
        thinking_enabled=thinking_enabled,
        attach_tracing=True,
    )


def get_model_name(weight: ModelWeight = "standard") -> str:
    """Get the model name for a given weight."""
    ws_config = get_writing_service_config()

    model_map = {
        "heavy": ws_config.model_heavy,
        "standard": ws_config.model_standard,
        "light": ws_config.model_light,
    }

    return model_map[weight]


def list_available_models() -> list[str]:
    """List all available models from DeerFlow config."""
    app_config = get_app_config()
    return [model.name for model in app_config.models]


def clear_model_cache() -> None:
    """Clear any model caches (for testing)."""
    # DeerFlow manages its own caching
    pass
