"""
Internal API endpoints for inter-service communication.

These endpoints are meant to be called only by other services in the Archon system,
not by external clients. They provide internal functionality like credential sharing.
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request

from ..services.credential_service import credential_service

logger = logging.getLogger(__name__)

# Create router with internal prefix
router = APIRouter(prefix="/internal", tags=["internal"])

# Simple IP-based access control for internal endpoints
# Note: Actual validation is done by is_internal_request() function below
ALLOWED_INTERNAL_RANGES = [
    "127.0.0.1",
    "::1",
    "localhost",  # Localhost addresses
    "172.30.0.0/16",  # Docker internal network range (172.30.x.x)
    "10.0.0.0/9",  # Private network range (10.0-127.x.x)
    "archon-agents",  # Docker service name
    "archon-mcp",  # Docker service name
]


def is_internal_request(request: Request) -> bool:
    """Check if request is from an internal source."""
    client_host = request.client.host if request.client else None

    if not client_host:
        return False

    # Check if it's a Docker network IP (172.30.0.0/16 range)
    if client_host.startswith("172.30."):
        logger.info(f"Allowing Docker network request from {client_host}")
        return True

    # Check if it's a private network IP (10.0.0.0/9 range)
    if client_host.startswith("10."):
        logger.info(f"Allowing private network request from {client_host}")
        return True

    # Check if it's localhost
    if client_host in ["127.0.0.1", "::1", "localhost"]:
        return True

    return False


@router.get("/health")
async def internal_health():
    """Internal health check endpoint."""
    return {"status": "healthy", "service": "internal-api"}


@router.get("/credentials/agents")
async def get_agent_credentials(request: Request) -> Dict[str, Any]:
    """
    Get credentials needed by the agents service.

    This endpoint is only accessible from internal services and provides
    the necessary credentials for AI agents to function.
    """
    # Check if request is from internal source
    if not is_internal_request(request):
        logger.warning(
            f"Unauthorized access to internal credentials from {request.client.host}"
        )
        raise HTTPException(status_code=403, detail="Access forbidden")

    try:
        # Get credentials needed by agents
        credentials = {
            # OpenAI credentials
            "OPENAI_API_KEY": await credential_service.get_credential(
                "OPENAI_API_KEY", decrypt=True
            ),
            "OPENAI_MODEL": await credential_service.get_credential(
                "OPENAI_MODEL", default="gpt-4.1-nano"
            ),
            # Model configurations
            "DOCUMENT_AGENT_MODEL": await credential_service.get_credential(
                "DOCUMENT_AGENT_MODEL", default="openai:gpt-4o"
            ),
            "RAG_AGENT_MODEL": await credential_service.get_credential(
                "RAG_AGENT_MODEL", default="openai:gpt-4.1-nano"
            ),
            "TASK_AGENT_MODEL": await credential_service.get_credential(
                "TASK_AGENT_MODEL", default="openai:gpt-4o"
            ),
            # Rate limiting settings
            "AGENT_RATE_LIMIT_ENABLED": await credential_service.get_credential(
                "AGENT_RATE_LIMIT_ENABLED", default="true"
            ),
            "AGENT_MAX_RETRIES": await credential_service.get_credential(
                "AGENT_MAX_RETRIES", default="3"
            ),
            # MCP endpoint
            "MCP_SERVICE_URL": "http://archon-mcp:8051",
            # Additional settings
            "LOG_LEVEL": await credential_service.get_credential(
                "LOG_LEVEL", default="INFO"
            ),
        }

        # Filter out None values
        credentials = {k: v for k, v in credentials.items() if v is not None}

        logger.info(
            f"Provided credentials to agents service from {request.client.host}"
        )
        return credentials

    except Exception as e:
        logger.error(f"Error retrieving agent credentials: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve credentials")


@router.get("/credentials/mcp")
async def get_mcp_credentials(request: Request) -> Dict[str, Any]:
    """
    Get credentials needed by the MCP service.

    This endpoint provides credentials for the MCP service if needed in the future.
    """
    # Check if request is from internal source
    if not is_internal_request(request):
        logger.warning(
            f"Unauthorized access to internal credentials from {request.client.host}"
        )
        raise HTTPException(status_code=403, detail="Access forbidden")

    try:
        credentials = {
            # MCP might need some credentials in the future
            "LOG_LEVEL": await credential_service.get_credential(
                "LOG_LEVEL", default="INFO"
            ),
        }

        logger.info(f"Provided credentials to MCP service from {request.client.host}")
        return credentials

    except Exception as e:
        logger.error(f"Error retrieving MCP credentials: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve credentials")
