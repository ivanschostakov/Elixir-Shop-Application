import re

from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse

from src.app.services.orders import apply_amocrm_status_update, reconcile_sbp_payment
from src.database import get_db
from src.database.crud import get_order_by_amocrm_lead_id, get_order_by_id, get_order_by_invoice_id, update_order
from src.database.schemas import OrderUpdate
from src.integrations.amocrm import amocrm_client
from src.integrations.intellectmoney import intellectmoney

webhooks_router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@webhooks_router.post("/amocrm")
async def amocrm_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    body = await request.body()
    payload = parse_qs(body.decode("utf-8", "replace"), keep_blank_values=True)

    lead_id = int((payload.get("leads[status][0][id]") or ["0"])[0] or "0")
    status_id = int((payload.get("leads[status][0][status_id]") or ["0"])[0] or "0")
    pipeline_id = int((payload.get("leads[status][0][pipeline_id]") or ["0"])[0] or "0")
    if not lead_id: return JSONResponse({"ok": True, "ignored": "no lead_id"})
    if pipeline_id and pipeline_id != amocrm_client.PIPELINE_ID: return JSONResponse({"ok": True, "ignored": "wrong pipeline"})

    lead = await amocrm_client.get_lead(lead_id)
    name = lead.get("name") or ""
    status_id = int(lead.get("status_id") or status_id or 0)
    pipeline_id = int(lead.get("pipeline_id") or pipeline_id or 0)
    if pipeline_id and pipeline_id != amocrm_client.PIPELINE_ID: return JSONResponse({"ok": True, "ignored": "pipeline mismatch"})

    order = await get_order_by_amocrm_lead_id(db, lead_id)
    if order is None:
        match = re.search(r"№\s*(\d+)", name)
        if match: order = await get_order_by_id(db, int(match.group(1)))

    if order is None: return JSONResponse({"ok": True, "ignored": "order not found"})

    updated_order = await apply_amocrm_status_update(db, order=order, status_id=status_id)
    return JSONResponse(
        {
            "ok": True,
            "order_id": updated_order.id,
            "lead_id": lead_id,
            "status_id": status_id,
        }
    )


@webhooks_router.post("/intellectmoney")
async def intellectmoney_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    form = await request.form()
    payload = {key: str(value) for key, value in form.items()}
    if not intellectmoney.verify_webhook_hash(payload):
        return PlainTextResponse("ERROR", status_code=400)

    order_id_raw = payload.get("OrderId") or ""
    order = None
    if order_id_raw.isdigit(): order = await get_order_by_id(db, int(order_id_raw))
    if order is None and payload.get("PaymentId"): order = await get_order_by_invoice_id(db, str(payload["PaymentId"]))
    if order is None: return PlainTextResponse("ERROR", status_code=404)

    order = await update_order(
        db,
        order,
        OrderUpdate(payment_provider="intellectmoney", payment_invoice_id=payload.get("PaymentId") or None),
        commit=True,
    )
    payment_status_raw = payload.get("PaymentStatus")
    payment_status_code = int(payment_status_raw) if payment_status_raw and payment_status_raw.isdigit() else None
    await reconcile_sbp_payment(
        db,
        order,
        payment_status_code=payment_status_code,
        payment_data=payload.get("PaymentData"),
        invoice_id=payload.get("PaymentId"),
    )
    return PlainTextResponse("OK")
