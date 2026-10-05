from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, MetaData, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class CatalogBase(DeclarativeBase):
    metadata = MetaData(schema="catalog")


class ServiceSpecificationModel(CatalogBase):
    __tablename__ = "service_specification"

    service_type: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    characteristics: Mapped[list["ServiceCharacteristicModel"]] = relationship(
        order_by="ServiceCharacteristicModel.position", lazy="selectin"
    )


class ServiceCharacteristicModel(CatalogBase):
    __tablename__ = "service_characteristic"

    service_type: Mapped[str] = mapped_column(
        ForeignKey("catalog.service_specification.service_type"), primary_key=True
    )
    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    value_text: Mapped[str] = mapped_column(String(100))
    value_type: Mapped[str] = mapped_column(String(8))  # "int" ou "str"
    position: Mapped[int] = mapped_column(Integer)
