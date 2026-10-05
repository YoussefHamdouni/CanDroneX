"""Objets valeur du contexte Fleet."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from candronex.shared.errors import InvalidInput

_IMSI = re.compile(r"^\d{15}$")
_ICCID = re.compile(r"^\d{19,20}$")


@dataclass(frozen=True, repr=False)
class Imsi:
    """Identité d'abonné du drone sur le réseau 5G. Donnée sensible (Loi 25, LPRPDE)."""

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not _IMSI.match(self.value):
            raise InvalidInput("L'IMSI doit comporter exactement 15 chiffres.", code="INVALID_IMSI")

    def masked(self) -> str:
        return self.value[:5] + "*" * 7 + self.value[-3:]

    def __repr__(self) -> str:  # évite toute fuite accidentelle dans un journal
        return f"Imsi({self.masked()})"

    __str__ = __repr__


@dataclass(frozen=True, repr=False)
class Iccid:
    """Numéro de la carte SIM ou du profil eSIM. Donnée sensible."""

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not _ICCID.match(self.value):
            raise InvalidInput("L'ICCID doit comporter 19 ou 20 chiffres.", code="INVALID_ICCID")

    def __repr__(self) -> str:
        return "Iccid(****)"

    __str__ = __repr__


class SimType(str, Enum):
    SIM = "SIM"
    ESIM = "ESIM"

    @classmethod
    def parse(cls, raw: str) -> "SimType":
        try:
            return cls(raw)
        except ValueError:
            raise InvalidInput(
                "Le type de SIM doit être SIM ou ESIM.", code="INVALID_SIM_TYPE"
            ) from None


@dataclass(frozen=True)
class SimInfo:
    sim_type: SimType
    iccid: Iccid


class DroneStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    RETIRED = "RETIRED"
