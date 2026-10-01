import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)

_index_dir = Path(__file__).parent.parent / "data" / "index"
needs_index = pytest.mark.skipif(
    not (_index_dir / "dictionary.json").exists(),
    reason="Built index not available — run 'python -m src.cli index' first"
)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_stats():
    response = client.get("/stats")
    assert response.status_code == 200
    data = response.json()
    assert "num_papers" in data
    assert "num_terms" in data

@needs_index
def test_search_basic():
    response = client.get("/search?q=neural+network")
    assert response.status_code == 200
    data = response.json()
    assert "query" in data
    assert "total_hits" in data
    assert "results" in data
    assert data["query"] == "neural network"

@needs_index
def test_search_pagination():
    response = client.get("/search?q=network&page=1&size=2")
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 1
    assert data["size"] == 2
    assert len(data["results"]) <= 2

@needs_index
def test_search_empty_query():
    response = client.get("/search?q=")
    # Empty query returns 0 results but is still valid
    assert response.status_code == 200
    data = response.json()
    assert data["total_hits"] == 0
