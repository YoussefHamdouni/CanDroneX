from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class OrderingBase(DeclarativeBase):
    metadata = MetaData(schema="ordering")


class ServiceOrderModel(OrderingBase):
    __tablename__ = "service_order"
    __table_args__ = (
        UniqueConstraint(
            "client_id", "idempotency_key", name="uq_service_order_client_idempotency_key"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64))
    idempotency_key: Mapped[str] = mapped_column(String(255))
    request_fingerprint: Mapped[str] = mapped_column(String(64))
    correlation_id: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(16))  # dérivé, conservé pour la consultation
    version: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    items: Mapped[list["ServiceOrderItemModel"]] = relationship(
        back_populates="order",
        order_by="ServiceOrderItemModel.position",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # Verrouillage optimiste : UPDATE ... WHERE version = <version lue>.
    __mapper_args__ = {"version_id_col": version}


class ServiceOrderItemModel(OrderingBase):
    __tablename__ = "service_order_item"
    __table_args__ = (
        UniqueConstraint(
            "order_id", "drone_id", "service_type", name="uq_service_order_item_drone_service"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ordering.service_order.id", ondelete="CASCADE")
    )
    position: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(16))
    drone_id: Mapped[str] = mapped_column(String(32))  # référence vers Fleet, sans clé étrangère
    service_type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16))
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(String(500), nullable=True)

    order: Mapped[ServiceOrderModel] = relationship(back_populates="items")
    characteristics: Mapped[list["OrderItemCharacteristicModel"]] = relationship(
        order_by="OrderItemCharacteristicModel.position",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class OrderItemCharacteristicModel(OrderingBase):
    __tablename__ = "order_item_characteristic"

    item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ordering.service_order_item.id", ondelete="CASCADE"), primary_key=True
    )
    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    value_text: Mapped[str] = mapped_column(String(100))
    value_type: Mapped[str] = mapped_column(String(8))  # "int" ou "str"
    position: Mapped[int] = mapped_column(Integer)
