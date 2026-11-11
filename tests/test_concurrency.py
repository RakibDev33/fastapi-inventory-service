from decimal import Decimal
from pathlib import Path

import pytest

from app.database import Base, create_db_engine, create_session_factory
from app.models import MovementType
from app.schemas import ProductCreate, StockMovementCreate
from app.services import ConflictError, InventoryService


def test_concurrent_update_of_the_same_product_is_detected(tmp_path: Path) -> None:
    engine = create_db_engine(f"sqlite+pysqlite:///{tmp_path / 'inventory.db'}")
    Base.metadata.create_all(engine)
    sessions = create_session_factory(engine)
    receipt = StockMovementCreate(type=MovementType.RECEIPT, quantity=5)
    shipment = StockMovementCreate(type=MovementType.SHIPMENT, quantity=5)

    with sessions() as setup:
        service = InventoryService(setup)
        product_id = service.create_product(
            ProductCreate(sku="KB-01", name="Keyboard", unit_price=Decimal("10.00"))
        ).id
        service.record_movement(product_id, receipt)

    try:
        with sessions() as first, sessions() as second:
            # Both requests read the same version of the product before either one writes.
            # Holding the instances keeps them in each session's identity map, like a live request would.
            seen_by_first = InventoryService(first).get_product(product_id)
            seen_by_second = InventoryService(second).get_product(product_id)
            assert seen_by_first.version == seen_by_second.version

            InventoryService(first).record_movement(product_id, shipment)
            with pytest.raises(ConflictError, match="modified by another request"):
                InventoryService(second).record_movement(product_id, shipment)

        with sessions() as check:
            assert InventoryService(check).get_product(product_id).quantity_on_hand == 0
    finally:
        engine.dispose()
