from datetime import datetime

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Order, User
from src.database.models.orders.history import OrderHistoryBucket, OrderStatusCode
from src.integrations.amocrm import amocrm_client
from src.integrations.intellectmoney import intellectmoney

from . import creation as _order_creation
from . import crm as _order_crm
from . import payments as _order_payments
from .common import _delivery_string, _normalize_phone
from .crm import _amocrm_payment_label, _order_has_state_patch, _order_state_patch_for_amocrm_status
from .fulfillment import create_delivery_for_order
from .payments import FINAL_PAYMENT_STATUSES, PAYMENT_STATUS_BY_CODE, PENDING_PAYMENT_STEPS
from .serialization import serialize_order, serialize_orders

_resolve_payment_qr_image = _order_payments._resolve_payment_qr_image


def _sync_runtime_dependencies() -> None:
    _order_crm.amocrm_client = amocrm_client
    _order_crm.create_delivery_for_order = create_delivery_for_order
    _order_creation.amocrm_client = amocrm_client
    _order_creation.ensure_order_has_amocrm_lead = ensure_order_has_amocrm_lead
    _order_payments.intellectmoney = intellectmoney
    _order_payments._resolve_payment_qr_image = _resolve_payment_qr_image


async def ensure_order_has_amocrm_lead(session: AsyncSession, order: Order, *, user: User) -> int:
    _sync_runtime_dependencies()
    return await _order_crm.ensure_order_has_amocrm_lead(session, order, user=user)


async def create_order_from_draft_for_user(session: AsyncSession, *, request: Request, user: User, draft_id: int, payment_method: str) -> Order:
    _sync_runtime_dependencies()
    return await _order_creation.create_order_from_draft_for_user(session, user=user, draft_id=draft_id, payment_method=payment_method)


async def get_order_for_user(session: AsyncSession, *, user_id: int, order_id: int) -> Order | None:
    return await _order_creation.get_order_for_user(session, user_id=user_id, order_id=order_id)


async def get_orders_history_for_user(session: AsyncSession, *, user_id: int, history_bucket: OrderHistoryBucket | None = None, status_code: OrderStatusCode | None = None, created_from: datetime | None = None, created_to: datetime | None = None, limit: int = 20, offset: int = 0) -> list[Order]:
    return await _order_creation.get_orders_history_for_user(session, user_id=user_id, history_bucket=history_bucket, status_code=status_code, created_from=created_from, created_to=created_to, limit=limit, offset=offset)


async def reconcile_sbp_payment(session: AsyncSession, order: Order, *, payment_step: str | None = None, payment_status_code: int | None = None, payment_data: str | None = None, invoice_id: str | None = None) -> Order:
    _sync_runtime_dependencies()
    return await _order_payments.reconcile_sbp_payment(session, order, payment_step=payment_step, payment_status_code=payment_status_code, payment_data=payment_data, invoice_id=invoice_id)


async def create_payment_for_order(session: AsyncSession, *, request: Request, order: Order) -> dict:
    _sync_runtime_dependencies()
    return await _order_payments.create_payment_for_order(session, request=request, order=order)


async def get_payment_status_for_order(session: AsyncSession, *, request: Request, order: Order) -> dict:
    _sync_runtime_dependencies()
    return await _order_payments.get_payment_status_for_order(session, request=request, order=order)


async def apply_amocrm_status_update(session: AsyncSession, *, order: Order, status_id: int) -> Order:
    _sync_runtime_dependencies()
    return await _order_crm.apply_amocrm_status_update(session, order=order, status_id=status_id)


__all__ = [
    "FINAL_PAYMENT_STATUSES",
    "PAYMENT_STATUS_BY_CODE",
    "PENDING_PAYMENT_STEPS",
    "amocrm_client",
    "apply_amocrm_status_update",
    "create_delivery_for_order",
    "create_order_from_draft_for_user",
    "create_payment_for_order",
    "ensure_order_has_amocrm_lead",
    "get_order_for_user",
    "get_orders_history_for_user",
    "get_payment_status_for_order",
    "intellectmoney",
    "reconcile_sbp_payment",
    "serialize_order",
    "serialize_orders",
]
