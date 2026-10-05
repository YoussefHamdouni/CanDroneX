from __future__ import annotations

from datetime import datetime
from typing import Union

from pydantic import BaseModel, Field


class OrderItemRequest(BaseModel):
    action: str = Field(min_length=1, max_length=16)
    droneId: str = Field(min_length=1, max_length=64)
    serviceType: str = Field(min_length=1, max_length=32)


class CreateServiceOrderRequest(BaseModel):
    items: list[OrderItemRequest] = Field(min_length=1, max_length=50)


class CharacteristicResponse(BaseModel):
    name: str
    value: Union[int, str]


class FailureCauseResponse(BaseModel):
    code: str
    message: str


class OrderItemResponse(BaseModel):
    id: str
    action: str
    droneId: str
    serviceType: str
    state: str
    characteristics: list[CharacteristicResponse]
    failureCause: FailureCauseResponse | None = None


class ServiceOrderResponse(BaseModel):
    id: str
    state: str
    correlationId: str
    createdAt: datetime
    items: list[OrderItemResponse]
