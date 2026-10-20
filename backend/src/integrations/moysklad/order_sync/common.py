import logging
import re


log = logging.getLogger(__name__)


MOY_SKLAD_REQUIRED_STORE_NAME = "Основной склад"


MOY_SKLAD_STATE_NEW_ORDER = "Новый заказ"


MOY_SKLAD_STATE_INVOICE_SENT = "Счет отправлен"


MOY_SKLAD_STATE_INVOICE_PAID = "Счет оплачен"


MOY_SKLAD_INVOICEOUT_STATE_PAID = "Оплачен"


MOY_SKLAD_PAYMENT_LATER = "СБП через менеджера"


MOY_SKLAD_PAYMENT_INTELLECT = "IntellectMoney"


MOY_SKLAD_DEFAULT_DELIVERY_METHOD_NAMES = {"CDEK": "СДЭК", "YANDEX": "Яндекс.Доставка"}


_STREET_HINT_RE = re.compile(r"\b(ул\.?|улиц|пр-?кт|просп|пер\.?|переул|бул\.?|бульв|наб\.?|набереж|ш\.?|шоссе|проезд|пр-д|пл\.?|площадь|аллея|тупик)\b", re.IGNORECASE)


_HOUSE_RE = re.compile(r"\b(?:д\.?|дом)\s*([0-9A-Za-zА-Яа-я/-]+(?:\s*(?:к(?:орп)?\.?|стр\.?|с)\s*[0-9A-Za-zА-Яа-я/-]+)?)", re.IGNORECASE)


_APARTMENT_RE = re.compile(r"\b(?:кв\.?|квартира|ап\.?|apartment|офис|оф\.?)\s*([0-9A-Za-zА-Яа-я/-]+)", re.IGNORECASE)


_REGION_HINT_RE = re.compile(r"\b(обл\.?|область|край|респ\.?|республика|автономный округ|ао)\b", re.IGNORECASE)


_BUILDING_HINT_RE = re.compile(r"\b(корп\.?|корпус|стр\.?|строение|лит\.?)\b", re.IGNORECASE)
