"""DeerFlow harness integration for Writing Service.

Uses DeerFlow's model factory and configuration system.
"""

from app.harness.openrouter_provider import get_model, get_model_name, ModelWeight
from app.harness.setup import initialize_harness

__all__ = ["get_model", "get_model_name", "ModelWeight", "initialize_harness"]
