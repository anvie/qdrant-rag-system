#!/usr/bin/env python3
"""
Embedding text formatter module for different embedding models.

This module provides automatic format detection and text formatting functions
that can be reused across indexing scripts, web backends, and search applications.
"""

from typing import Optional, Dict, Callable
import re


class EmbeddingFormatter:
    """
    Handles text formatting for different embedding models with automatic format detection.
    """

    # Model format mappings
    MODEL_FORMATS = {
        # EmbeddingGemma variants
        "embeddinggemma": "gemma",
        "embedding-gemma": "gemma",
        "gemma": "gemma",
        # BGE variants
        "bge": "bge",
        "bge-m3": "bge",
        "bge-large": "bge",
        "bge-base": "bge",
        "bge-small": "bge",
        # Sentence transformers
        "sentence-transformers": "sentence_transformers",
        "all-minilm": "sentence_transformers",
        "all-mpnet": "sentence_transformers",
        # OpenAI
        "text-embedding": "openai",
        "ada": "openai",
        # Default fallback
        "default": "default",
    }

    @classmethod
    def detect_model_format(cls, model_name: str) -> str:
        """
        Auto-detect embedding format based on model name.

        Args:
            model_name: Name of the embedding model (e.g., 'embeddinggemma:latest', 'bge-m3:567m')

        Returns:
            Format identifier: 'gemma', 'bge', 'sentence_transformers', 'openai', or 'default'
        """
        if not model_name:
            return "default"

        # Clean model name (remove version tags, convert to lowercase)
        clean_name = model_name.lower().strip()
        clean_name = re.sub(r"[:@].*$", "", clean_name)  # Remove :latest, @sha256, etc.
        clean_name = re.sub(
            r"[-_]?\d+[kmb]?$", "", clean_name
        )  # Remove size suffixes like -567m

        # Check for exact matches first
        if clean_name in cls.MODEL_FORMATS:
            return cls.MODEL_FORMATS[clean_name]

        # Check for partial matches
        for pattern, format_type in cls.MODEL_FORMATS.items():
            if pattern in clean_name:
                return format_type

        return "default"

    @classmethod
    def format_document_for_embedding(
        cls, title: str, content: str, model_format: str
    ) -> str:
        """
        Format document text according to model requirements.

        Args:
            title: Document title
            content: Document content
            model_format: Format type returned by detect_model_format()

        Returns:
            Formatted text ready for embedding
        """
        if model_format == "gemma":
            return cls._format_gemma_document(title, content)
        elif model_format == "bge":
            return cls._format_bge_document(title, content)
        elif model_format == "sentence_transformers":
            return cls._format_sentence_transformers_document(title, content)
        elif model_format == "openai":
            return cls._format_openai_document(title, content)
        else:
            return cls._format_default_document(title, content)

    @classmethod
    def format_query_for_embedding(
        cls, query: str, task_type: str, model_format: str
    ) -> str:
        """
        Format search query according to model requirements.

        Args:
            query: Search query text
            task_type: Type of task ('search', 'qa', 'classification', 'similarity', etc.)
            model_format: Format type returned by detect_model_format()

        Returns:
            Formatted query ready for embedding
        """
        if model_format == "gemma":
            return cls._format_gemma_query(query, task_type)
        elif model_format == "bge":
            return cls._format_bge_query(query, task_type)
        elif model_format == "sentence_transformers":
            return cls._format_sentence_transformers_query(query, task_type)
        elif model_format == "openai":
            return cls._format_openai_query(query, task_type)
        else:
            return cls._format_default_query(query, task_type)

    # EmbeddingGemma formatting methods
    @staticmethod
    def _format_gemma_document(title: str, content: str) -> str:
        """Format document for EmbeddingGemma model."""
        title_part = title.strip() if title and title.strip() else "none"
        return f"title: {title_part} | text: {content}"

    @staticmethod
    def _format_gemma_query(query: str, task_type: str) -> str:
        """Format query for EmbeddingGemma model."""
        # Map task types to EmbeddingGemma conventions
        task_mapping = {
            "search": "search result",
            "qa": "question answering",
            "question_answering": "question answering",
            "fact_checking": "fact checking",
            "classification": "classification",
            "clustering": "clustering",
            "similarity": "sentence similarity",
            "code": "code retrieval",
            "code_retrieval": "code retrieval",
        }

        gemma_task = task_mapping.get(task_type.lower(), "search result")
        return f"task: {gemma_task} | query: {query}"

    # BGE formatting methods
    @staticmethod
    def _format_bge_document(title: str, content: str) -> str:
        """Format document for BGE models."""
        if title and title.strip():
            return f"{title.strip()}\n\n{content}"
        return content

    @staticmethod
    def _format_bge_query(query: str, task_type: str) -> str:
        """Format query for BGE models."""
        # BGE typically works well with plain queries, but can add prefixes for specific tasks
        if task_type.lower() in ["search", "retrieval"]:
            return (
                f"查询: {query}"
                if any("\u4e00" <= char <= "\u9fff" for char in query)
                else query
            )
        return query

    # Sentence Transformers formatting methods
    @staticmethod
    def _format_sentence_transformers_document(title: str, content: str) -> str:
        """Format document for Sentence Transformers models."""
        if title and title.strip():
            return f"{title.strip()}: {content}"
        return content

    @staticmethod
    def _format_sentence_transformers_query(query: str, task_type: str) -> str:
        """Format query for Sentence Transformers models."""
        return query  # Usually work best with plain text

    # OpenAI formatting methods
    @staticmethod
    def _format_openai_document(title: str, content: str) -> str:
        """Format document for OpenAI embedding models."""
        if title and title.strip():
            return f"Title: {title.strip()}\n\nContent: {content}"
        return content

    @staticmethod
    def _format_openai_query(query: str, task_type: str) -> str:
        """Format query for OpenAI embedding models."""
        return query  # OpenAI models work well with plain queries

    # Default/fallback formatting methods
    @staticmethod
    def _format_default_document(title: str, content: str) -> str:
        """Default document formatting."""
        if title and title.strip():
            return f"# {title.strip()}\n\n{content}"
        return content

    @staticmethod
    def _format_default_query(query: str, task_type: str) -> str:
        """Default query formatting."""
        return query


# Convenience functions for easy usage
def format_document(title: str, content: str, model_name: str) -> str:
    """
    Auto-format document with model detection.

    Args:
        title: Document title
        content: Document content
        model_name: Name of the embedding model

    Returns:
        Formatted text ready for embedding
    """
    model_format = EmbeddingFormatter.detect_model_format(model_name)
    return EmbeddingFormatter.format_document_for_embedding(
        title, content, model_format
    )


def format_query(query: str, model_name: str, task_type: str = "search") -> str:
    """
    Auto-format query with model detection.

    Args:
        query: Search query text
        model_name: Name of the embedding model
        task_type: Type of task (default: 'search')

    Returns:
        Formatted query ready for embedding
    """
    model_format = EmbeddingFormatter.detect_model_format(model_name)
    return EmbeddingFormatter.format_query_for_embedding(query, task_type, model_format)


def get_supported_models() -> Dict[str, str]:
    """
    Get list of supported model patterns and their formats.

    Returns:
        Dictionary mapping model patterns to format types
    """
    return EmbeddingFormatter.MODEL_FORMATS.copy()


# Example usage
if __name__ == "__main__":
    # Test model detection
    test_models = [
        "embeddinggemma:latest",
        "bge-m3:567m",
        "sentence-transformers/all-MiniLM-L6-v2",
        "text-embedding-ada-002",
        "unknown-model",
    ]

    print("Model Format Detection:")
    for model in test_models:
        format_type = EmbeddingFormatter.detect_model_format(model)
        print(f"  {model} -> {format_type}")

    print("\nDocument Formatting Examples:")
    title = "Sample Article"
    content = "This is the content of the article."

    for model in test_models:
        formatted = format_document(title, content, model)
        print(f"  {model}:")
        print(f"    {formatted}")
        print()

    print("Query Formatting Examples:")
    query = "What is machine learning?"

    for model in test_models:
        formatted = format_query(query, model, "search")
        print(f"  {model}:")
        print(f"    {formatted}")
        print()
