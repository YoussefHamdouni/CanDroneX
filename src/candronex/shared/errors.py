"""Familles d'erreurs communes à tous les modules.

Chaque module définit ses propres erreurs métier en héritant de l'une de ces
familles. La frontière REST associe chaque famille à un code HTTP sans avoir à
connaître les modules (voir platform/web/errors.py et ADR-004).
"""

from __future__ import annotations


class CanDroneXError(Exception):
    """Erreur de base. `code` est un code stable, exposé aux clients."""

    code: str = "INTERNAL_ERROR"
    title: str = "Erreur interne"

    def __init__(self, detail: str, *, code: str | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        if code is not None:
            self.code = code


class InvalidInput(CanDroneXError):
    """Donnée mal formée ou manquante (HTTP 400)."""

    code = "INVALID_INPUT"
    title = "Requête invalide"


class Unauthenticated(CanDroneXError):
    """Client non authentifié (HTTP 401)."""

    code = "UNAUTHENTICATED"
    title = "Authentification requise"


class ResourceNotFound(CanDroneXError):
    """Ressource absente ou appartenant à un autre client (HTTP 404)."""

    code = "NOT_FOUND"
    title = "Ressource introuvable"


class ConflictError(CanDroneXError):
    """Conflit avec l'état existant, par exemple une unicité (HTTP 409)."""

    code = "CONFLICT"
    title = "Conflit"


class BusinessRuleViolation(CanDroneXError):
    """Requête bien formée mais contraire à une règle métier (HTTP 422)."""

    code = "BUSINESS_RULE_VIOLATION"
    title = "Règle métier non respectée"


class ServiceUnavailable(CanDroneXError):
    """Dépendance indisponible, par exemple la base de données (HTTP 503)."""

    code = "SERVICE_UNAVAILABLE"
    title = "Service indisponible"
