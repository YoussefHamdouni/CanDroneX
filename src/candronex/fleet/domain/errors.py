from __future__ import annotations

from candronex.shared.errors import ConflictError


class DroneAlreadyRegistered(ConflictError):
    code = "DRONE_ALREADY_REGISTERED"

    def __init__(self, drone_id: str | None = None) -> None:
        subject = f"Le drone {drone_id}" if drone_id else "Ce drone"
        super().__init__(f"{subject} est déjà enregistré pour ce client.")


class NetworkIdentityInUse(ConflictError):
    """Message volontairement générique : ne révèle pas le client qui détient l'identité."""

    code = "NETWORK_IDENTITY_IN_USE"

    def __init__(self) -> None:
        super().__init__("Cette identité réseau (IMSI ou ICCID) est déjà associée à un drone.")
