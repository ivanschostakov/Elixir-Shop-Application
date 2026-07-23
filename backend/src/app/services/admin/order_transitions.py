from src.database.models.orders.history import OrderStatusCode
from src.integrations.amocrm.constants import STATUS_IDS


STATUS_ID_BY_CODE: dict[OrderStatusCode, int] = {
    "created": STATUS_IDS["main"],
    "invoice_sent": STATUS_IDS["pending_payment"],
    "paid": STATUS_IDS["check_paid"],
    "waiting_response": STATUS_IDS["waiting_response"],
    "packaged": STATUS_IDS["packaged"],
    "sent": STATUS_IDS["package_sent"],
    "delivered": STATUS_IDS["package_delivered"],
    "canceled": STATUS_IDS["canceled"],
    "completed": STATUS_IDS["won"],
    "refund_declined": STATUS_IDS["refund_declined"],
}

ALLOWED_TRANSITIONS: dict[OrderStatusCode, frozenset[OrderStatusCode]] = {
    "created": frozenset(("invoice_sent", "waiting_response", "canceled")),
    "invoice_sent": frozenset(("paid", "waiting_response", "canceled")),
    "paid": frozenset(("waiting_response", "packaged", "refund_declined")),
    "waiting_response": frozenset(("paid", "packaged", "canceled")),
    "packaged": frozenset(("sent", "canceled", "refund_declined")),
    "sent": frozenset(("delivered", "refund_declined")),
    "delivered": frozenset(("completed", "refund_declined")),
    "canceled": frozenset(),
    "completed": frozenset(("refund_declined",)),
    "refund_declined": frozenset(),
}


def transition_status_id(status_code: OrderStatusCode) -> int:
    return STATUS_ID_BY_CODE[status_code]


def transition_is_allowed(current_code: OrderStatusCode, target_code: OrderStatusCode) -> bool:
    return target_code in ALLOWED_TRANSITIONS[current_code]
