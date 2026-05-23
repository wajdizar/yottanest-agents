"""API endpoints for the Writing Service."""

from app.endpoints.plan import router as plan_router
from app.endpoints.retrieve import router as retrieve_router
from app.endpoints.write import router as write_router
from app.endpoints.revise import router as revise_router
from app.endpoints.consistency import router as consistency_router

__all__ = [
    "plan_router",
    "retrieve_router",
    "write_router",
    "revise_router",
    "consistency_router",
]
