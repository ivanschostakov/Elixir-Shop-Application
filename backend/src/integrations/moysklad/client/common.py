import logging
from config import MOY_SKLAD_BASE_URL
from src.normalize import optional_str


logger = logging.getLogger(__name__)


MOY_SKLAD_API_BASE_URL = (optional_str(MOY_SKLAD_BASE_URL) or "https://api.moysklad.ru/api/remap/1.2").rstrip("/")


CUSTOMER_ORDER_ATTR_IDS: dict[str, str] = {
    "payment_method": "a47a457d-13e4-11f1-0a80-15c80013f10c",
    "delivery_method": "a47a4700-13e4-11f1-0a80-15c80013f10d",
    "promo_code": "a47a48ae-13e4-11f1-0a80-15c80013f10f",
    "delivery_cost": "a47a4973-13e4-11f1-0a80-15c80013f110",
    "responsible": "a47a4a52-13e4-11f1-0a80-15c80013f111",
    "counterparty_group": "a47a4b57-13e4-11f1-0a80-15c80013f112",
    "deal_link": "a0194a8b-13e7-11f1-0a80-11510020f72d",
    "created_by_widget": "a031e3b6-13e7-11f1-0a80-11510020f734",
    "client_waybill_link": "c559d1f5-537f-11f1-0a80-1b730010ddf0",
    "tracking_number": "c559d4c6-537f-11f1-0a80-1b730010ddf1",
    "site_order_link": "c559d71a-537f-11f1-0a80-1b730010ddf2",
    "delivery_tracking": "6dfc7b81-55c3-11f1-0a80-08cf000a4f89",
}


CUSTOMER_ORDER_CUSTOMENTITY_ATTR_KEYS = frozenset(("payment_method", "delivery_method", "responsible", "counterparty_group"))
