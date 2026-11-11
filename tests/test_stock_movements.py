from typing import Any

import pytest
from fastapi.testclient import TestClient


def move(client: TestClient, product_id: int, type_: str, quantity: int, note: str | None = None) -> Any:
    return client.post(
        f"/products/{product_id}/stock-movements",
        json={"type": type_, "quantity": quantity, "note": note},
    )


def test_movements_update_stock_and_build_an_audit_trail(client: TestClient, create_product: Any) -> None:
    product = create_product(reorder_level=5)

    assert move(client, product["id"], "receipt", 20, "PO-1042").status_code == 201
    assert move(client, product["id"], "shipment", 12).status_code == 201
    adjustment = move(client, product["id"], "adjustment", -3, "Cycle count")

    assert adjustment.status_code == 201
    assert adjustment.json()["quantity_after"] == 5

    current = client.get(f"/products/{product['id']}").json()
    assert current["quantity_on_hand"] == 5
    assert current["low_stock"] is True

    history = client.get(f"/products/{product['id']}/stock-movements").json()
    assert [(m["type"], m["quantity"], m["quantity_after"]) for m in history] == [
        ("receipt", 20, 20),
        ("shipment", -12, 8),
        ("adjustment", -3, 5),
    ]


def test_shipping_more_than_on_hand_is_rejected_and_changes_nothing(
    client: TestClient, create_product: Any
) -> None:
    product = create_product()
    move(client, product["id"], "receipt", 3)

    response = move(client, product["id"], "shipment", 4)

    assert response.status_code == 409
    assert "Insufficient stock" in response.json()["detail"]
    assert client.get(f"/products/{product['id']}").json()["quantity_on_hand"] == 3
    assert len(client.get(f"/products/{product['id']}/stock-movements").json()) == 1


@pytest.mark.parametrize(
    ("type_", "quantity"),
    [("receipt", 0), ("receipt", -5), ("shipment", 0), ("adjustment", 0), ("unknown", 1)],
)
def test_invalid_movements_are_rejected(
    client: TestClient, create_product: Any, type_: str, quantity: int
) -> None:
    product = create_product()

    assert move(client, product["id"], type_, quantity).status_code == 422


def test_movement_for_unknown_product_returns_404(client: TestClient) -> None:
    assert move(client, 12345, "receipt", 1).status_code == 404
