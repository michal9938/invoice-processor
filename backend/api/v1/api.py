"""
Main API router setup for versioning
Combines all v1 endpoints into a single router
"""
from fastapi import APIRouter
from backend.api.v1.endpoints import invoice, validation

# Create main API router for v1
api_router = APIRouter()

# Include endpoint routers
api_router.include_router(invoice.router, prefix="/invoices", tags=["invoices"])
api_router.include_router(validation.router, prefix="/validation", tags=["validation"])

