"""
API route definitions
"""

from fastapi import APIRouter
from api.endpoints import collections, indexing, search, chat, documents, system, classification

# Create main router
router = APIRouter()

# Include all endpoint routers
router.include_router(system.router, prefix="/system", tags=["system"])

router.include_router(collections.router, prefix="/collections", tags=["collections"])

router.include_router(indexing.router, prefix="/indexing", tags=["indexing"])

router.include_router(search.router, prefix="/search", tags=["search"])

router.include_router(chat.router, prefix="/chat", tags=["chat"])

router.include_router(documents.router, prefix="/documents", tags=["documents"])

router.include_router(classification.router, prefix="/classification", tags=["classification"])
