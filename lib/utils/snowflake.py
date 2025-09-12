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
            custom_epoch: Custom epoch timestamp (default: Twitter epoch)
        """
        self.instance_id = instance_id
        self.custom_epoch = custom_epoch

        # Initialize the generator
        if custom_epoch:
            self._generator = SnowflakeGenerator(instance_id, epoch=custom_epoch)
        else:
            self._generator = SnowflakeGenerator(instance_id)

    @classmethod
    def get_instance(cls, instance_id: int = 42, custom_epoch: Optional[int] = None):
        """
        Get or create the singleton instance.

        Args:
            instance_id: Unique identifier for this instance (0-1023)
            custom_epoch: Custom epoch timestamp (default: Twitter epoch)

        Returns:
            SnowflakeIDManager instance
        """
        if cls._instance is None:
            cls._instance = cls(instance_id, custom_epoch)
        return cls._instance

    def next_id(self) -> int:
        """
        Generate the next Snowflake ID.

        Returns:
            A unique Snowflake ID as an integer
        """
        return next(self._generator)

    def generate_batch(self, count: int) -> list[int]:
        """
        Generate a batch of Snowflake IDs.

        Args:
            count: Number of IDs to generate

        Returns:
            List of unique Snowflake IDs
        """
        return [self.next_id() for _ in range(count)]

    def get_timestamp(self, snowflake_id: int) -> int:
        """
        Extract timestamp from a Snowflake ID.

        Args:
            snowflake_id: The Snowflake ID to parse

        Returns:
            Unix timestamp in milliseconds
        """
        # Snowflake ID structure: timestamp (41 bits) | instance (10 bits) | sequence (12 bits)
        # Extract the 41-bit timestamp
        timestamp_bits = snowflake_id >> 22

        # Add the epoch offset
        if self.custom_epoch:
            return timestamp_bits + self.custom_epoch
        else:
            # Twitter epoch: January 1, 2010, 00:00:00 UTC
            twitter_epoch = 1288834974657
            return timestamp_bits + twitter_epoch

    def get_instance_id(self, snowflake_id: int) -> int:
        """
        Extract instance ID from a Snowflake ID.

        Args:
            snowflake_id: The Snowflake ID to parse

        Returns:
            Instance ID (0-1023)
        """
        # Extract the 10-bit instance ID
        return (snowflake_id >> 12) & 0x3FF

    def get_sequence(self, snowflake_id: int) -> int:
        """
        Extract sequence number from a Snowflake ID.

        Args:
            snowflake_id: The Snowflake ID to parse

        Returns:
            Sequence number (0-4095)
        """
        # Extract the 12-bit sequence number
        return snowflake_id & 0xFFF

    def parse_id(self, snowflake_id: int) -> dict:
        """
        Parse a Snowflake ID into its components.

        Args:
            snowflake_id: The Snowflake ID to parse

        Returns:
            Dictionary with timestamp, instance_id, and sequence
        """
        return {
            "timestamp": self.get_timestamp(snowflake_id),
            "instance_id": self.get_instance_id(snowflake_id),
            "sequence": self.get_sequence(snowflake_id),
            "human_readable": time.strftime(
                "%Y-%m-%d %H:%M:%S UTC",
                time.gmtime(self.get_timestamp(snowflake_id) / 1000),
            ),
        }


# Global instance for convenience
_global_manager: Optional[SnowflakeIDManager] = None


def get_snowflake_manager(
    instance_id: int = 42, custom_epoch: Optional[int] = None
) -> SnowflakeIDManager:
    """
    Get the global Snowflake ID manager instance.

    Args:
        instance_id: Unique identifier for this instance (0-1023)
        custom_epoch: Custom epoch timestamp (default: Twitter epoch)

    Returns:
        SnowflakeIDManager instance
    """
    global _global_manager
    if _global_manager is None:
        _global_manager = SnowflakeIDManager(instance_id, custom_epoch)
    return _global_manager


def get_snowflake_ids(count: int = 1, instance_id: int = 42) -> list[int]:
    """
    Generate Snowflake IDs using the global manager.

    Args:
        count: Number of IDs to generate (default: 1)
        instance_id: Instance ID to use (default: 42)

    Returns:
        List of Snowflake IDs (single ID if count=1)
    """
    manager = get_snowflake_manager(instance_id)
    return manager.generate_batch(count)


def next_snowflake_id(instance_id: int = 42) -> int:
    """
    Generate a single Snowflake ID using the global manager.

    Args:
        instance_id: Instance ID to use (default: 42)

    Returns:
        A unique Snowflake ID
    """
    manager = get_snowflake_manager(instance_id)
    return manager.next_id()


def parse_snowflake_id(snowflake_id: int, instance_id: int = 42) -> dict:
    """
    Parse a Snowflake ID into its components.

    Args:
        snowflake_id: The Snowflake ID to parse
        instance_id: Instance ID used during generation (default: 42)

    Returns:
        Dictionary with timestamp, instance_id, and sequence
    """
    manager = get_snowflake_manager(instance_id)
    return manager.parse_id(snowflake_id)


# Example usage
if __name__ == "__main__":
    # Test the Snowflake ID manager
    manager = SnowflakeIDManager(instance_id=1)

    print("Generating 5 Snowflake IDs:")
    ids = manager.generate_batch(5)
    for snowflake_id in ids:
        parsed = manager.parse_id(snowflake_id)
        print(f"ID: {snowflake_id}")
        print(f"  Timestamp: {parsed['timestamp']} ({parsed['human_readable']})")
        print(f"  Instance ID: {parsed['instance_id']}")
        print(f"  Sequence: {parsed['sequence']}")
        print()

    # Test convenience functions
    print("Using convenience functions:")
    single_id = next_snowflake_id()
    print(f"Single ID: {single_id}")

    batch_ids = get_snowflake_ids(3)
    print(f"Batch IDs: {batch_ids}")

    parsed = parse_snowflake_id(single_id)
    print(f"Parsed: {parsed}")
