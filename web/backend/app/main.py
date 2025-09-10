#!/usr/bin/env python3
"""
FastAPI backend for Qdrant RAG System Web UI
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import uvicorn
import logging

import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from api.routes import router
from core.config import settings
from core.websocket import websocket_manager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("🚀 Starting Qdrant RAG Web UI")
    logger.info(f"API docs available at: {settings.API_V1_STR}/docs")
    yield
    # Shutdown
    logger.info("👋 Shutting down Qdrant RAG Web UI")


# Create FastAPI app
app = FastAPI(
    title="Qdrant RAG Web UI",
    description="Web interface for managing Qdrant RAG operations",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix=settings.API_V1_STR)

# Serve static files in production
if settings.SERVE_STATIC:
    app.mount("/", StaticFiles(directory="static", html=True), name="static")


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"message": "Qdrant RAG Web UI API", "version": "1.0.0", "status": "healthy"}


@app.get("/health")
async def health_check():
    """Detailed health check."""
    return {
        "status": "healthy",
        "qdrant_url": settings.QDRANT_URL,
        "ollama_url": settings.OLLAMA_URL,
    }


@app.websocket("/ws/system")
async def system_websocket(websocket: WebSocket):
    """WebSocket for system status updates."""
    client_id = "system_monitor"
    await websocket_manager.connect(websocket, client_id)
    try:
        while True:
            # Send periodic system status updates
            await websocket.receive_text()
            # For now, just echo back
            await websocket_manager.send_personal_message(
                "System status update", client_id
            )
    except WebSocketDisconnect:
        websocket_manager.disconnect(client_id)
        logger.info(f"System monitor disconnected")


@app.websocket("/ws/collections")
async def collections_websocket(websocket: WebSocket):
    """WebSocket for collections updates."""
    client_id = "collections_monitor"
    await websocket_manager.connect(websocket, client_id)
    try:
        while True:
            await websocket.receive_text()
            # For now, just echo back
            await websocket_manager.send_personal_message(
                "Collections update", client_id
            )
    except WebSocketDisconnect:
        websocket_manager.disconnect(client_id)
        logger.info(f"Collections monitor disconnected")


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """Main WebSocket endpoint."""
    await websocket_manager.connect(websocket, client_id)
    try:
        while True:
            data = await websocket.receive_text()
            await websocket_manager.send_personal_message(f"Echo: {data}", client_id)
    except WebSocketDisconnect:
        websocket_manager.disconnect(client_id)
        logger.info(f"Client {client_id} disconnected")


@app.websocket("/ws/indexing/{job_id}")
async def indexing_websocket(websocket: WebSocket, job_id: str):
    """WebSocket for indexing progress updates."""
    await websocket_manager.connect(websocket, job_id)
    try:
        while True:
            await websocket.receive_text()
            # Job progress will be sent from background tasks
    except WebSocketDisconnect:
        websocket_manager.disconnect(job_id)


@app.websocket("/ws/chat/{session_id}")
async def chat_websocket(websocket: WebSocket, session_id: str):
    """WebSocket for streaming chat responses."""
    await websocket_manager.connect(websocket, session_id)
    try:
        while True:
            message = await websocket.receive_text()
            # Handle chat message and stream response
            await websocket_manager.send_personal_message(
                f"Processing: {message}", session_id
            )
    except WebSocketDisconnect:
        websocket_manager.disconnect(session_id)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info",
    )
