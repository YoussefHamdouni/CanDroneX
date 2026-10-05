from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SimRequest(BaseModel):
    type: Literal["SIM", "ESIM"]
    iccid: str = Field(pattern=r"^\d{19,20}$")


class RegisterDroneRequest(BaseModel):
    droneId: str = Field(pattern=r"^[A-Z0-9-]{3,32}$")
    imsi: str = Field(pattern=r"^\d{15}$")
    sim: SimRequest


class DroneResponse(BaseModel):
    """L'IMSI est masqué et l'ICCID n'est jamais renvoyé."""

    droneId: str
    status: str
    imsiMasked: str
    simType: str
    registeredAt: datetime
