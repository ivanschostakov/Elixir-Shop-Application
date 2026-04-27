PIPELINE_ID = 9280278

STATUS_IDS = {
    "main": 81419122,
    "pending_payment": 75784938,
    "check_paid": 75784946,
    "waiting_response": 74461446,
    "packaged": 75784942,
    "package_sent": 76566302,
    "package_delivered": 76566306,
    "canceled": 82657618,
    "refund_declined": 143,
    "won": 142,
}

STATUS_WORDS: dict[int, str] = {
    81419122: "Создан",
    75784938: "Счет отправлен",
    75784946: "Оплачен",
    75784942: "Укомплектован",
    76566302: "Отправлен",
    76566306: "Доставлен",
    74461446: "Ожидание ответа",
    82756582: "Ожидание ответа",
    82657618: "Отменен",
    142: "Завершен",
    143: "Возврат/отказ",
}

CF = {
    "cdek_tracking_url": 752437,
    "delivery_cdek": 752921,
    "delivery_yandex": 753603,
    "tg_nick": 753183,
    "payment": 753401,
    "cdek_number": 751951,
    "address": 752435,
    "delivery_sum": 752929,
}

PAID_STATUS_IDS = [
    STATUS_IDS["check_paid"],
    STATUS_IDS["packaged"],
    STATUS_IDS["package_sent"],
    STATUS_IDS["package_delivered"],
    STATUS_IDS["won"],
]
