"""Adaptateur d'entrée REST du module Fleet. Aucune règle métier ici."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status

from candronex.fleet.adapter.inbound.web.schemas import (
    DroneResponse,
    RegisterDroneRequest,
)
from candronex.fleet.application.register_drone import (
    RegisterDroneCommand,
    RegisterDroneService,
)
from candronex.platform.web.auth import get_client_id
from candronex.platform.web.correlation import correlation_id_of
from candronex.shared.ids import ClientId

router = APIRouter(tags=["fleet"])


@router.post("/drones", status_code=status.HTTP_201_CREATED, response_model=DroneResponse)
def register_drone(
    body: RegisterDroneRequest,
    request: Request,
    client_id: ClientId = Depends(get_client_id),
) -> DroneResponse:
    service: RegisterDroneService = request.app.state.services.register_drone
    result = service.execute(
        RegisterDroneCommand(
            client_id=client_id,
            drone_id=body.droneId,
            imsi=body.imsi,
            sim_type=body.sim.type,
            iccid=body.sim.iccid,
            correlation_id=correlation_id_of(request),
        )
    )
    return DroneResponse(
        droneId=result.drone_id,
        status=result.status,
        imsiMasked=result.imsi_masked,
        simType=result.sim_type,
        registeredAt=result.registered_at,
    )
