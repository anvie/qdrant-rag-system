"""
Chat database models for conversation tracking and message history.
"""

from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
    Text,
    Float,
    Boolean,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import json
import uuid

from app.core.database import Base


class ChatSession(Base):
    """Chat session model for conversation tracking."""

    __tablename__ = "chat_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(200), default="New Conversation")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # RAG Configuration
    collection_name = Column(String(100), default="articles")
    llm_model = Column(String(100), default="llama2")
    embedding_model = Column(String(100), default="embeddinggemma:latest")
    temperature = Column(Float, default=0.7)
    top_k = Column(Integer, default=5)
    min_score = Column(Float, default=0.5)
    max_context_length = Column(Integer, default=3000)
    max_tokens = Column(Integer, default=2000)

    # System configuration
    system_prompt = Column(Text, nullable=True)
    show_sources = Column(Boolean, default=True)

    # Relationships
    messages = relationship(
        "ChatMessage", back_populates="session", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        """Convert session to dictionary."""
        # Use cached data if available to avoid DetachedInstanceError
        cached_data = getattr(self, "_loaded_data", None)
        if cached_data:
            result = cached_data.copy()
            # Format dates
            if result.get("created_at"):
                result["created_at"] = result["created_at"].isoformat()
            if result.get("updated_at"):
                result["updated_at"] = result["updated_at"].isoformat()
            # Add message count
            result["message_count"] = getattr(self, "_message_count", 0)
            return result

        # Fallback to direct access with exception handling
        try:
            message_count = getattr(self, "_message_count", None)
            if message_count is None:
                try:
                    message_count = len(self.messages) if self.messages else 0
                except Exception:
                    message_count = 0

            return {
                "id": self.id,
                "title": self.title,
                "created_at": self.created_at.isoformat() if self.created_at else None,
                "updated_at": self.updated_at.isoformat() if self.updated_at else None,
                "collection_name": self.collection_name,
                "llm_model": self.llm_model,
                "embedding_model": self.embedding_model,
                "temperature": self.temperature,
                "top_k": self.top_k,
                "min_score": self.min_score,
                "max_context_length": self.max_context_length,
                "max_tokens": self.max_tokens,
                "system_prompt": self.system_prompt,
                "show_sources": self.show_sources,
                "message_count": message_count,
            }
        except Exception as e:
            # If all else fails, return minimal data using internal dict
            cached_data = getattr(self, "_loaded_data", {})
            return {
                "id": cached_data.get("id", "unknown"),
                "title": cached_data.get("title", "Error loading session"),
                "created_at": None,
                "updated_at": None,
                "collection_name": cached_data.get("collection_name", "articles"),
                "llm_model": cached_data.get("llm_model", "llama2"),
                "embedding_model": cached_data.get(
                    "embedding_model", "embeddinggemma:latest"
                ),
                "temperature": cached_data.get("temperature", 0.7),
                "top_k": cached_data.get("top_k", 5),
                "min_score": cached_data.get("min_score", 0.5),
                "max_context_length": cached_data.get("max_context_length", 3000),
                "max_tokens": cached_data.get("max_tokens", 2000),
                "system_prompt": cached_data.get("system_prompt"),
                "show_sources": cached_data.get("show_sources", True),
                "message_count": getattr(self, "_message_count", 0),
            }


class ChatMessage(Base):
    """Chat message model for storing conversation messages."""

    __tablename__ = "chat_messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("chat_sessions.id"), nullable=False)
    role = Column(String(20), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Metadata for assistant messages
    response_time_ms = Column(Integer, nullable=True)
    token_count = Column(Integer, nullable=True)

    # RAG-specific fields
    context_sources = Column(Text, nullable=True)  # JSON string of sources
    search_query = Column(
        Text, nullable=True
    )  # Original search query for assistant messages

    # Relationships
    session = relationship("ChatSession", back_populates="messages")

    def to_dict(self) -> dict:
        """Convert message to dictionary."""
        try:
            sources = None
            if self.context_sources:
                try:
                    sources = json.loads(self.context_sources)
                except json.JSONDecodeError:
                    sources = None

            return {
                "id": self.id,
                "session_id": self.session_id,
                "role": self.role,
                "content": self.content,
                "created_at": self.created_at.isoformat() if self.created_at else None,
                "response_time_ms": self.response_time_ms,
                "token_count": self.token_count,
                "sources": sources,
                "search_query": self.search_query,
            }
        except Exception as e:
            # Fallback for DetachedInstanceError
            return {
                "id": "unknown",
                "session_id": "unknown",
                "role": "assistant",
                "content": "Error loading message",
                "created_at": None,
                "response_time_ms": None,
                "token_count": None,
                "sources": None,
                "search_query": None,
            }

    def set_sources(self, sources: list):
        """Set context sources as JSON string."""
        if sources:
            self.context_sources = json.dumps(sources)
        else:
            self.context_sources = None

    def get_sources(self) -> list:
        """Get context sources from JSON string."""
        if self.context_sources:
            try:
                return json.loads(self.context_sources)
            except json.JSONDecodeError:
                return []
        return []
