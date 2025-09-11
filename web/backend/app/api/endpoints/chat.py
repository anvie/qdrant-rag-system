"""
Chat endpoints for RAG conversations
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import json

import traceback

from app.services.chat_service import get_chat_service
from app.models.chat import ChatSession

router = APIRouter()
chat_service = get_chat_service()


# Pydantic models
class ChatMessage(BaseModel):
    """Chat message model for API responses."""

    id: str
    session_id: str
    role: str
    content: str
    created_at: str
    response_time_ms: Optional[int] = None
    sources: Optional[List[Dict[str, Any]]] = None
    search_query: Optional[str] = None


class ChatSession(BaseModel):
    """Chat session model for API responses."""

    id: str
    title: str
    created_at: str
    updated_at: str
    collection_name: str
    llm_model: str
    embedding_model: str
    temperature: float
    top_k: int
    min_score: float
    max_context_length: int
    max_tokens: int
    system_prompt: Optional[str] = None
    show_sources: bool
    message_count: int


class CreateSessionRequest(BaseModel):
    """Request model for creating a new chat session."""

    title: Optional[str] = "New Conversation"
    collection_name: str = "articles"
    llm_model: str = "llama2"
    embedding_model: Optional[str] = None
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    top_k: int = Field(default=5, ge=1, le=20)
    min_score: float = Field(default=0.5, ge=0.0, le=1.0)
    max_context_length: int = Field(default=3000, ge=500, le=8000)
    max_tokens: int = Field(default=2000, ge=100, le=4000)
    system_prompt: Optional[str] = None
    show_sources: bool = True


class UpdateSessionRequest(BaseModel):
    """Request model for updating session settings."""

    title: Optional[str] = None
    collection_name: Optional[str] = None
    llm_model: Optional[str] = None
    embedding_model: Optional[str] = None
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    top_k: Optional[int] = Field(default=None, ge=1, le=20)
    min_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    max_context_length: Optional[int] = Field(default=None, ge=500, le=8000)
    max_tokens: Optional[int] = Field(default=None, ge=100, le=4000)
    system_prompt: Optional[str] = None
    show_sources: Optional[bool] = None


class SendMessageRequest(BaseModel):
    """Request model for sending a message."""

    message: str = Field(min_length=1, max_length=2000)
    stream: bool = False


class ChatResponse(BaseModel):
    """Response model for chat messages."""

    message: ChatMessage
    sources: Optional[List[Dict[str, Any]]] = None


# Session endpoints
@router.post("/sessions", response_model=ChatSession)
async def create_session(request: CreateSessionRequest):
    """Create a new chat session."""
    try:
        session = await chat_service.create_session(**request.dict())
        return session
    except Exception as e:
        traceback.print_exception(type(e), e, e.__traceback__)
        raise HTTPException(
            status_code=500, detail=f"Failed to create session: {str(e)}"
        )


@router.get("/sessions", response_model=List[ChatSession])
async def list_sessions(limit: int = 50, offset: int = 0):
    """List chat sessions."""
    try:
        sessions = await chat_service.list_sessions(limit=limit, offset=offset)
        return sessions
    except Exception as e:
        traceback.print_exception(type(e), e, e.__traceback__)
        raise HTTPException(
            status_code=500, detail=f"Failed to list sessions: {str(e)}"
        )


@router.get("/sessions/{session_id}", response_model=ChatSession)
async def get_session(session_id: str):
    """Get a specific chat session."""
    try:
        session = await chat_service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return session
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exception(type(e), e, e.__traceback__)
        raise HTTPException(status_code=500, detail=f"Failed to get session: {str(e)}")


@router.put("/sessions/{session_id}", response_model=ChatSession)
async def update_session(session_id: str, request: UpdateSessionRequest):
    """Update session settings."""
    try:
        # Filter out None values
        update_data = {k: v for k, v in request.dict().items() if v is not None}

        session = await chat_service.update_session_settings(session_id, **update_data)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return session
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exception(type(e), e, e.__traceback__)
        raise HTTPException(
            status_code=500, detail=f"Failed to update session: {str(e)}"
        )


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a chat session."""
    try:
        success = await chat_service.delete_session(session_id)
        if not success:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"message": "Session deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exception(type(e), e, e.__traceback__)
        raise HTTPException(
            status_code=500, detail=f"Failed to delete session: {str(e)}"
        )


# Message endpoints
@router.get("/sessions/{session_id}/messages", response_model=List[ChatMessage])
async def get_session_messages(session_id: str, limit: int = 100, offset: int = 0):
    """Get messages for a chat session."""
    try:
        # Verify session exists
        session = await chat_service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        messages = await chat_service.get_session_messages(
            session_id, limit=limit, offset=offset
        )
        return [message for message in messages]
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exception(type(e), e, e.__traceback__)
        raise HTTPException(status_code=500, detail=f"Failed to get messages: {str(e)}")


@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: str, request: SendMessageRequest, background_tasks: BackgroundTasks
):
    """Send a message to the chat session."""
    try:
        # Verify session exists
        session = await chat_service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Add user message
        user_message = await chat_service.add_user_message(session_id, request.message)

        if request.stream:
            # Return streaming response
            async def generate_stream():
                try:
                    async for chunk in chat_service.generate_streaming_response(
                        session_id, request.message
                    ):
                        yield f"data: {json.dumps(chunk)}\n\n"
                except Exception as e:
                    traceback.print_exception(type(e), e, e.__traceback__)
                    error_chunk = {"type": "error", "data": {"error": str(e)}}
                    yield f"data: {json.dumps(error_chunk)}\n\n"

                # Send completion signal
                yield "data: [DONE]\n\n"

            return StreamingResponse(
                generate_stream(),
                media_type="text/plain",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Content-Type": "text/plain; charset=utf-8",
                },
            )
        else:
            # Generate non-streaming response
            (
                response_text,
                sources,
                response_time_ms,
            ) = await chat_service.generate_response(session_id, request.message)

            # Store assistant message
            assistant_message = await chat_service._store_assistant_message(
                session_id=session_id,
                content=response_text,
                sources=sources,
                search_query=request.message,
                response_time_ms=response_time_ms,
            )

            return ChatResponse(
                message=assistant_message.to_dict(),
                sources=sources if session.show_sources else None,
            )

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exception(type(e), e, e.__traceback__)
        raise HTTPException(status_code=500, detail=f"Failed to send message: {str(e)}")


# Legacy endpoints for backward compatibility
@router.post("/", response_model=ChatResponse)
async def send_message_legacy(request: SendMessageRequest):
    """Legacy endpoint - creates a temporary session."""
    try:
        # Create temporary session
        session = await chat_service.create_session(title="Quick Chat")

        # Add user message and generate response
        user_message = await chat_service.add_user_message(session.id, request.message)
        response_text, sources, response_time_ms = await chat_service.generate_response(
            session.id, request.message
        )

        # Store assistant message
        assistant_message = await chat_service._store_assistant_message(
            session_id=session.id,
            content=response_text,
            sources=sources,
            search_query=request.message,
            response_time_ms=response_time_ms,
        )

        return ChatResponse(
            message=assistant_message.to_dict(),
            sources=sources if session.show_sources else None,
        )

    except Exception as e:
        traceback.print_exception(type(e), e, e.__traceback__)
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


@router.get("/conversations")
async def get_conversations():
    """Legacy endpoint - returns list of sessions."""
    try:
        sessions = await chat_service.list_sessions(limit=20)
        return {
            "conversations": [
                {
                    "id": session.id,
                    "title": session.title,
                    "created_at": session.created_at.isoformat()
                    if session.created_at
                    else None,
                    "updated_at": session.updated_at.isoformat()
                    if session.updated_at
                    else None,
                    "message_count": len(session.messages) if session.messages else 0,
                }
                for session in sessions
            ]
        }
    except Exception as e:
        traceback.print_exception(type(e), e, e.__traceback__)
        raise HTTPException(
            status_code=500, detail=f"Failed to get conversations: {str(e)}"
        )
