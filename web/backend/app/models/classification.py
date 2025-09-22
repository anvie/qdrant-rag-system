"""
SQLAlchemy models for text classification system.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, JSON
from sqlalchemy.sql import func
from app.core.database import Base


class Category(Base):
    """Model for classification categories."""

    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    sample_texts = Column(JSON, nullable=False)  # List of sample texts for this category
    embedding = Column(JSON)  # Cached average embedding vector
    model_name = Column(String(255))  # Model used to generate the embedding
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<Category(name='{self.name}', samples={len(self.sample_texts or [])})>"