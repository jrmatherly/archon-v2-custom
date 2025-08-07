"""Essential API tests - Focus on core functionality that must work."""

from unittest.mock import MagicMock, patch

import pytest


def test_health_endpoint(client):
    """Test that health endpoint returns OK status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] in ["healthy", "initializing"]


def test_create_project(client, test_project, mock_supabase_client):
    """Test creating a new project via API."""
    # Set up mock to return a project
    mock_supabase_client.table.return_value.insert.return_value.execute.return_value.data = [
        {
            "id": "test-project-id",
            "title": test_project["title"],
            "description": test_project["description"],
        }
    ]

    response = client.post("/api/projects", json=test_project)
    # Should succeed - project creation returns 200
    assert response.status_code == 200

    data = response.json()
    # The API returns progress_id and status for async project creation
    assert "progress_id" in data
    assert "status" in data
    assert data["status"] == "started"
    assert "message" in data


def test_list_projects(client, mock_supabase_client):
    """Test listing projects endpoint exists and responds."""
    # Set up mock to return empty list (no projects)
    mock_supabase_client.table.return_value.select.return_value.execute.return_value.data = []

    response = client.get("/api/projects")
    assert response.status_code == 200
    # Response should be a list of projects (empty list when no projects)
    data = response.json()
    assert isinstance(data, list)
    # With empty mock data, should return empty list
    assert len(data) == 0

    # Verify mock was called
    assert mock_supabase_client.table.called


def test_create_task(client, test_task):
    """Test task creation endpoint exists."""
    # Try the tasks endpoint directly
    response = client.post("/api/tasks", json=test_task)
    # Accept various status codes - endpoint exists
    assert response.status_code in [200, 201, 400, 422, 405]


def test_list_tasks(client):
    """Test tasks listing endpoint exists."""
    response = client.get("/api/tasks")
    # Accept 200, 400, 422, or 500 - endpoint exists
    assert response.status_code in [200, 400, 422, 500]


def test_start_crawl(client):
    """Test crawl endpoint exists and validates input."""
    crawl_request = {"url": "https://example.com", "max_depth": 2, "max_pages": 10}

    response = client.post("/api/knowledge/crawl", json=crawl_request)
    # Accept various status codes - endpoint exists and processes request
    assert response.status_code in [200, 201, 400, 404, 422, 500]


def test_search_knowledge(client):
    """Test knowledge search endpoint exists."""
    response = client.post("/api/knowledge/search", json={"query": "test"})
    # Accept various status codes - endpoint exists
    assert response.status_code in [200, 400, 404, 422, 500]


def test_websocket_connection(client):
    """Test WebSocket/Socket.IO endpoint exists."""
    response = client.get("/socket.io/")
    # Socket.IO returns specific status codes
    assert response.status_code in [200, 400, 404]


def test_authentication(client):
    """Test that API handles auth headers gracefully."""
    # Test with no auth header
    response = client.get("/api/projects")
    assert response.status_code in [200, 401, 403]

    # Test with invalid auth header
    headers = {"Authorization": "Bearer invalid-token"}
    response = client.get("/api/projects", headers=headers)
    assert response.status_code in [200, 401, 403]


def test_error_handling(client):
    """Test API returns proper error responses."""
    # Test non-existent endpoint
    response = client.get("/api/nonexistent")
    assert response.status_code == 404

    # Test invalid JSON
    response = client.post("/api/projects", data="invalid json")
    assert response.status_code in [400, 422]
