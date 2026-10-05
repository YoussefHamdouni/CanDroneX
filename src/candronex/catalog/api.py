"""Interface publiée du module Catalog."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Union

CharacteristicValue = Union[int, str]


@dataclass(frozen=True)
class CharacteristicView:
    name: str
    value: CharacteristicValue


@dataclass(frozen=True)
class ServiceSpecificationView:
    service_type: str
    name: str
    characteristics: tuple[CharacteristicView, ...]


class CatalogQueries(Protocol):
    def find_specification(self, service_type: str) -> ServiceSpecificationView | None: ...
