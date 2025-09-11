"""
Chat service for RAG conversations with streaming support.
Integrates vector search, prompt augmentation, and LLM generation.
"""

import asyncio
import functools
import json
import time
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any, Generator, AsyncGenerator
import logging
import sys
import os

import requests
from sqlalchemy.orm import Session
from qdrant_client import QdrantClient

from app.core.config import settings
from app.core.database import get_db_session
from app.models.chat import ChatSession, ChatMessage
from app.services.rag_core import (
    async_embed_one_ollama,
    async_search_qdrant_hybrid,
    build_rag_prompt,
    create_session as create_http_session,
    async_stream_llm_response,
    generate_llm_response,
)

# Configure logger
logger = logging.getLogger(__name__)


class ChatService:
    """Service for handling RAG chat operations with session management."""

    def __init__(self):
        self.http_session = create_http_session()
        self.qdrant_client = QdrantClient(url=settings.QDRANT_URL, timeout=60.0)

    async def create_session(
        self,
        title: str = "New Conversation",
        collection_name: str = "articles",
        llm_model: str = "llama2",
        embedding_model: Optional[str] = None,
        temperature: float = 0.7,
        top_k: int = 5,
        min_score: float = 0.5,
        max_context_length: int = 3000,
        max_tokens: int = 2000,
        system_prompt: Optional[str] = None,
        show_sources: bool = True,
    ) -> ChatSession:
        """Create a new chat session."""

        # Use default embedding model if not provided
        if not embedding_model:
            embedding_model = settings.EMBEDDING_MODEL

        session = ChatSession(
            title=title,
            collection_name=collection_name,
            llm_model=llm_model,
            embedding_model=embedding_model,
            temperature=temperature,
            top_k=top_k,
            min_score=min_score,
            max_context_length=max_context_length,
            max_tokens=max_tokens,
            system_prompt=system_prompt,
            show_sources=show_sources,
        )

        with get_db_session() as db:
            db.add(session)
            db.commit()
            db.refresh(session)
            # Ensure all attributes are loaded before session closes
            session_data = {
                "id": session.id,
                "title": session.title,
                "created_at": session.created_at,
                "updated_at": session.updated_at,
                "collection_name": session.collection_name,
                "llm_model": session.llm_model,
                "embedding_model": session.embedding_model,
                "temperature": session.temperature,
                "top_k": session.top_k,
                "min_score": session.min_score,
                "max_context_length": session.max_context_length,
                "max_tokens": session.max_tokens,
                "system_prompt": session.system_prompt,
                "show_sources": session.show_sources,
            }
            # Cache loaded data and message count
            session._loaded_data = session_data
            session._message_count = 0  # New session has no messages

        return session

    async def get_session(self, session_id: str) -> Optional[ChatSession]:
        """Get chat session by ID."""
        with get_db_session() as db:
            session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
            if session:
                # Cache data to avoid DetachedInstanceError
                session_data = {
                    "id": session.id,
                    "title": session.title,
                    "created_at": session.created_at,
                    "updated_at": session.updated_at,
                    "collection_name": session.collection_name,
                    "llm_model": session.llm_model,
                    "embedding_model": session.embedding_model,
                    "temperature": session.temperature,
                    "top_k": session.top_k,
                    "min_score": session.min_score,
                    "max_context_length": session.max_context_length,
                    "max_tokens": session.max_tokens,
                    "system_prompt": session.system_prompt,
                    "show_sources": session.show_sources,
                }
                session._loaded_data = session_data
                session._message_count = (
                    len(session.messages) if session.messages else 0
                )
            return session

    async def list_sessions(
        self, limit: int = 50, offset: int = 0
    ) -> List[ChatSession]:
        """List chat sessions ordered by most recent."""
        with get_db_session() as db:
            sessions = (
                db.query(ChatSession)
                .order_by(ChatSession.updated_at.desc())
                .limit(limit)
                .offset(offset)
                .all()
            )
            # Eagerly load all data to avoid DetachedInstanceError
            for session in sessions:
                session_data = {
                    "id": session.id,
                    "title": session.title,
                    "created_at": session.created_at,
                    "updated_at": session.updated_at,
                    "collection_name": session.collection_name,
                    "llm_model": session.llm_model,
                    "embedding_model": session.embedding_model,
                    "temperature": session.temperature,
                    "top_k": session.top_k,
                    "min_score": session.min_score,
                    "max_context_length": session.max_context_length,
                    "max_tokens": session.max_tokens,
                    "system_prompt": session.system_prompt,
                    "show_sources": session.show_sources,
                }
                session._loaded_data = session_data
                session._message_count = (
                    len(session.messages) if session.messages else 0
                )
            return sessions

    async def delete_session(self, session_id: str) -> bool:
        """Delete chat session and all its messages."""
        with get_db_session() as db:
            session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
            if session:
                db.delete(session)
                db.commit()
                return True
            return False

    async def get_session_messages(
        self, session_id: str, limit: int = 100, offset: int = 0
    ) -> List[ChatMessage]:
        """Get messages for a chat session."""
        with get_db_session() as db:
            return (
                db.query(ChatMessage)
                .filter(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at.asc())
                .limit(limit)
                .offset(offset)
                .all()
            )

    async def add_user_message(self, session_id: str, content: str) -> ChatMessage:
        """Add a user message to the session."""
        message = ChatMessage(
            session_id=session_id,
            role="user",
            content=content,
        )

        with get_db_session() as db:
            # Update session timestamp
            session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
            if session:
                session.updated_at = datetime.utcnow()

            db.add(message)
            db.commit()
            db.refresh(message)

        return message

    async def generate_response(
        self, session_id: str, user_message: str
    ) -> tuple[str, List[Dict[str, Any]], int]:
        """
        Generate RAG response for user message.

        Returns:
            Tuple of (response_text, sources, response_time_ms)
        """
        start_time = time.time()

        # Get session configuration
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # Step 1: Generate query embedding and search for relevant context
        logger.info(f"Searching for context in collection: {session.collection_name}")

        try:
            # Generate embedding for the query
            query_vector = await async_embed_one_ollama(
                user_message,
                session.embedding_model,
                settings.OLLAMA_URL,
                session=self.http_session,
            )

            # Search Qdrant for relevant context using hybrid search
            search_results = await async_search_qdrant_hybrid(
                client=self.qdrant_client,
                collection_name=session.collection_name,
                query_text=user_message,
                query_vector=query_vector,
                limit=session.top_k,
                min_score=session.min_score,
            )
        except Exception as e:
            logger.error(f"Search failed: {e}")
            search_results = []

        # Step 2: Build RAG prompt with context
        sources = []
        if search_results:
            # search_results is already in correct format from rag_core
            augmented_prompt, sources = build_rag_prompt(
                user_message, search_results, session.max_context_length
            )
        else:
            # No context found - direct response
            augmented_prompt = f"""Please answer the user's question. If you don't have enough information to provide a complete answer, please say so.

User Question: {user_message}

Please provide a helpful response:"""
            sources = []

        # Step 3: Generate LLM response
        try:
            response = generate_llm_response(
                prompt=augmented_prompt,
                model=session.llm_model,
                ollama_url=settings.OLLAMA_URL,
                temperature=session.temperature,
                max_tokens=session.max_tokens,
                system_prompt=session.system_prompt,
                session=self.http_session,
            )
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            response = f"I apologize, but I encountered an error generating a response: {str(e)}"

        response_time_ms = int((time.time() - start_time) * 1000)

        return response, sources, response_time_ms

    async def generate_streaming_response(
        self, session_id: str, user_message: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Generate streaming RAG response for user message.

        Yields dictionaries with response chunks and metadata.
        """
        start_time = time.time()

        # Get session configuration
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # Yield status update
        yield {"type": "status", "data": "Searching for relevant context..."}

        # Step 1: Generate query embedding and search for relevant context
        try:
            # Generate embedding for the query
            query_vector = await async_embed_one_ollama(
                user_message,
                session.embedding_model,
                settings.OLLAMA_URL,
                session=self.http_session,
            )

            # Search Qdrant for relevant context using hybrid search
            search_results = await async_search_qdrant_hybrid(
                client=self.qdrant_client,
                collection_name=session.collection_name,
                query_text=user_message,
                query_vector=query_vector,
                limit=session.top_k,
                min_score=session.min_score,
            )
        except Exception as e:
            logger.error(f"Search failed: {e}")
            search_results = []

        # Step 2: Build RAG prompt
        sources = []
        if search_results:
            # search_results is already in correct format from rag_core
            augmented_prompt, sources = build_rag_prompt(
                user_message, search_results, session.max_context_length
            )
        else:
            augmented_prompt = f"""Please answer the user's question. If you don't have enough information to provide a complete answer, please say so.

User Question: {user_message}

Please provide a helpful response:"""
            sources = []

        # Yield context information
        yield {
            "type": "context",
            "data": {"sources": sources, "context_found": len(sources) > 0},
        }

        # Yield status update
        yield {"type": "status", "data": "Generating response..."}

        # Step 3: Stream LLM response
        full_response = []
        try:
            async for chunk in async_stream_llm_response(
                prompt=augmented_prompt,
                model=session.llm_model,
                ollama_url=settings.OLLAMA_URL,
                temperature=session.temperature,
                max_tokens=session.max_tokens,
                system_prompt=session.system_prompt,
                session=self.http_session,
            ):
                full_response.append(chunk)
                yield {"type": "content", "data": chunk}
        except Exception as e:
            logger.error(f"Streaming LLM generation failed: {e}")
            error_msg = f"I apologize, but I encountered an error: {str(e)}"
            full_response.append(error_msg)
            yield {"type": "content", "data": error_msg}

        response_time_ms = int((time.time() - start_time) * 1000)

        # Yield completion
        show_sources = True  # Default to True
        if hasattr(session, "_loaded_data") and session._loaded_data:
            show_sources = session._loaded_data.get("show_sources", True)
        else:
            try:
                show_sources = session.show_sources
            except Exception:
                show_sources = True  # Fallback to True

        yield {
            "type": "complete",
            "data": {
                "response_time_ms": response_time_ms,
                "sources": sources if show_sources else [],
            },
        }

        # Store the complete response
        await self._store_assistant_message(
            session_id=session_id,
            content="".join(full_response),
            sources=sources,
            search_query=user_message,
            response_time_ms=response_time_ms,
        )

    async def _store_assistant_message(
        self,
        session_id: str,
        content: str,
        sources: List[Dict[str, Any]],
        search_query: str,
        response_time_ms: int,
    ) -> ChatMessage:
        """Store assistant message in database."""
        message = ChatMessage(
            session_id=session_id,
            role="assistant",
            content=content,
            search_query=search_query,
            response_time_ms=response_time_ms,
        )

        message.set_sources(sources)

        with get_db_session() as db:
            # Update session timestamp
            session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
            if session:
                session.updated_at = datetime.utcnow()
                # Update title if this is the first exchange
                if len(session.messages) == 1:  # Only user message exists
                    # Generate a title from the first user message
                    title = (
                        search_query[:50] + "..."
                        if len(search_query) > 50
                        else search_query
                    )
                    session.title = title

            db.add(message)
            db.commit()
            db.refresh(message)

        return message

    async def update_session_settings(
        self, session_id: str, **kwargs
    ) -> Optional[ChatSession]:
        """Update session settings."""
        with get_db_session() as db:
            session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
            if not session:
                return None

            # Update allowed fields
            allowed_fields = {
                "title",
                "collection_name",
                "llm_model",
                "embedding_model",
                "temperature",
                "top_k",
                "min_score",
                "max_context_length",
                "max_tokens",
                "system_prompt",
                "show_sources",
            }

            for key, value in kwargs.items():
                if key in allowed_fields and hasattr(session, key):
                    setattr(session, key, value)

            session.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(session)

            # Cache the updated data to avoid DetachedInstanceError
            session_data = {
                "id": session.id,
                "title": session.title,
                "created_at": session.created_at,
                "updated_at": session.updated_at,
                "collection_name": session.collection_name,
                "llm_model": session.llm_model,
                "embedding_model": session.embedding_model,
                "temperature": session.temperature,
                "top_k": session.top_k,
                "min_score": session.min_score,
                "max_context_length": session.max_context_length,
                "max_tokens": session.max_tokens,
                "system_prompt": session.system_prompt,
                "show_sources": session.show_sources,
            }
            session._loaded_data = session_data
            session._message_count = len(session.messages) if session.messages else 0

        return session

    def close(self):
        """Close HTTP session and cleanup."""
        if self.http_session:
            self.http_session.close()
        if self.qdrant_client:
            self.qdrant_client.close()


# Global chat service instance
_chat_service: Optional[ChatService] = None


def get_chat_service() -> ChatService:
    """Get or create global chat service instance."""
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service


def close_chat_service():
    """Close global chat service instance."""
    global _chat_service
    if _chat_service:
        _chat_service.close()
        _chat_service = None
