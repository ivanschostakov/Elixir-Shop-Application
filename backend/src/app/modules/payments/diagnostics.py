import logging
import re

from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from starlette.exceptions import HTTPException


log = logging.getLogger(__name__)


class PaymentRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()
        if "POST" not in self.methods:
            return handler

        async def traced(request):
            try:
                return await handler(request)
            except Exception as exc:
                # FastAPI already decoded the JSON before resolving dependencies.
                # Never log the body, headers, payment links or provider messages.
                order_id = getattr(request.state, "payment_order_id", None)
                if order_id is None and request.headers.get("content-type", "").split(";")[0] == "application/json":
                    try:
                        body = await request.json()
                        value = body.get("order_id") if isinstance(body, dict) else None
                        if type(value) is int and 0 < value < 2**63:
                            order_id = value
                    except (ValueError, RuntimeError, UnicodeError):
                        pass
                code = getattr(exc, "reason_code", None)
                if not code and isinstance(exc, HTTPException) and isinstance(exc.detail, dict):
                    code = exc.detail.get("code")
                reason = code if isinstance(code, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,79}", code) else type(exc).__name__
                origin = exc.__traceback__
                while origin.tb_next is not None:
                    origin = origin.tb_next
                stage = origin.tb_frame.f_code.co_name
                status = getattr(exc, "status_code", 422 if isinstance(exc, RequestValidationError) else 500)
                log.warning("payment_create_rejected order_id=%s order_code=%s stage=%s reason=%s status=%s at=%s:%s",
                            order_id, getattr(request.state, "payment_order_code", None), stage, reason, status,
                            origin.tb_frame.f_globals.get("__name__"), origin.tb_lineno)
                raise

        return traced
