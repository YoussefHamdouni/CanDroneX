"""Agrégat ServiceSpecification. Les caractéristiques sont des données, pas du code."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Union

from candronex.shared.errors import InvalidInput

_SERVICE_TYPE = re.compile(r"^[A-Z0-9_]{1,32}$")

CharacteristicValue = Union[int, str]


@dataclass(frozen=True)
class ServiceType:
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not _SERVICE_TYPE.match(self.value):
            raise InvalidInput("Type de service invalide.", code="INVALID_SERVICE_TYPE")


@dataclass(frozen=True)
class ServiceCharacteristic:
    name: str
    value: CharacteristicValue

    def __post_init__(self) -> None:
        if not self.name:
            raise InvalidInput("Une caractéristique doit avoir un nom.")
        if isinstance(self.value, bool) or not isinstance(self.value, (int, str)):
            raise InvalidInput("Une caractéristique doit être un entier ou une chaîne.")


@dataclass(frozen=True)
class ServiceSpecification:
    service_type: ServiceType
    name: str
    characteristics: tuple[ServiceCharacteristic, ...]

    def __post_init__(self) -> None:
        if not self.characteristics:
            raise InvalidInput("Une spécification doit avoir au moins une caractéristique.")
        names = [c.name for c in self.characteristics]
        if len(names) != len(set(names)):
            raise InvalidInput("Les caractéristiques d'une spécification doivent être uniques.")
