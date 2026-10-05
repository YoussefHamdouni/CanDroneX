from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, MetaData, String, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class IdentityBase(DeclarativeBase):
    metadata = MetaData(schema="identity")


class B2BClientModel(IdentityBase):
    __tablename__ = "b2b_client"

    client_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ApiCredentialModel(IdentityBase):
    __tablename__ = "api_credential"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    client_id: Mapped[str] = mapped_column(ForeignKey("identity.b2b_client.client_id"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
