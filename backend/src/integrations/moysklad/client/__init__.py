from .common import logger, MOY_SKLAD_API_BASE_URL, CUSTOMER_ORDER_ATTR_IDS, CUSTOMER_ORDER_CUSTOMENTITY_ATTR_KEYS
from .utils import _customer_order_attr_id, attr_meta, order_attr, custom_order_attr, entity_ref, moysklad_money
from .transport import TransportMixin
from .counterparties import CounterpartiesMixin
from .bonus import BonusMixin
from .metadata import MetadataMixin
from .documents import DocumentsMixin
from .catalog import CatalogMixin


class MoySkladClient(TransportMixin, CounterpartiesMixin, BonusMixin, MetadataMixin, DocumentsMixin, CatalogMixin):
    pass


moysklad_client = MoySkladClient()
def get_moysklad_client() -> MoySkladClient: return moysklad_client

__all__ = ["MoySkladClient", "get_moysklad_client", "moysklad_client", "attr_meta", "order_attr", "custom_order_attr", "entity_ref", "moysklad_money"]
