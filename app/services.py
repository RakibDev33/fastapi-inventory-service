from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.models import Product, StockMovement
from app.schemas import ProductCreate, ProductUpdate, StockMovementCreate


class NotFoundError(Exception):
    pass


class ConflictError(Exception):
    pass


def to_cents(amount: Decimal) -> int:
    return int((amount * 100).to_integral_value())


class InventoryService:
    """Business rules for products and stock. Knows nothing about HTTP."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create_product(self, data: ProductCreate) -> Product:
        sku = data.sku.upper()
        if self.session.scalar(select(Product.id).where(Product.sku == sku)) is not None:
            raise ConflictError(f"A product with SKU '{sku}' already exists.")

        product = Product(
            sku=sku,
            name=data.name.strip(),
            unit_price_cents=to_cents(data.unit_price),
            reorder_level=data.reorder_level,
            quantity_on_hand=0,
        )
        self.session.add(product)
        self._commit(on_integrity_error=f"A product with SKU '{sku}' already exists.")
        return product

    def get_product(self, product_id: int) -> Product:
        product = self.session.get(Product, product_id)
        if product is None:
            raise NotFoundError(f"Product {product_id} was not found.")
        return product

    def list_products(self, *, low_stock: bool, limit: int, offset: int) -> tuple[list[Product], int]:
        query = select(Product)
        if low_stock:
            query = query.where(Product.quantity_on_hand <= Product.reorder_level)

        total = self.session.scalar(select(func.count()).select_from(query.subquery())) or 0
        products = self.session.scalars(query.order_by(Product.sku).limit(limit).offset(offset)).all()
        return list(products), total

    def update_product(self, product_id: int, data: ProductUpdate) -> Product:
        product = self.get_product(product_id)
        if data.name is not None:
            product.name = data.name.strip()
        if data.unit_price is not None:
            product.unit_price_cents = to_cents(data.unit_price)
        if data.reorder_level is not None:
            product.reorder_level = data.reorder_level
        self._commit()
        return product

    def record_movement(self, product_id: int, data: StockMovementCreate) -> StockMovement:
        product = self.get_product(product_id)

        new_quantity = product.quantity_on_hand + data.delta
        if new_quantity < 0:
            raise ConflictError(
                f"Insufficient stock for {product.sku}: {product.quantity_on_hand} on hand, "
                f"{-data.delta} requested."
            )

        product.quantity_on_hand = new_quantity
        movement = StockMovement(
            product=product,
            type=data.type,
            quantity=data.delta,
            quantity_after=new_quantity,
            note=data.note,
        )
        self.session.add(movement)
        self._commit()
        return movement

    def list_movements(self, product_id: int) -> list[StockMovement]:
        return list(self.get_product(product_id).movements)

    def _commit(self, on_integrity_error: str = "The request violates a data constraint.") -> None:
        try:
            self.session.commit()
        except StaleDataError as error:
            self.session.rollback()
            message = "The product was modified by another request. Reload it and retry."
            raise ConflictError(message) from error
        except IntegrityError as error:
            self.session.rollback()
            raise ConflictError(on_integrity_error) from error
