__all__ = [
    "BitrixSyncApiClient",
    "BitrixSyncApiError",
    "BitrixSyncBatchResult",
    "get_bitrix_sync_api_client",
]

from .client import bitrix_sync_api_client, BitrixSyncBatchResult, BitrixSyncApiClient
from .exceptions import BitrixSyncApiError


def get_bitrix_sync_api_client() -> BitrixSyncApiClient:
    return bitrix_sync_api_client
