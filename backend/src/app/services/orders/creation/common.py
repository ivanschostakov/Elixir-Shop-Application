import logging
from src.integrations.amocrm import get_amocrm_client


ORDER_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


amocrm_client = get_amocrm_client()


log = logging.getLogger(__name__)
