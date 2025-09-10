"""
WebSocket connection manager
"""

from fastapi import WebSocket
from typing import Dict, List
import json
import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections."""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_groups: Dict[str, List[str]] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(
            f"Client {client_id} connected. Total: {len(self.active_connections)}"
        )

    def disconnect(self, client_id: str):
        """Disconnect a WebSocket connection."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info(
                f"Client {client_id} disconnected. Remaining: {len(self.active_connections)}"
            )

            # Remove from groups
            for group_name, members in self.connection_groups.items():
                if client_id in members:
                    members.remove(client_id)

    async def send_personal_message(self, message: str, client_id: str):
        """Send a message to a specific client."""
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_text(message)
            except Exception as e:
                logger.error(f"Failed to send message to {client_id}: {e}")
                self.disconnect(client_id)

    async def send_json_message(self, data: dict, client_id: str):
        """Send JSON data to a specific client."""
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_text(json.dumps(data))
            except Exception as e:
                logger.error(f"Failed to send JSON to {client_id}: {e}")
                self.disconnect(client_id)

    async def broadcast(self, message: str):
        """Broadcast a message to all connected clients."""
        disconnected = []
        for client_id, connection in self.active_connections.items():
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Failed to broadcast to {client_id}: {e}")
                disconnected.append(client_id)

        # Clean up disconnected clients
        for client_id in disconnected:
            self.disconnect(client_id)

    async def broadcast_json(self, data: dict):
        """Broadcast JSON data to all connected clients."""
        await self.broadcast(json.dumps(data))

    def add_to_group(self, client_id: str, group_name: str):
        """Add a client to a group."""
        if group_name not in self.connection_groups:
            self.connection_groups[group_name] = []

        if client_id not in self.connection_groups[group_name]:
            self.connection_groups[group_name].append(client_id)

    def remove_from_group(self, client_id: str, group_name: str):
        """Remove a client from a group."""
        if group_name in self.connection_groups:
            if client_id in self.connection_groups[group_name]:
                self.connection_groups[group_name].remove(client_id)

    async def broadcast_to_group(self, message: str, group_name: str):
        """Broadcast a message to all clients in a group."""
        if group_name in self.connection_groups:
            disconnected = []
            for client_id in self.connection_groups[group_name]:
                if client_id in self.active_connections:
                    try:
                        await self.active_connections[client_id].send_text(message)
                    except Exception as e:
                        logger.error(
                            f"Failed to send to group {group_name}, client {client_id}: {e}"
                        )
                        disconnected.append(client_id)

            # Clean up disconnected clients
            for client_id in disconnected:
                self.disconnect(client_id)

    async def broadcast_json_to_group(self, data: dict, group_name: str):
        """Broadcast JSON data to all clients in a group."""
        await self.broadcast_to_group(json.dumps(data), group_name)

    def get_connection_count(self) -> int:
        """Get the number of active connections."""
        return len(self.active_connections)

    def get_group_members(self, group_name: str) -> List[str]:
        """Get all members of a group."""
        return self.connection_groups.get(group_name, [])


# Global WebSocket manager instance
websocket_manager = ConnectionManager()
