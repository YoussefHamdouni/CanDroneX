from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, MetaData, String, UniqueConstraint, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class FleetBase(DeclarativeBase):
    metadata = MetaData(schema="fleet")


class DroneModel(FleetBase):
    __tablename__ = "drone"
    __table_args__ = (
        UniqueConstraint("client_id", "drone_id", name="uq_drone_client_drone_id"),
        UniqueConstraint("imsi", name="uq_drone_imsi"),
        UniqueConstraint("iccid", name="uq_drone_iccid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64))
    drone_id: Mapped[str] = mapped_column(String(32))
    imsi: Mapped[str] = mapped_column(String(15))
    iccid: Mapped[str] = mapped_column(String(20))
    sim_type: Mapped[str] = mapped_column(String(8))
    status: Mapped[str] = mapped_column(String(16))
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
