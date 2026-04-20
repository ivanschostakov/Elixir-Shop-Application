from enum import Enum
from typing import TypedDict


class YandexCargo(TypedDict):
    dx: int
    dy: int
    dz: int
    weight_gross: int


class CdekCargo(TypedDict):
    length: int
    width: int
    height: int
    weight: int


class Cargo(Enum):
    YANDEX = {"dx": 25, "dy": 15, "dz": 10, "weight_gross": 100}
    CDEK = {"length": 25, "width": 10, "height": 15, "weight": 100}