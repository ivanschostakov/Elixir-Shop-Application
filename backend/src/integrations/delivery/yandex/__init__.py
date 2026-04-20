from .client import YandexDeliveryClient, yandex_delivery_client
from .schemas import YandexCalculatedDelivery


def get_yandex_delivery_client() -> YandexDeliveryClient: return yandex_delivery_client

__all__ = ["get_yandex_delivery_client", "YandexDeliveryClient", "YandexCalculatedDelivery"]
