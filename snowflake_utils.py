#!/usr/bin/env python3
"""
Snowflake ID utilities for generating unique identifiers in Qdrant vector database.

This module provides a centralized way to generate Snowflake IDs for all records
in the Qdrant system, ensuring uniqueness and time-ordered properties.
"""

import time
from typing import Optional
from snowflake import SnowflakeGenerator


class SnowflakeIDManager:
    """
    Manages Snowflake ID generation for the application.

    This class provides a singleton-like interface for generating unique
    Snowflake IDs across the application.
    """

    _instance: Optional["SnowflakeIDManager"] = None
    _generator: Optional[SnowflakeGenerator] = None

    def __init__(self, instance_id: int = 42, custom_epoch: Optional[int] = None):
        """
        Initialize the Snowflake ID manager.

        Args:
            instance_id: Unique identifier for this instance (0-1023)
            custom_epoch: Custom epoch timestamp in milliseconds (optional)
        """
        if custom_epoch is None:
            # Use a recent epoch (Jan 1, 2020) to maximize ID space
            custom_epoch = int(time.mktime((2020, 1, 1, 0, 0, 0, 0, 0, 0)) * 1000)

        self._generator = SnowflakeGenerator(instance_id, epoch=custom_epoch)
        SnowflakeIDManager._instance = self

    @classmethod
    def get_instance(
        cls, instance_id: int = 42, custom_epoch: Optional[int] = None
    ) -> "SnowflakeIDManager":
        """
        Get or create the singleton instance of SnowflakeIDManager.

        Args:
            instance_id: Unique identifier for this instance (0-1023)
            custom_epoch: Custom epoch timestamp in milliseconds (optional)

        Returns:
            SnowflakeIDManager instance
        """
        if cls._instance is None:
            cls._instance = SnowflakeIDManager(instance_id, custom_epoch)
        return cls._instance

    def generate_id(self) -> int:
        """
        Generate a new Snowflake ID.

        Returns:
            Unique Snowflake ID as integer
        """
        if self._generator is None:
            raise RuntimeError("SnowflakeIDManager not properly initialized")
        return next(self._generator)

    def generate_ids(self, count: int) -> list[int]:
        """
        Generate multiple Snowflake IDs.

        Args:
            count: Number of IDs to generate

        Returns:
            List of unique Snowflake IDs
        """
        return [self.generate_id() for _ in range(count)]


# Global instance for easy access
_default_manager: Optional[SnowflakeIDManager] = None


def get_snowflake_id() -> int:
    """
    Generate a new Snowflake ID using the default manager.

    Returns:
        Unique Snowflake ID as integer
    """
    global _default_manager
    if _default_manager is None:
        _default_manager = SnowflakeIDManager.get_instance()
    return _default_manager.generate_id()


def get_snowflake_ids(count: int) -> list[int]:
    """
    Generate multiple Snowflake IDs using the default manager.

    Args:
        count: Number of IDs to generate

    Returns:
        List of unique Snowflake IDs
    """
    global _default_manager
    if _default_manager is None:
        _default_manager = SnowflakeIDManager.get_instance()
    return _default_manager.generate_ids(count)


def initialize_snowflake(
    instance_id: int = 42, custom_epoch: Optional[int] = None
) -> None:
    """
    Initialize the global Snowflake ID manager with custom parameters.

    Args:
        instance_id: Unique identifier for this instance (0-1023)
        custom_epoch: Custom epoch timestamp in milliseconds (optional)
    """
    global _default_manager
    _default_manager = SnowflakeIDManager(instance_id, custom_epoch)


# Example usage and testing
if __name__ == "__main__":
    # Initialize the manager
    manager = SnowflakeIDManager.get_instance(instance_id=1)

    # Generate some test IDs
    print("Generated Snowflake IDs:")
    for i in range(5):
        snowflake_id = manager.generate_id()
        print(f"  {i + 1}: {snowflake_id}")

    # Test the global functions
    print("\nUsing global functions:")
    for i in range(3):
        snowflake_id = get_snowflake_id()
        print(f"  {i + 1}: {snowflake_id}")

    # Generate multiple IDs at once
    print("\nBatch generation:")
    batch_ids = get_snowflake_ids(5)
    for i, snowflake_id in enumerate(batch_ids, 1):
        print(f"  {i}: {snowflake_id}")
