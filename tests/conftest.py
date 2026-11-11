from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client() -> Iterator[TestClient]:
    """A fresh application and in-memory database for every test."""
    with TestClient(create_app("sqlite+pysqlite:///:memory:")) as test_client:
        yield test_client


@pytest.fixture
def create_product(client: TestClient) -> Any:
    def _create(**overrides: Any) -> dict[str, Any]:
        payload = {"sku": "KB-01", "name": "Mechanical keyboard", "unit_price": "89.90", "reorder_level": 5}
        payload.update(overrides)
        response = client.post("/products", json=payload)
        assert response.status_code == 201, response.text
        return dict(response.json())

    return _create
