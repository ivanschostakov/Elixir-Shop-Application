from .client import AsyncAmoCRM, amocrm_client


def get_amocrm_client() -> AsyncAmoCRM:
    return amocrm_client


__all__ = ["AsyncAmoCRM", "amocrm_client", "get_amocrm_client"]
