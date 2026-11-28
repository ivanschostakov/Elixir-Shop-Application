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
    "promo_code": 752923,
    "delivery_yandex": 753603,
    "tg_nick": 753183,
    "payment": 753401,
    "cdek_number": 751951,
    "address": 752435,
    "delivery_sum": 752929,
    "shipment_address": 755035,
    "delivery_method": 755099,
    "checkout_payment_method": 755097,
    "payment_status": 754985,
    "sales_channel": 755041,
    "composition": 755019,
    "order_comment": 755027,
    "order_budget": 755765,
    "cash_due": 756131,
    "balance_spent": 756209,
    "ms_order_url": 755037,
    "ms_order_id": 755005,
    "ms_order_number": 755013,
    "ms_invoice_id": 755009,
    "ms_invoice_number": 755017,
    "ms_invoice_url": 755001,
}

CHECKOUT_CHANNEL_ENUMS = {"ios": 1234871, "android": 1234873, "web": 1234867}
CHECKOUT_PAYMENT_ENUMS = {"sbp": 1233749, "later": 1233175}
CHECKOUT_DELIVERY_ENUMS = {"CDEK": 1233181, "YANDEX": 1233183}

PAID_STATUS_IDS = [
    STATUS_IDS["check_paid"],
    STATUS_IDS["packaged"],
    STATUS_IDS["package_sent"],
    STATUS_IDS["package_delivered"],
    STATUS_IDS["won"],
]
