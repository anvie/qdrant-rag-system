"""
System status and health endpoints
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import requests
import time
from typing import Dict, Any, Optional
import sys
import os

# Add parent directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), "../../../../.."))

from app.core.config import settings

router = APIRouter()


class SystemStatus(BaseModel):
    """System status response model."""

    qdrant_status: str
    ollama_status: str
    active_connections: int
    uptime: str


class ServiceHealth(BaseModel):
    """Individual service health check."""

    service: str
    status: str
    url: str
    response_time_ms: Optional[float] = None
    error: Optional[str] = None


@router.get("/status", response_model=SystemStatus)
async def get_system_status():
    """Get overall system status."""
    try:
        from app.core.websocket import websocket_manager
        import time

        start_time = time.time()

        # Check Qdrant
        qdrant_status = "unknown"
        try:
            response = requests.get(f"{settings.QDRANT_URL}/collections", timeout=5)
            qdrant_status = "healthy" if response.status_code == 200 else "unhealthy"
        except Exception:
            qdrant_status = "unhealthy"

        # Check Ollama
        ollama_status = "unknown"
        try:
            response = requests.get(f"{settings.OLLAMA_URL}/api/tags", timeout=5)
            ollama_status = "healthy" if response.status_code == 200 else "unhealthy"
        except Exception:
            ollama_status = "unhealthy"

        uptime = f"{time.time() - start_time:.2f}s"

        return SystemStatus(
            qdrant_status=qdrant_status,
            ollama_status=ollama_status,
            active_connections=websocket_manager.get_connection_count(),
            uptime=uptime,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get system status: {str(e)}"
        )


@router.get("/health")
async def health_check():
    """Detailed health check for all services."""
    services = []

    # Check Qdrant
    qdrant_health = await check_service_health("qdrant", settings.QDRANT_URL)
    services.append(qdrant_health)

    # Check Ollama
    ollama_health = await check_service_health("ollama", settings.OLLAMA_URL)
    services.append(ollama_health)

    overall_status = (
        "healthy" if all(s.status == "healthy" for s in services) else "unhealthy"
    )

    return {"status": overall_status, "services": services, "timestamp": time.time()}


async def check_service_health(service_name: str, base_url: str) -> ServiceHealth:
    """Check health of a specific service."""
    import time

    start_time = time.time()

    try:
        endpoint = (
            f"{base_url}/collections"
            if service_name == "qdrant"
            else f"{base_url}/api/tags"
        )
        response = requests.get(endpoint, timeout=5)
        response_time = (time.time() - start_time) * 1000

        status = "healthy" if response.status_code == 200 else "unhealthy"

        return ServiceHealth(
            service=service_name,
            status=status,
            url=base_url,
            response_time_ms=response_time,
        )

    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        return ServiceHealth(
            service=service_name,
            status="unhealthy",
            url=base_url,
            response_time_ms=response_time,
            error=str(e),
        )


@router.get("/models")
async def get_available_models():
    """Get available models from Ollama."""
    try:
        response = requests.get(f"{settings.OLLAMA_URL}/api/tags", timeout=10)
        if response.status_code == 200:
            data = response.json()

            # Categorize models
            embedding_models = []
            llm_models = []

            for model in data.get("models", []):
                name = model["name"]
                if any(keyword in name.lower() for keyword in ["embed", "bge", "e5"]):
                    embedding_models.append(
                        {
                            "name": name,
                            "size": model.get("size", 0),
                            "modified_at": model.get("modified_at"),
                        }
                    )
                else:
                    llm_models.append(
                        {
                            "name": name,
                            "size": model.get("size", 0),
                            "modified_at": model.get("modified_at"),
                        }
                    )

            return {
                "embedding_models": embedding_models,
                "llm_models": llm_models,
                "total_models": len(data.get("models", [])),
            }
        else:
            raise HTTPException(status_code=503, detail="Ollama service unavailable")

    except requests.exceptions.RequestException:
        raise HTTPException(status_code=503, detail="Cannot connect to Ollama service")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get models: {str(e)}")
