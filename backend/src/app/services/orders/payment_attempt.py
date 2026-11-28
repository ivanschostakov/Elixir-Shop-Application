"""Live documents for one verification pass, and negative-only payment backoff."""
from collections import Counter, OrderedDict
from contextlib import asynccontextmanager
import logging
from math import ceil
from time import monotonic

import httpx
from fastapi import HTTPException

from src.app.services.cache import get_cache_service
from src.integrations.moysklad.client.documents import expanded_invoice
from src.integrations.moysklad.client.utils import moysklad_retry_after_seconds
from src.integrations.moysklad.settlement_checkout import entity_id

log = logging.getLogger(__name__)


class PaymentDocuments:
    def __init__(self, client=None, *, with_stock=False, expand_invoices=False):
        from src.integrations.moysklad.client import get_moysklad_client
        self.client = client or get_moysklad_client()
        self.with_stock = with_stock
        self.expand_invoices = expand_invoices
        self._orders = {}
        self._invoices = {}

    async def order(self, order_id, *, stock=False):
        stock = stock or self.with_stock
        key = (order_id, stock)
        if key not in self._orders:
            kwargs = {"expand": True, "include_stock": True} if stock else {}
            if self.expand_invoices:
                kwargs["expand_invoices"] = True
            remote = await self.client.get_customer_order(order_id, **kwargs)
            if self.expand_invoices and entity_id(remote) == order_id:
                refs = remote.get("invoicesOut") or []
                counts = Counter(map(entity_id, refs))
                for row in refs:
                    iid = entity_id(row)
                    if counts[iid] == 1 and (invoice := expanded_invoice(row)) is not None:
                        self._invoices[iid] = invoice
            self._orders[key] = remote
        return self._orders[key]

    async def invoice(self, invoice_id):
        if invoice_id not in self._invoices:
            self._invoices[invoice_id] = await self.client.get_invoiceout(invoice_id)
        return self._invoices[invoice_id]


def settlement_pending(*, rate_limit: httpx.Response | None = None, seconds: int = 4) -> HTTPException:
    if rate_limit is not None:
        seconds = ceil(moysklad_retry_after_seconds(rate_limit, default=seconds))
    return HTTPException(409, {
        "code": "settlement_pending",
        "message": "Рассчитываем оплату. Пожалуйста, подождите",
        "retry_after_seconds": seconds,
    })


# Only deadlines, never order data. Bound memory when Redis is unavailable.
_local_deadlines = OrderedDict()


async def _record_pending(redis, key, seconds):
    if redis is not None:
        try:
            await redis.set(key, "1", ex=seconds)
            return
        except Exception:
            log.warning("Payment backoff write unavailable", exc_info=True)
    _local_deadlines[key] = monotonic() + seconds
    if len(_local_deadlines) > 4096:
        _local_deadlines.popitem(last=False)


@asynccontextmanager
async def payment_backoff(order_id, method):
    """Use under the payment advisory lock, after terminal/provider checks."""
    key = f"ms:payment:wait:v1:{order_id}:{method}"
    remaining = ceil(_local_deadlines.get(key, 0) - monotonic())
    if remaining > 0:
        raise settlement_pending(seconds=remaining)
    _local_deadlines.pop(key, None)
    redis = get_cache_service().client
    if redis is not None:
        try:
            ttl_ms = await redis.pttl(key)
        except Exception:
            log.warning("Payment backoff read unavailable", exc_info=True)
        else:
            if ttl_ms > 0:
                raise settlement_pending(seconds=ceil(ttl_ms / 1000))
    try:
        yield
    except HTTPException as exc:
        if exc.status_code != 409 or not isinstance(exc.detail, dict) or exc.detail.get("code") != "settlement_pending":
            raise
        await _record_pending(redis, key, exc.detail["retry_after_seconds"])
        raise
