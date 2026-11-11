from typing import Any

from fastapi.testclient import TestClient


def test_create_product_normalizes_sku_and_returns_money_as_decimal_string(
    client: TestClient, create_product: Any
) -> None:
    product = create_product(sku="kb-01", unit_price="89.9")

    assert product["sku"] == "KB-01"
    assert product["unit_price"] == "89.90"
    assert product["quantity_on_hand"] == 0
    assert product["low_stock"] is True
    assert product["created_at"].endswith("Z") or product["created_at"].endswith("+00:00")


def test_duplicate_sku_is_rejected(client: TestClient, create_product: Any) -> None:
    create_product(sku="KB-01")

    response = client.post("/products", json={"sku": "kb-01", "name": "Other", "unit_price": "1.00"})

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_invalid_product_is_rejected_with_field_errors(client: TestClient) -> None:
    response = client.post("/products", json={"sku": "bad sku!", "name": "", "unit_price": "-1"})

    assert response.status_code == 422
    fields = {error["loc"][-1] for error in response.json()["detail"]}
    assert {"sku", "name", "unit_price"} <= fields


def test_get_unknown_product_returns_404(client: TestClient) -> None:
    response = client.get("/products/999")

    assert response.status_code == 404


def test_partial_update_changes_only_given_fields(client: TestClient, create_product: Any) -> None:
    product = create_product()

    response = client.patch(f"/products/{product['id']}", json={"unit_price": "79.00"})

    assert response.status_code == 200
    updated = response.json()
    assert updated["unit_price"] == "79.00"
    assert updated["name"] == product["name"]


def test_empty_update_is_rejected(client: TestClient, create_product: Any) -> None:
    product = create_product()

    response = client.patch(f"/products/{product['id']}", json={})

    assert response.status_code == 422


def test_list_supports_low_stock_filter_and_paging(client: TestClient, create_product: Any) -> None:
    stocked = create_product(sku="A-1", reorder_level=2)
    create_product(sku="B-1", reorder_level=2)
    create_product(sku="C-1", reorder_level=2)
    client.post(f"/products/{stocked['id']}/stock-movements", json={"type": "receipt", "quantity": 10})

    low = client.get("/products", params={"low_stock": True}).json()
    page = client.get("/products", params={"limit": 2, "offset": 2}).json()

    assert [item["sku"] for item in low["items"]] == ["B-1", "C-1"]
    assert low["total"] == 2
    assert page["total"] == 3
    assert [item["sku"] for item in page["items"]] == ["C-1"]
