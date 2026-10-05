from __future__ import annotations

from candronex.shared.errors import (
    BusinessRuleViolation,
    CanDroneXError,
    InvalidInput,
    ResourceNotFound,
)

# --- Erreurs exposées aux clients -------------------------------------------------


class EmptyOrder(InvalidInput):
    code = "EMPTY_ORDER"

    def __init__(self) -> None:
        super().__init__("Une commande doit contenir au moins un élément.")


class DuplicateItem(BusinessRuleViolation):
    code = "DUPLICATE_ITEM"

    def __init__(self, drone_id: str | None = None, service_type: str | None = None) -> None:
        if drone_id and service_type:
            detail = (
                f"Le service {service_type} est demandé plus d'une fois pour le drone {drone_id}."
            )
        else:
            detail = "Un même service est demandé plus d'une fois pour un même drone."
        super().__init__(detail)


class UnsupportedAction(BusinessRuleViolation):
    code = "UNSUPPORTED_ACTION"

    def __init__(self, action: str) -> None:
        super().__init__(f"L'action « {action} » n'est pas prise en charge; seule « add » l'est.")


class DroneNotEligible(BusinessRuleViolation):
    """Même réponse pour un drone inexistant, d'un autre client ou non actif (UC-11)."""

    code = "DRONE_NOT_ELIGIBLE"

    def __init__(self, drone_id: str) -> None:
        super().__init__(f"Le drone {drone_id} ne peut pas recevoir de service.")


class UnknownServiceType(BusinessRuleViolation):
    code = "UNKNOWN_SERVICE_TYPE"

    def __init__(self, service_type: str) -> None:
        super().__init__(f"Le type de service {service_type} n'existe pas au catalogue.")


class IdempotencyKeyReused(BusinessRuleViolation):
    code = "IDEMPOTENCY_KEY_REUSED"

    def __init__(self) -> None:
        super().__init__("Cette clé d'idempotence a déjà été utilisée pour une requête différente.")


class ServiceOrderNotFound(ResourceNotFound):
    code = "SERVICE_ORDER_NOT_FOUND"

    def __init__(self) -> None:
        super().__init__("Commande introuvable.")


# --- Erreurs internes (jamais exposées telles quelles) ----------------------------


class InvalidItemTransition(CanDroneXError):
    code = "INVALID_ITEM_TRANSITION"


class UnknownOrderItem(CanDroneXError):
    code = "UNKNOWN_ORDER_ITEM"


class DuplicateIdempotencyKey(Exception):
    """Signal du dépôt : une autre transaction a enregistré la même clé (concurrence)."""


class ConcurrentModification(Exception):
    """Signal du dépôt : la commande a été modifiée entre la lecture et l'écriture."""
