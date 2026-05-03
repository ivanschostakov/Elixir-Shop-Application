import hashlib
import logging
import httpx

from decimal import Decimal
from typing import Any

from config import (
    INTELLECTMONEY_API_BASE,
    INTELLECTMONEY_BEARER_TOKEN,
    INTELLECTMONEY_SECRET_KEY,
    INTELLECTMONEY_SHOP_ID,
    INTELLECTMONEY_SIGN_SECRET_KEY,
)
from .errors import IntellectMoneyError
from .helpers import as_str, safe_form_for_log, response_body_for_log, is_hash_error, webhook_payload_value


class AsyncIntellectMoney:
    def __init__(self) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.api_base = (INTELLECTMONEY_API_BASE or "").rstrip("/")
        self.bearer_token = INTELLECTMONEY_BEARER_TOKEN or ""
        self.secret_key = INTELLECTMONEY_SECRET_KEY or ""
        self.sign_secret_key = INTELLECTMONEY_SIGN_SECRET_KEY or ""
        self.shop_id = INTELLECTMONEY_SHOP_ID or ""

    @classmethod
    def _sha256_signature(cls, *parts: Any) -> str:
        raw = "::".join(as_str(part) for part in parts)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @classmethod
    def _md5_hash(cls, *parts: Any) -> str:
        raw = "::".join(as_str(part) for part in parts)
        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    @classmethod
    def _md5_hash_encoded(cls, *parts: Any, encoding: str = "utf-8") -> str | None:
        raw = "::".join(as_str(part) for part in parts)
        try: return hashlib.md5(raw.encode(encoding)).hexdigest()
        except UnicodeEncodeError: return None

    def _ensure_config(self) -> None:
        missing = []
        if not self.api_base: missing.append("INTELLECTMONEY_API_BASE")
        if not self.shop_id: missing.append("INTELLECTMONEY_SHOP_ID")
        if not self.bearer_token: missing.append("INTELLECTMONEY_BEARER_TOKEN")
        if not self.secret_key: missing.append("INTELLECTMONEY_SECRET_KEY")
        if not self.sign_secret_key: missing.append("INTELLECTMONEY_SIGN_SECRET_KEY")
        if missing: raise IntellectMoneyError(f"Missing IntellectMoney config: {', '.join(missing)}")

    def _headers(self, *sign_parts: Any) -> dict[str, str]:
        self._ensure_config()
        return {"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded", "Authorization": f"Bearer {self.bearer_token}", "Sign": self._sha256_signature(*sign_parts, self.sign_secret_key),  }

    def _hash_secrets(self) -> list[str]:
        secrets: list[str] = []
        for candidate in (self.secret_key, self.sign_secret_key):
            normalized = str(candidate or "").strip()
            if normalized and normalized not in secrets: secrets.append(normalized)

        return secrets
    
    async def _post_form(self, path: str, form_data: dict[str, Any], *sign_parts: Any) -> dict[str, Any]:
        headers = self._headers(*sign_parts)
        self.logger.info( "IntellectMoney POST request path=%s form=%s", path, safe_form_for_log(form_data))
        async with httpx.AsyncClient(timeout=30.0) as client: response = await client.post(f"{self.api_base}{path}", data=form_data, headers=headers)

        self.logger.info("IntellectMoney POST response path=%s status_code=%s headers=%s body=%s", path, response.status_code, dict(response.headers), response_body_for_log(response),  )

        try: response.raise_for_status()
        except httpx.HTTPError as exc: raise IntellectMoneyError(str(exc)) from exc

        try: data = response.json()
        except ValueError as exc: raise IntellectMoneyError(f"IntellectMoney returned non-JSON response: {response_body_for_log(response)}") from exc
        operation = data.get("OperationState") or {}
        if int(operation.get("Code") or 0) != 0: raise IntellectMoneyError(str(operation.get("Desc") or "IntellectMoney operation failed"))

        result = data.get("Result") or {}
        if isinstance(result, dict):
            state = result.get("State") or {}
            state_code_raw = state.get("Code")
            if state_code_raw not in (None, ""):
                try: state_code = int(state_code_raw)
                except (TypeError, ValueError): state_code = None
                if state_code not in (None, 0, 1):
                    description = str(state.get("Desc") or "IntellectMoney request failed")
                    error_source = str(state.get("ErrorSourceParam") or "").strip()
                    if error_source: description = f"{description} (param: {error_source})"
                    raise IntellectMoneyError(description)

        return data

    async def create_invoice(self,  *,  order_id: str,  service_name: str,  amount_rub: Decimal | float | int | str,  user_name: str,  email: str,  success_url: str,  fail_url: str,  back_url: str,  result_url: str,  preference: str = "Sbp") -> dict[str, Any]:
        amount_str = self.amount(amount_rub)
        base_form = {"EshopId": self.shop_id, "OrderId": order_id, "ServiceName": service_name, "RecipientAmount": amount_str, "RecipientCurrency": "RUB", "UserName": user_name, "Email": email, "SuccessUrl": success_url, "FailUrl": fail_url, "BackUrl": back_url, "ResultUrl": result_url, "Preference": preference,  }
        last_exc: Exception | None = None
        for idx, hash_secret in enumerate(self._hash_secrets()):
            form = dict(base_form)
            form["Hash"] = self._md5_hash(self.shop_id, order_id, service_name, amount_str, "RUB", user_name, email, success_url, fail_url, back_url, result_url, "", "", preference, hash_secret)
            try: return await self._post_form("/merchant/createInvoice", form, self.shop_id, order_id, service_name, amount_str, "RUB", user_name, email, success_url, fail_url, back_url, result_url, "", "", preference)
            except IntellectMoneyError as exc:
                last_exc = exc
                if idx + 1 >= len(self._hash_secrets()) or not is_hash_error(exc): raise
                self.logger.warning("Retrying createInvoice with alternate IntellectMoney hash secret")

        assert last_exc is not None
        raise last_exc

    async def sbp_payment(self, *, invoice_id: str, success_url: str, fail_url: str, ip_address: str, additional_params: str = "") -> dict[str, Any]:
        base_form = {"EshopId": self.shop_id, "InvoiceId": invoice_id, "SuccessUrl": success_url, "FailUrl": fail_url, "AdditionalParams": additional_params, "IpAddress": ip_address}
        last_exc: Exception | None = None
        for idx, hash_secret in enumerate(self._hash_secrets()):
            form = dict(base_form)
            form["Hash"] = self._md5_hash(self.shop_id, invoice_id, success_url, fail_url, additional_params, ip_address, hash_secret)
            try: return await self._post_form("/merchant/sbpPayment", form, self.shop_id, invoice_id, success_url, fail_url, additional_params, ip_address)
            except IntellectMoneyError as exc:
                last_exc = exc
                if idx + 1 >= len(self._hash_secrets()) or not is_hash_error(exc): raise
                self.logger.warning("Retrying sbpPayment with alternate IntellectMoney hash secret")

        assert last_exc is not None
        raise last_exc

    async def get_bank_card_payment_state(self, *, invoice_id: str) -> dict[str, Any]:
        base_form = {"EshopId": self.shop_id, "InvoiceId": invoice_id}
        last_exc: Exception | None = None
        for idx, hash_secret in enumerate(self._hash_secrets()):
            form = dict(base_form)
            form["Hash"] = self._md5_hash(self.shop_id, invoice_id, hash_secret)
            try: return await self._post_form("/merchant/getBankCardPaymentState", form, self.shop_id, invoice_id)
            except IntellectMoneyError as exc:
                last_exc = exc
                if idx + 1 >= len(self._hash_secrets()) or not is_hash_error(exc): raise
                self.logger.warning("Retrying getBankCardPaymentState with alternate IntellectMoney hash secret")

        assert last_exc is not None
        raise last_exc

    def verify_webhook_hash(self, payload: dict[str, Any]) -> bool:
        actual = str(webhook_payload_value(payload, "Hash") or "")
        if not actual: return False

        hash_parts = [webhook_payload_value(payload, "EshopId"), webhook_payload_value(payload, "OrderId"), webhook_payload_value(payload, "ServiceName"), webhook_payload_value(payload, "EshopAccount"), webhook_payload_value(payload, "RecipientAmount"), webhook_payload_value(payload, "RecipientCurrency"), webhook_payload_value(payload, "PaymentStatus"), webhook_payload_value(payload, "UserName"), webhook_payload_value(payload, "UserEmail"), webhook_payload_value(payload, "PaymentData"),  ]
        for hash_secret in self._hash_secrets():
            for encoding in ("utf-8", "cp1251"):
                expected = self._md5_hash_encoded(*hash_parts, hash_secret, encoding=encoding)
                if expected and actual.lower() == expected.lower(): return True

        return False
