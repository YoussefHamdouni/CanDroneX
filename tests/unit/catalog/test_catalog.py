import pytest

from candronex.catalog.domain.service_specification import (
    ServiceCharacteristic,
    ServiceSpecification,
    ServiceType,
)
from candronex.shared.errors import InvalidInput


def test_une_specification_porte_des_caracteristiques_uniques():
    ServiceSpecification(ServiceType("C2"), "C&C", (ServiceCharacteristic("sst", 2),))
    with pytest.raises(InvalidInput):
        ServiceSpecification(
            ServiceType("C2"),
            "C&C",
            (ServiceCharacteristic("sst", 2), ServiceCharacteristic("sst", 1)),
        )
    with pytest.raises(InvalidInput):
        ServiceSpecification(ServiceType("C2"), "C&C", ())


def test_le_type_de_service_respecte_son_format():
    with pytest.raises(InvalidInput):
        ServiceType("c2")
