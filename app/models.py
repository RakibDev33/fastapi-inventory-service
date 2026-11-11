from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, UTCDateTime, utc_now


class MovementType(StrEnum):
    RECEIPT = "receipt"
    SHIPMENT = "shipment"
    ADJUSTMENT = "adjustment"


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("quantity_on_hand >= 0", name="ck_products_quantity_non_negative"),
        CheckConstraint("unit_price_cents >= 0", name="ck_products_price_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    # Money is stored in minor units to avoid floating point rounding in databases without a decimal type.
    unit_price_cents: Mapped[int]
    reorder_level: Mapped[int] = mapped_column(default=0)
    quantity_on_hand: Mapped[int] = mapped_column(default=0)
    version: Mapped[int] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)

    movements: Mapped[list["StockMovement"]] = relationship(
        back_populates="product", order_by="StockMovement.id", cascade="all, delete-orphan"
    )

    # Optimistic locking: every UPDATE checks and increments the version column.
    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012

    @property
    def is_low_stock(self) -> bool:
        return self.quantity_on_hand <= self.reorder_level


class StockMovement(Base):
    __tablename__ = "stock_movements"
    __table_args__ = (Index("ix_stock_movements_product_id", "product_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    type: Mapped[MovementType] = mapped_column(Enum(MovementType, native_enum=False, length=20))
    quantity: Mapped[int]
    quantity_after: Mapped[int]
    note: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)

    product: Mapped[Product] = relationship(back_populates="movements")
