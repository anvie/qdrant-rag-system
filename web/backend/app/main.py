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
import json
from datetime import datetime

import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from api.routes import router
from core.config import settings
from core.websocket import websocket_manager
from core.database import init_database, DatabaseManager
from services.embedding_models import init_embedding_models

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("🚀 Starting Qdrant RAG Web UI")
    logger.info(f"API docs available at: {settings.API_V1_STR}/docs")

    # Initialize database
    logger.info("📊 Initializing database...")
    try:
        if init_database():
            logger.info("✅ Database initialized successfully")
        else:
            logger.error("❌ Database initialization failed")
    except Exception as e:
        logger.error(f"❌ Database initialization error: {e}")

    # Initialize embedding models
    logger.info("🤖 Initializing embedding models...")
    try:
        if init_embedding_models():
            logger.info("✅ Embedding models initialized successfully")
        else:
            logger.warning("⚠️ Embedding models initialization had issues")
    except Exception as e:
        logger.error(f"❌ Embedding models initialization error: {e}")

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
    # Check database health
    db_health = DatabaseManager.health_check()

    return {
        "status": "healthy",
        "qdrant_url": settings.QDRANT_URL,
        "ollama_url": settings.OLLAMA_URL,
        "database": db_health,
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

    # Import chat service here to avoid circular imports
    from app.services.chat_service import get_chat_service

    chat_service = get_chat_service()

    try:
        # Send connection confirmation
        await websocket_manager.send_personal_message(
            json.dumps(
                {
                    "type": "connected",
                    "data": {
                        "session_id": session_id,
                        "timestamp": datetime.now().isoformat(),
                    },
                }
            ),
            session_id,
        )

        while True:
            # Receive message from client
            message_data = await websocket.receive_text()
            logger.info(f"[WebSocket] Received message: {message_data}")

            try:
                # Parse incoming message
                message = json.loads(message_data)
                message_type = message.get("type", "message")
                message_content = message.get("data", {})
                logger.info(
                    f"[WebSocket] Message type: {message_type}, content: {message_content}"
                )

                if message_type == "message":
                    # Handle chat message
                    user_message = message_content.get("message", "")
                    if not user_message.strip():
                        logger.warning("[WebSocket] Empty message received, skipping")
                        continue

                    logger.info(f"[WebSocket] Processing user message: {user_message}")

                    # Verify session exists or create if needed
                    session = await chat_service.get_session(session_id)
                    if not session:
                        logger.info(
                            f"[WebSocket] Session {session_id} not found, creating new session"
                        )
                        # Create new session
                        session = await chat_service.create_session(
                            title="WebSocket Chat"
                        )
                        # Update session_id in websocket manager
                        websocket_manager.disconnect(session_id)
                        session_id = session.id
                        await websocket_manager.connect(websocket, session_id)
                        logger.info(f"[WebSocket] New session created: {session_id}")

                    # Add user message to database
                    logger.info(
                        f"[WebSocket] Adding user message to session {session_id}"
                    )
                    await chat_service.add_user_message(session_id, user_message)

                    # Stream response
                    try:
                        logger.info(
                            f"[WebSocket] Starting streaming response for session {session_id}"
                        )
                        chunk_count = 0
                        async for chunk in chat_service.generate_streaming_response(
                            session_id, user_message
                        ):
                            chunk_count += 1
                            logger.debug(
                                f"[WebSocket] Sending chunk {chunk_count}: {str(chunk)[:100]}..."
                            )
                            await websocket_manager.send_personal_message(
                                json.dumps(chunk), session_id
                            )
                        logger.info(
                            f"[WebSocket] Streaming complete, sent {chunk_count} chunks"
                        )
                    except Exception as e:
                        logger.error(f"Chat streaming error: {e}")
                        await websocket_manager.send_personal_message(
                            json.dumps({"type": "error", "data": {"error": str(e)}}),
                            session_id,
                        )

                elif message_type == "ping":
                    # Respond to ping with pong
                    await websocket_manager.send_personal_message(
                        json.dumps(
                            {
                                "type": "pong",
                                "data": {"timestamp": datetime.now().isoformat()},
                            }
                        ),
                        session_id,
                    )

                elif message_type == "typing":
                    # Handle typing indicator (optional feature)
                    typing_status = message_content.get("status", False)
                    # Could broadcast to other clients in future multi-user chats
                    pass

                else:
                    # Unknown message type
                    await websocket_manager.send_personal_message(
                        json.dumps(
                            {
                                "type": "error",
                                "data": {
                                    "error": f"Unknown message type: {message_type}"
                                },
                            }
                        ),
                        session_id,
                    )

            except json.JSONDecodeError:
                # Handle plain text messages for backward compatibility
                user_message = message_data.strip()
                if user_message:
                    # Verify session exists
                    session = await chat_service.get_session(session_id)
                    if not session:
                        session = await chat_service.create_session(
                            title="WebSocket Chat"
                        )
                        websocket_manager.disconnect(session_id)
                        session_id = session.id
                        await websocket_manager.connect(websocket, session_id)

                    # Add user message
                    await chat_service.add_user_message(session_id, user_message)

                    # Stream response
                    async for chunk in chat_service.generate_streaming_response(
                        session_id, user_message
                    ):
                        await websocket_manager.send_personal_message(
                            json.dumps(chunk), session_id
                        )

            except Exception as e:
                logger.error(f"WebSocket message processing error: {e}")
                await websocket_manager.send_personal_message(
                    json.dumps({"type": "error", "data": {"error": str(e)}}), session_id
                )

    except WebSocketDisconnect:
        websocket_manager.disconnect(session_id)
        logger.info(f"Chat WebSocket disconnected: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        websocket_manager.disconnect(session_id)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info",
    )
