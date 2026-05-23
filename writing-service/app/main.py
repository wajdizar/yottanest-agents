"""Main FastAPI application for the Writing Service.

Integrates with DeerFlow's model factory and configuration system.
"""

import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

# Add DeerFlow backend to path for imports
DEER_FLOW_ROOT = Path(__file__).parent.parent.parent
DEER_FLOW_BACKEND = DEER_FLOW_ROOT / "backend"
if str(DEER_FLOW_BACKEND) not in sys.path:
    sys.path.insert(0, str(DEER_FLOW_BACKEND))

from app.harness.setup import initialize_harness
from app.logging import setup_logging, get_logger, set_trace_id, get_trace_id
from app.schemas.errors import ErrorPayload, ErrorCodes
from app.endpoints import (
    plan_router,
    retrieve_router,
    write_router,
    revise_router,
    consistency_router,
)


logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    setup_logging()
    initialize_harness()
    logger.info("application_started", integration="deerflow")

    yield

    # Shutdown
    logger.info("application_shutdown")


app = FastAPI(
    title="Writing Service",
    description="A DeerFlow-integrated service for generating structured compliance reports",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def trace_id_middleware(request: Request, call_next):
    """Add trace ID to all requests."""
    # Check for existing trace ID in header
    trace_id = request.headers.get("X-Trace-ID")
    trace_id = set_trace_id(trace_id)

    # Add trace ID to response
    response = await call_next(request)
    response.headers["X-Trace-ID"] = trace_id

    return response


@app.exception_handler(ValidationError)
async def validation_exception_handler(
    request: Request, exc: ValidationError
) -> JSONResponse:
    """Handle Pydantic validation errors."""
    trace_id = get_trace_id()
    logger.warning(
        "validation_error",
        errors=exc.errors(),
        url=str(request.url),
    )

    return JSONResponse(
        status_code=400,
        content=ErrorPayload(
            error_code=ErrorCodes.VALIDATION_ERROR,
            message="Request validation failed",
            details={"errors": exc.errors()},
            trace_id=trace_id,
            retryable=False,
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def general_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Handle unexpected exceptions."""
    trace_id = get_trace_id()
    logger.error(
        "unhandled_exception",
        error=str(exc),
        error_type=type(exc).__name__,
        url=str(request.url),
    )

    return JSONResponse(
        status_code=500,
        content=ErrorPayload(
            error_code=ErrorCodes.INTERNAL_ERROR,
            message="An unexpected error occurred",
            details={"error_type": type(exc).__name__},
            trace_id=trace_id,
            retryable=False,
        ).model_dump(),
    )


# Register routers
app.include_router(plan_router, prefix="/api/report-writer")
app.include_router(retrieve_router, prefix="/api/report-writer")
app.include_router(write_router, prefix="/api/report-writer")
app.include_router(revise_router, prefix="/api/report-writer")
app.include_router(consistency_router, prefix="/api/report-writer")


@app.get("/health")
async def health_check() -> dict[str, Any]:
    """Health check endpoint."""
    # Check DeerFlow integration
    try:
        from deerflow.config import get_app_config
        from app.config import get_writing_service_config

        app_config = get_app_config()
        ws_config = get_writing_service_config()

        return {
            "status": "healthy",
            "service": "writing-service",
            "version": "1.0.0",
            "integration": "deerflow",
            "models_available": len(app_config.models),
            "config": {
                "model_heavy": ws_config.model_heavy,
                "model_standard": ws_config.model_standard,
                "model_light": ws_config.model_light,
            },
        }
    except Exception as e:
        return {
            "status": "degraded",
            "service": "writing-service",
            "version": "1.0.0",
            "error": str(e),
        }


@app.get("/")
async def root() -> dict[str, Any]:
    """Root endpoint with service info."""
    return {
        "service": "Writing Service",
        "version": "1.0.0",
        "integration": "DeerFlow",
        "endpoints": {
            "plan": "/api/report-writer/plan",
            "retrieve_plan": "/api/report-writer/retrieve/plan",
            "retrieve_evaluate": "/api/report-writer/retrieve/evaluate",
            "write": "/api/report-writer/write",
            "revise": "/api/report-writer/revise",
            "consistency": "/api/report-writer/consistency",
            "health": "/health",
        },
    }
