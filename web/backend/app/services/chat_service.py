"""
Chat service using raw SQL queries instead of SQLAlchemy ORM.
Much more reliable and avoids DetachedInstanceError issues.
"""

import asyncio
import sqlite3
import json
import time
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any, AsyncGenerator
import logging

from app.core.config import settings
from app.services.rag_core import (
    async_embed_one_ollama,
    async_search_qdrant_hybrid,
    build_rag_prompt,
    create_session as create_http_session,
    async_stream_llm_response,
    generate_llm_response,
)
from qdrant_client import QdrantClient

logger = logging.getLogger(__name__)


class ChatService:
    """Chat service using raw SQL for better performance and reliability."""

    def __init__(self, db_path: str = "./qdrant_web.db"):
        self.db_path = db_path
        self.http_session = create_http_session()
        self.qdrant_client = QdrantClient(url=settings.QDRANT_URL, timeout=60.0)
        self._init_tables()

    def _init_tables(self):
        """Initialize chat tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        try:
            # Create chat_sessions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    collection_name TEXT,
                    llm_model TEXT,
                    embedding_model TEXT,
                    temperature REAL,
                    top_k INTEGER,
                    min_score REAL,
                    max_context_length INTEGER,
                    max_tokens INTEGER,
                    system_prompt TEXT,
                    show_sources INTEGER
                )
            """)

            # Create chat_messages table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id TEXT PRIMARY KEY,
                    session_id TEXT,
                    role TEXT,
                    content TEXT,
                    created_at TEXT,
                    response_time_ms INTEGER,
                    token_count INTEGER,
                    context_sources TEXT,
                    search_query TEXT,
                    FOREIGN KEY (session_id) REFERENCES chat_sessions (id)
                )
            """)

            conn.commit()
        finally:
            conn.close()

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
    ) -> Dict[str, Any]:
        """Create a new chat session."""
        if not embedding_model:
            embedding_model = settings.EMBEDDING_MODEL

        session_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                INSERT INTO chat_sessions (
                    id, title, created_at, updated_at, collection_name,
                    llm_model, embedding_model, temperature, top_k, min_score,
                    max_context_length, max_tokens, system_prompt, show_sources
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    session_id,
                    title,
                    now,
                    now,
                    collection_name,
                    llm_model,
                    embedding_model,
                    temperature,
                    top_k,
                    min_score,
                    max_context_length,
                    max_tokens,
                    system_prompt,
                    1 if show_sources else 0,
                ),
            )
            conn.commit()
        finally:
            conn.close()

        return {
            "id": session_id,
            "title": title,
            "created_at": now,
            "updated_at": now,
            "collection_name": collection_name,
            "llm_model": llm_model,
            "embedding_model": embedding_model,
            "temperature": temperature,
            "top_k": top_k,
            "min_score": min_score,
            "max_context_length": max_context_length,
            "max_tokens": max_tokens,
            "system_prompt": system_prompt,
            "show_sources": show_sources,
            "message_count": 0,
        }

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session by ID."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT * FROM chat_sessions WHERE id = ?", (session_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None

            # Get column names
            columns = [desc[0] for desc in cursor.description]
            session_dict = dict(zip(columns, row))

            # Convert show_sources back to boolean
            session_dict["show_sources"] = bool(session_dict["show_sources"])

            # Get message count
            cursor = conn.execute(
                "SELECT COUNT(*) FROM chat_messages WHERE session_id = ?", (session_id,)
            )
            message_count = cursor.fetchone()[0]
            session_dict["message_count"] = message_count

            return session_dict
        finally:
            conn.close()

    async def list_sessions(
        self, limit: int = 50, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List chat sessions ordered by most recent."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                """
                SELECT *, (
                    SELECT COUNT(*) FROM chat_messages 
                    WHERE chat_messages.session_id = chat_sessions.id
                ) as message_count
                FROM chat_sessions 
                ORDER BY updated_at DESC 
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            )

            columns = [desc[0] for desc in cursor.description]
            sessions = []
            for row in cursor.fetchall():
                session_dict = dict(zip(columns, row))
                session_dict["show_sources"] = bool(session_dict["show_sources"])
                sessions.append(session_dict)

            return sessions
        finally:
            conn.close()

    async def delete_session(self, session_id: str) -> bool:
        """Delete chat session and all its messages."""
        conn = sqlite3.connect(self.db_path)
        try:
            # Delete messages first (foreign key)
            conn.execute(
                "DELETE FROM chat_messages WHERE session_id = ?", (session_id,)
            )
            # Delete session
            cursor = conn.execute(
                "DELETE FROM chat_sessions WHERE id = ?", (session_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    async def get_session_messages(
        self, session_id: str, limit: int = 100, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get messages for a chat session."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                """
                SELECT * FROM chat_messages 
                WHERE session_id = ? 
                ORDER BY created_at ASC 
                LIMIT ? OFFSET ?
                """,
                (session_id, limit, offset),
            )

            columns = [desc[0] for desc in cursor.description]
            messages = []
            for row in cursor.fetchall():
                message_dict = dict(zip(columns, row))

                # Parse JSON sources if present
                if message_dict["context_sources"]:
                    try:
                        message_dict["sources"] = json.loads(
                            message_dict["context_sources"]
                        )
                    except json.JSONDecodeError:
                        message_dict["sources"] = None
                else:
                    message_dict["sources"] = None

                # Remove the raw JSON field
                del message_dict["context_sources"]
                messages.append(message_dict)

            return messages
        finally:
            conn.close()

    async def add_user_message(self, session_id: str, content: str) -> Dict[str, Any]:
        """Add a user message to the session."""
        message_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        conn = sqlite3.connect(self.db_path)
        try:
            # Update session timestamp
            conn.execute(
                "UPDATE chat_sessions SET updated_at = ? WHERE id = ?",
                (now, session_id),
            )

            # Insert message
            conn.execute(
                """
                INSERT INTO chat_messages (
                    id, session_id, role, content, created_at
                ) VALUES (?, ?, ?, ?, ?)
            """,
                (message_id, session_id, "user", content, now),
            )

            conn.commit()

            return {
                "id": message_id,
                "session_id": session_id,
                "role": "user",
                "content": content,
                "created_at": now,
                "response_time_ms": None,
                "sources": None,
                "search_query": None,
            }
        finally:
            conn.close()

    async def generate_response(
        self, session_id: str, user_message: str
    ) -> tuple[str, List[Dict[str, Any]], int]:
        """Generate RAG response for user message."""
        start_time = time.time()

        # Get session configuration
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # Step 1: Search for relevant context
        logger.info(
            f"Searching for context in collection: {session['collection_name']}"
        )

        try:
            # Generate embedding for the query
            query_vector = await async_embed_one_ollama(
                user_message,
                session["embedding_model"],
                settings.OLLAMA_URL,
                session=self.http_session,
            )

            # Search Qdrant for relevant context using hybrid search
            search_results = await async_search_qdrant_hybrid(
                client=self.qdrant_client,
                collection_name=session["collection_name"],
                query_text=user_message,
                query_vector=query_vector,
                limit=session["top_k"],
                min_score=session["min_score"],
            )
        except Exception as e:
            logger.error(f"Search failed: {e}")
            search_results = []

        # Step 2: Build RAG prompt with context
        sources = []
        if search_results:
            augmented_prompt, sources = build_rag_prompt(
                user_message, search_results, session["max_context_length"]
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
                model=session["llm_model"],
                ollama_url=settings.OLLAMA_URL,
                temperature=session["temperature"],
                max_tokens=session["max_tokens"],
                system_prompt=session["system_prompt"],
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
        """Generate streaming RAG response for user message."""
        logger.info(
            f"[ChatService] Starting streaming response for session {session_id}, message: {user_message}"
        )
        start_time = time.time()

        # Get session configuration
        session = await self.get_session(session_id)
        if not session:
            logger.error(f"[ChatService] Session {session_id} not found")
            raise ValueError(f"Session {session_id} not found")

        logger.info(
            f"[ChatService] Session config - model: {session['llm_model']}, collection: {session['collection_name']}"
        )

        # Yield status update
        yield {"type": "status", "data": "Searching for relevant context..."}

        # Step 1: Search for relevant context
        try:
            logger.info(
                f"[ChatService] Generating embedding with model: {session['embedding_model']}"
            )
            # Generate embedding for the query
            query_vector = await async_embed_one_ollama(
                user_message,
                session["embedding_model"],
                settings.OLLAMA_URL,
                session=self.http_session,
            )
            logger.info(
                f"[ChatService] Embedding generated, vector size: {len(query_vector)}"
            )

            # Search Qdrant for relevant context using hybrid search
            logger.info(
                f"[ChatService] Searching Qdrant collection: {session['collection_name']}"
            )
            search_results = await async_search_qdrant_hybrid(
                client=self.qdrant_client,
                collection_name=session["collection_name"],
                query_text=user_message,
                query_vector=query_vector,
                limit=session["top_k"],
                min_score=session["min_score"],
            )
            logger.info(
                f"[ChatService] Search complete, found {len(search_results)} results"
            )
        except Exception as e:
            logger.error(f"[ChatService] Search failed: {e}", exc_info=True)
            search_results = []

        # Step 2: Build RAG prompt
        sources = []
        if search_results:
            augmented_prompt, sources = build_rag_prompt(
                user_message, search_results, session["max_context_length"]
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
            logger.info(
                f"[ChatService] Starting LLM streaming with model: {session['llm_model']}"
            )
            chunk_count = 0
            async for chunk in async_stream_llm_response(
                prompt=augmented_prompt,
                model=session["llm_model"],
                ollama_url=settings.OLLAMA_URL,
                temperature=session["temperature"],
                max_tokens=session["max_tokens"],
                system_prompt=session["system_prompt"],
                session=self.http_session,
            ):
                chunk_count += 1
                logger.debug(
                    f"[ChatService] Streaming chunk {chunk_count}: {chunk[:50]}..."
                )
                full_response.append(chunk)
                yield {"type": "content", "data": chunk}
            logger.info(
                f"[ChatService] LLM streaming complete, {chunk_count} chunks sent"
            )
        except Exception as e:
            logger.error(
                f"[ChatService] Streaming LLM generation failed: {e}", exc_info=True
            )
            error_msg = f"I apologize, but I encountered an error: {str(e)}"
            full_response.append(error_msg)
            yield {"type": "content", "data": error_msg}

        response_time_ms = int((time.time() - start_time) * 1000)

        # Yield completion
        yield {
            "type": "complete",
            "data": {
                "response_time_ms": response_time_ms,
                "sources": sources if session["show_sources"] else [],
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
    ) -> Dict[str, Any]:
        """Store assistant message in database."""
        message_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        sources_json = json.dumps(sources) if sources else None

        conn = sqlite3.connect(self.db_path)
        try:
            # Update session timestamp and title if needed
            cursor = conn.execute(
                "SELECT COUNT(*) FROM chat_messages WHERE session_id = ?", (session_id,)
            )
            message_count = cursor.fetchone()[0]

            if message_count == 1:  # Only user message exists, update title
                title = (
                    search_query[:50] + "..."
                    if len(search_query) > 50
                    else search_query
                )
                conn.execute(
                    "UPDATE chat_sessions SET updated_at = ?, title = ? WHERE id = ?",
                    (now, title, session_id),
                )
            else:
                conn.execute(
                    "UPDATE chat_sessions SET updated_at = ? WHERE id = ?",
                    (now, session_id),
                )

            # Insert assistant message
            conn.execute(
                """
                INSERT INTO chat_messages (
                    id, session_id, role, content, created_at,
                    response_time_ms, context_sources, search_query
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    message_id,
                    session_id,
                    "assistant",
                    content,
                    now,
                    response_time_ms,
                    sources_json,
                    search_query,
                ),
            )

            conn.commit()

            return {
                "id": message_id,
                "session_id": session_id,
                "role": "assistant",
                "content": content,
                "created_at": now,
                "response_time_ms": response_time_ms,
                "sources": sources,
                "search_query": search_query,
            }
        finally:
            conn.close()

    async def update_session_settings(
        self, session_id: str, **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Update session settings."""
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

        updates = []
        values = []

        for key, value in kwargs.items():
            if key in allowed_fields:
                updates.append(f"{key} = ?")
                # Convert boolean to integer for show_sources
                if key == "show_sources":
                    value = 1 if value else 0
                values.append(value)

        if not updates:
            return await self.get_session(session_id)

        # Add updated_at and session_id
        updates.append("updated_at = ?")
        values.append(datetime.utcnow().isoformat())
        values.append(session_id)

        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                f"UPDATE chat_sessions SET {', '.join(updates)} WHERE id = ?", values
            )
            conn.commit()

            if cursor.rowcount == 0:
                return None

            return await self.get_session(session_id)
        finally:
            conn.close()

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
