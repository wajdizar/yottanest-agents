"""DeerFlow harness initialization for Writing Service."""

import sys
from pathlib import Path

# Add DeerFlow backend to path for imports
DEER_FLOW_ROOT = Path(__file__).parent.parent.parent.parent.parent
DEER_FLOW_BACKEND = DEER_FLOW_ROOT / "backend"
if str(DEER_FLOW_BACKEND) not in sys.path:
    sys.path.insert(0, str(DEER_FLOW_BACKEND))

from app.logging import setup_logging, get_logger

_initialized = False


def initialize_harness() -> None:
    """
    Initialize the DeerFlow harness for the Writing Service.

    This sets up:
    - Structured logging
    - DeerFlow model factory (via config.yaml)
    - Tracing integration (LangSmith/Langfuse if configured)

    The harness is configured for stateless operation:
    - memory.enabled: Not used by writing service
    - sandbox.enabled: Not used by writing service
    - checkpointing.enabled: Not used by writing service
    """
    global _initialized

    if _initialized:
        return

    # Set up logging first
    setup_logging()

    logger = get_logger("harness")
    logger.info("harness_initializing", mode="deerflow-integrated")

    # Verify DeerFlow config is accessible
    try:
        from deerflow.config import get_app_config
        from app.config import get_writing_service_config

        app_config = get_app_config()
        ws_config = get_writing_service_config()

        logger.info(
            "deerflow_config_loaded",
            models_available=len(app_config.models),
            model_heavy=ws_config.model_heavy,
            model_standard=ws_config.model_standard,
            model_light=ws_config.model_light,
        )

        # Verify models exist in config
        model_names = [m.name for m in app_config.models]
        for weight, model in [
            ("heavy", ws_config.model_heavy),
            ("standard", ws_config.model_standard),
            ("light", ws_config.model_light),
        ]:
            if model not in model_names:
                logger.warning(
                    "model_not_found",
                    weight=weight,
                    model=model,
                    available=model_names,
                )

    except Exception as e:
        logger.error("deerflow_config_error", error=str(e))
        raise

    _initialized = True
    logger.info("harness_initialized", integration="deerflow")


def is_initialized() -> bool:
    """Check if harness is initialized."""
    return _initialized


def reset_harness() -> None:
    """Reset harness state (for testing)."""
    global _initialized
    _initialized = False

    # Clear config caches
    from app.config import clear_settings_cache
    clear_settings_cache()
