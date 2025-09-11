"""
Database models for collection metadata management.
"""

from sqlalchemy import Column, String, Integer, DateTime, Text, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional

Base = declarative_base()


class Collection(Base):
    """Collection metadata model for storing collection-specific configurations."""

    __tablename__ = "collections"

    # Primary fields
    name = Column(String(255), primary_key=True, index=True)
    embedding_model = Column(String(255), nullable=False)
    vector_size = Column(Integer, nullable=False)
    distance_metric = Column(String(50), nullable=False, default="cosine")

    # Metadata
    description = Column(Text, nullable=True)
    tags = Column(Text, nullable=True)  # JSON string for tags

    # Performance settings
    index_config = Column(Text, nullable=True)  # JSON string for custom index config

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Optional statistics (cached from Qdrant)
    points_count = Column(Integer, default=0)
    vectors_count = Column(Integer, default=0)
    status = Column(String(50), default="unknown")
    last_stats_update = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<Collection(name='{self.name}', model='{self.embedding_model}', size={self.vector_size})>"

    def to_dict(self):
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "embedding_model": self.embedding_model,
            "vector_size": self.vector_size,
            "distance_metric": self.distance_metric,
            "description": self.description,
            "tags": self.tags,
            "index_config": self.index_config,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "points_count": self.points_count,
            "vectors_count": self.vectors_count,
            "status": self.status,
            "last_stats_update": self.last_stats_update.isoformat()
            if self.last_stats_update
            else None,
        }

    @classmethod
    def from_dict(cls, data: dict):
        """Create instance from dictionary."""
        return cls(
            **{k: v for k, v in data.items() if k in cls.__table__.columns.keys()}
        )


class EmbeddingModel(Base):
    """Embedding model registry for tracking available models and their specifications."""

    __tablename__ = "embedding_models"

    # Model identification
    name = Column(String(255), primary_key=True, index=True)
    display_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Model specifications
    vector_size = Column(Integer, nullable=False)
    model_type = Column(
        String(100), nullable=True
    )  # e.g., "sentence-transformer", "ollama"
    provider = Column(String(100), nullable=True)  # e.g., "ollama", "huggingface"

    # Performance characteristics
    max_sequence_length = Column(Integer, nullable=True)
    processing_speed = Column(Float, nullable=True)  # tokens/second or similar metric
    memory_usage = Column(Integer, nullable=True)  # MB

    # Capabilities
    supports_similarity = Column(String(10), default="yes")  # yes/no/limited
    supports_classification = Column(String(10), default="yes")
    supports_clustering = Column(String(10), default="yes")
    supports_multilingual = Column(String(10), default="no")

    # Status
    is_available = Column(String(10), default="unknown")  # yes/no/unknown
    is_tested = Column(String(10), default="no")

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    last_checked = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<EmbeddingModel(name='{self.name}', size={self.vector_size}, provider='{self.provider}')>"

    def to_dict(self):
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "vector_size": self.vector_size,
            "model_type": self.model_type,
            "provider": self.provider,
            "max_sequence_length": self.max_sequence_length,
            "processing_speed": self.processing_speed,
            "memory_usage": self.memory_usage,
            "supports_similarity": self.supports_similarity,
            "supports_classification": self.supports_classification,
            "supports_clustering": self.supports_clustering,
            "supports_multilingual": self.supports_multilingual,
            "is_available": self.is_available,
            "is_tested": self.is_tested,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_checked": self.last_checked.isoformat()
            if self.last_checked
            else None,
        }
