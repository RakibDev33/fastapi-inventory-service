from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_session
from app.schemas import (
    ProductCreate,
    ProductPage,
    ProductRead,
    ProductUpdate,
    StockMovementCreate,
    StockMovementRead,
)
from app.services import InventoryService


def get_service(session: Annotated[Session, Depends(get_session)]) -> InventoryService:
    return InventoryService(session)


Service = Annotated[InventoryService, Depends(get_service)]

router = APIRouter(prefix="/products", tags=["products"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_product(data: ProductCreate, service: Service) -> ProductRead:
    return ProductRead.from_model(service.create_product(data))


@router.get("")
def list_products(
    service: Service,
    low_stock: Annotated[bool, Query(description="Only products at or below their reorder level.")] = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ProductPage:
    products, total = service.list_products(low_stock=low_stock, limit=limit, offset=offset)
    return ProductPage(
        items=[ProductRead.from_model(product) for product in products],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{product_id}")
def get_product(product_id: int, service: Service) -> ProductRead:
    return ProductRead.from_model(service.get_product(product_id))


@router.patch("/{product_id}")
def update_product(product_id: int, data: ProductUpdate, service: Service) -> ProductRead:
    return ProductRead.from_model(service.update_product(product_id, data))


@router.post("/{product_id}/stock-movements", status_code=status.HTTP_201_CREATED)
def record_stock_movement(product_id: int, data: StockMovementCreate, service: Service) -> StockMovementRead:
    return StockMovementRead.from_model(service.record_movement(product_id, data))


@router.get("/{product_id}/stock-movements")
def list_stock_movements(product_id: int, service: Service) -> list[StockMovementRead]:
    return [StockMovementRead.from_model(movement) for movement in service.list_movements(product_id)]
