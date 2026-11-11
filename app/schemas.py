from datetime import datetime
from decimal import Decimal
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import MovementType, Product, StockMovement

Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
CENT = Decimal("0.01")


class ProductCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9-]*$")
    name: str = Field(min_length=1, max_length=200)
    unit_price: Money
    reorder_level: int = Field(default=0, ge=0)


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    unit_price: Money | None = None
    reorder_level: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def at_least_one_field(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided.")
        return self


class ProductRead(BaseModel):
    id: int
    sku: str
    name: str
    unit_price: Decimal
    reorder_level: int
    quantity_on_hand: int
    low_stock: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, product: Product) -> "ProductRead":
        return cls(
            id=product.id,
            sku=product.sku,
            name=product.name,
            unit_price=(Decimal(product.unit_price_cents) / 100).quantize(CENT),
            reorder_level=product.reorder_level,
            quantity_on_hand=product.quantity_on_hand,
            low_stock=product.is_low_stock,
            created_at=product.created_at,
            updated_at=product.updated_at,
        )


class ProductPage(BaseModel):
    items: list[ProductRead]
    total: int
    limit: int
    offset: int


class StockMovementCreate(BaseModel):
    type: MovementType
    quantity: int = Field(description="Units received or shipped; for adjustments, a signed correction.")
    note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def check_quantity(self) -> Self:
        if self.type is MovementType.ADJUSTMENT:
            if self.quantity == 0:
                raise ValueError("An adjustment must change the quantity.")
        elif self.quantity <= 0:
            raise ValueError(f"A {self.type.value} must have a positive quantity.")
        return self

    @property
    def delta(self) -> int:
        """Signed change to the quantity on hand."""
        return -self.quantity if self.type is MovementType.SHIPMENT else self.quantity


class StockMovementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    type: MovementType
    quantity: int
    quantity_after: int
    note: str | None
    created_at: datetime

    @classmethod
    def from_model(cls, movement: StockMovement) -> "StockMovementRead":
        return cls.model_validate(movement)
