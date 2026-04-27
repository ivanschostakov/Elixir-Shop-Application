from typing import TYPE_CHECKING, Literal

from sqlalchemy import and_, not_, or_
from sqlalchemy.sql.elements import ColumnElement

from src.integrations.amocrm.constants import STATUS_IDS, STATUS_WORDS

if TYPE_CHECKING:
    from .order import Order

OrderHistoryBucket = Literal["active", "completed"]
OrderStatusCode = Literal[
    "created",
    "invoice_sent",
    "paid",
    "waiting_response",
    "packaged",
    "sent",
    "delivered",
    "canceled",
    "completed",
    "refund_declined",
]

ORDER_HISTORY_BUCKET_VALUES: tuple[OrderHistoryBucket, ...] = ("active", "completed")
ORDER_STATUS_CODE_VALUES: tuple[OrderStatusCode, ...] = (
    "created",
    "invoice_sent",
    "paid",
    "waiting_response",
    "packaged",
    "sent",
    "delivered",
    "canceled",
    "completed",
    "refund_declined",
)

STATUS_LABELS_BY_CODE: dict[OrderStatusCode, tuple[str, ...]] = {
    "created": (STATUS_WORDS[STATUS_IDS["main"]],),
    "invoice_sent": (STATUS_WORDS[STATUS_IDS["pending_payment"]],),
    "paid": (STATUS_WORDS[STATUS_IDS["check_paid"]],),
    "waiting_response": (STATUS_WORDS[STATUS_IDS["waiting_response"]],),
    "packaged": (STATUS_WORDS[STATUS_IDS["packaged"]],),
    "sent": (STATUS_WORDS[STATUS_IDS["package_sent"]],),
    "delivered": (STATUS_WORDS[STATUS_IDS["package_delivered"]],),
    "canceled": (STATUS_WORDS[STATUS_IDS["canceled"]],),
    "completed": (STATUS_WORDS[STATUS_IDS["won"]],),
    "refund_declined": (STATUS_WORDS[STATUS_IDS["refund_declined"]],),
}

COMPLETED_STATUS_CODES = frozenset[OrderStatusCode](("delivered", "completed", "canceled", "refund_declined"))
KNOWN_STATUS_LABELS = frozenset(label for labels in STATUS_LABELS_BY_CODE.values() for label in labels)
KNOWN_NON_CREATED_ACTIVE_LABELS = frozenset(
    label
    for code, labels in STATUS_LABELS_BY_CODE.items()
    if code in {"invoice_sent", "paid", "waiting_response", "packaged", "sent"}
    for label in labels
)


def normalize_order_status(value: str | None) -> str:
    return (value or "").strip()


def _completed_clause(order_model: type["Order"]) -> ColumnElement[bool]:
    return or_(
        order_model.status.in_(tuple(label for code in COMPLETED_STATUS_CODES for label in STATUS_LABELS_BY_CODE[code])),
        and_(
            order_model.is_active.is_(False),
            order_model.is_paid.is_(True),
            order_model.is_canceled.is_(False),
        ),
    )


def build_history_bucket_clause(
    order_model: type["Order"],
    history_bucket: OrderHistoryBucket,
) -> ColumnElement[bool]:
    completed_clause = _completed_clause(order_model)
    if history_bucket == "completed":
        return completed_clause
    return not_(completed_clause)


def build_status_code_clause(
    order_model: type["Order"],
    status_code: OrderStatusCode,
) -> ColumnElement[bool]:
    if status_code == "created":
        return and_(
            build_history_bucket_clause(order_model, "active"),
            not_(order_model.status.in_(tuple(KNOWN_NON_CREATED_ACTIVE_LABELS))),
        )

    if status_code == "canceled":
        return or_(
            order_model.status.in_(STATUS_LABELS_BY_CODE["canceled"]),
            and_(
                order_model.is_canceled.is_(True),
                not_(order_model.status.in_(STATUS_LABELS_BY_CODE["refund_declined"])),
            ),
        )

    if status_code == "completed":
        return and_(
            _completed_clause(order_model),
            not_(
                order_model.status.in_(
                    tuple(
                        label
                        for code in ("delivered", "canceled", "refund_declined")
                        for label in STATUS_LABELS_BY_CODE[code]
                    )
                )
            ),
        )

    return order_model.status.in_(STATUS_LABELS_BY_CODE[status_code])


def get_order_status_code(order: "Order") -> OrderStatusCode:
    status = normalize_order_status(order.status)

    for status_code in ORDER_STATUS_CODE_VALUES:
        if status in STATUS_LABELS_BY_CODE[status_code]:
            return status_code

    if order.is_canceled:
        return "canceled"

    if not order.is_active and order.is_paid:
        return "completed"

    return "created"


def get_order_history_bucket(order: "Order") -> OrderHistoryBucket:
    if get_order_status_code(order) in COMPLETED_STATUS_CODES:
        return "completed"
    return "active"
