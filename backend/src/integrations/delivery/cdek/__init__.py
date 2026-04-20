from .client import AsyncCDEKClient, cdek_client
from .schemas import CDEKCalculatedDelivery


def get_cdek_client() -> AsyncCDEKClient: return cdek_client


__all__ = [
    "get_cdek_client",
    "AsyncCDEKClient",
    "CDEKCalculatedDelivery"
]