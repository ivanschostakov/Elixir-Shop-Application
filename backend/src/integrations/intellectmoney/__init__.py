from .client import AsyncIntellectMoney
from .errors import IntellectMoneyError

intellectmoney = AsyncIntellectMoney()
def get_intellectmoney_client() -> AsyncIntellectMoney: return intellectmoney

__all__ = ["get_intellectmoney_client", "AsyncIntellectMoney", "intellectmoney", "IntellectMoneyError"]