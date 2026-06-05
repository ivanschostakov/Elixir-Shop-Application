import asyncio
import logging
import os
import re

from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse
from fastapi import HTTPException

from .constants import CF, PAID_STATUS_IDS, PIPELINE_ID, STATUS_IDS, STATUS_WORDS
from .payloads import build_contact_create_payload, build_contact_update_payload, build_lead_create_payload, build_lead_link_payload, build_lead_note_payload, build_order_lead_custom_fields
from .schemas.lead import LeadStatusUpdatePayload
from .transport import AmoCRMTransport
from .utils import extract_email_from_contact_obj, extract_phone_from_contact_obj, normalize_phone
from config import AMOCRM_ACCESS_TOKEN, AMOCRM_ACCOUNT_ID, AMOCRM_AUTH_CODE, AMOCRM_BASE_DOMAIN, AMOCRM_CLIENT_ID, AMOCRM_CLIENT_SECRET, AMOCRM_LOGIN_EMAIL, AMOCRM_LOGIN_PASSWORD, AMOCRM_PLAYWRIGHT_HEADLESS, AMOCRM_REDIRECT_URI, AMOCRM_REFRESH_TOKEN, WORKING_DIR


class AsyncAmoCRM:
    _playwright = None
    _auth_context = None
    _auth_page = None
    _auth_session_lock = None

    def __init__(self, *, base_domain: str | None = AMOCRM_BASE_DOMAIN, client_id: str | None = AMOCRM_CLIENT_ID, client_secret: str | None = AMOCRM_CLIENT_SECRET, redirect_uri: str | None = AMOCRM_REDIRECT_URI, access_token: str | None = AMOCRM_ACCESS_TOKEN, refresh_token: str | None = AMOCRM_REFRESH_TOKEN, auth_code: str | None = AMOCRM_AUTH_CODE, login_email: str | None = AMOCRM_LOGIN_EMAIL, login_password: str | None = AMOCRM_LOGIN_PASSWORD, account_id: str | None = AMOCRM_ACCOUNT_ID, playwright_headless: bool = AMOCRM_PLAYWRIGHT_HEADLESS) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.auth_code = (auth_code or "").strip() or None
        self.login_email = (login_email or "").strip() or None
        self.login_password = login_password
        self.account_id = (account_id or "").strip() or None
        self.playwright_headless = playwright_headless
        self._auth_code_lock = asyncio.Lock()
        self.transport = AmoCRMTransport(base_domain=(base_domain or "").strip(), client_id=client_id or "", client_secret=client_secret or "", redirect_uri=redirect_uri or "", access_token=access_token, refresh_token=refresh_token, save_tokens_callback=self._save_env_values)
        self.PIPELINE_ID = PIPELINE_ID
        self.STATUS_IDS = STATUS_IDS
        self.STATUS_WORDS = STATUS_WORDS
        self.CF = CF
        self.PAID_STATUS_IDS = PAID_STATUS_IDS

    def _ensure_playwright_auth_config(self) -> None:
        missing = []
        if not self.login_email: missing.append("AMOCRM_LOGIN_EMAIL")
        if not self.login_password: missing.append("AMOCRM_LOGIN_PASSWORD")
        if missing: raise HTTPException(status_code=503, detail=f"Missing amoCRM Playwright auth config: {', '.join(missing)}")

    @classmethod
    def _get_auth_session_lock(cls) -> asyncio.Lock:
        if cls._auth_session_lock is None:
            cls._auth_session_lock = asyncio.Lock()
        return cls._auth_session_lock

    async def _get_auth_page(self):
        async with self._get_auth_session_lock():
            if self.__class__._auth_context is None or self.__class__._auth_page is None or self.__class__._auth_page.is_closed():
                try:
                    from playwright.async_api import async_playwright
                except ModuleNotFoundError as exc:
                    raise HTTPException(status_code=503, detail="Playwright is not installed for amoCRM interactive authorization") from exc

                profile_dir = Path(os.getenv("AMOCRM_PLAYWRIGHT_USER_DATA_DIR") or (WORKING_DIR / "logs" / ".amocrm_playwright_profile"))
                profile_dir.mkdir(parents=True, exist_ok=True)
                self.logger.info(
                    "Starting persistent amoCRM Playwright session | profile=%s | headless=%s",
                    profile_dir,
                    self.playwright_headless,
                )
                if self.__class__._playwright is None:
                    self.__class__._playwright = await async_playwright().start()
                self.__class__._auth_context = await self.__class__._playwright.chromium.launch_persistent_context(
                    user_data_dir=str(profile_dir),
                    headless=self.playwright_headless,
                    viewport={"width": 1280, "height": 900},
                    args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-web-security", "--disable-features=IsolateOrigins,site-per-process"],
                )
                pages = self.__class__._auth_context.pages
                self.__class__._auth_page = pages[0] if pages else await self.__class__._auth_context.new_page()
            return self.__class__._auth_page

    def _save_env_values(self, values: dict[str, str]) -> None:
        if not values: return
        path = WORKING_DIR / ".env"
        lines = path.read_text().splitlines(keepends=True) if path.exists() else []
        pending = dict(values)
        new_lines: list[str] = []
        for line in lines:
            stripped = line.strip()
            if "=" not in line or stripped.startswith("#"): new_lines.append(line); continue
            key = line.split("=", 1)[0].strip()
            if key not in pending: new_lines.append(line); continue
            new_lines.append(f'{key}="{pending.pop(key)}"\n')
        for key, value in pending.items(): new_lines.append(f'{key}="{value}"\n')
        path.write_text("".join(new_lines))

    async def _get_new_auth_code(self) -> str:
        self.transport._ensure_config()
        self._ensure_playwright_auth_config()
        query = urlencode({"client_id": self.transport.client_id, "redirect_uri": self.transport.redirect_uri, "response_type": "code"})
        auth_url = f"https://www.amocrm.ru/oauth?{query}"
        self.logger.warning("Reusing persistent Playwright session to get a new amoCRM authorization code")

        async with self._auth_code_lock:
            page = await self._get_auth_page()
            await page.goto(auth_url, wait_until="domcontentloaded", timeout=45000)

            try:
                await page.wait_for_selector('input[name="username"]', timeout=5000)
                await page.fill('input[name="username"]', self.login_email or "")
                await page.fill('input[name="password"]', self.login_password or "")
                await page.click('button[type="submit"]')
                self.logger.info("Logged into amoCRM via persistent Playwright session")
                try:
                    await page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    pass
            except Exception as exc:
                self.logger.info("amoCRM login form not shown; using saved browser session | error=%s", exc)

            try:
                await page.wait_for_selector("select.js-accounts-list", timeout=10000)
                if self.account_id:
                    await page.select_option("select.js-accounts-list", value=self.account_id)
                    self.logger.info("Selected amoCRM account %s", self.account_id)
            except Exception as exc:
                self.logger.info("amoCRM account picker not shown or already selected | error=%s", exc)

            clicked = False
            for selector in ("button.js-accept", 'button:has-text("Разрешить")', 'button:has-text("Allow")', 'button[type="submit"]'):
                try:
                    locator = page.locator(selector)
                    if await locator.count():
                        await locator.first.click(timeout=5000)
                        clicked = True
                        self.logger.info("Clicked amoCRM authorization button via selector %s", selector)
                        break
                except Exception as exc:
                    self.logger.debug("amoCRM authorization button selector failed: %s | %s", selector, exc)
            if not clicked:
                self.logger.info("No amoCRM authorization button visible; waiting for redirect/code anyway")

            redirect_prefix = self.transport.redirect_uri.rstrip("/")
            try:
                await page.wait_for_function(
                    "(redirectUri) => { const href = window.location.href; return href.startsWith(redirectUri) && href.includes('code='); }",
                    arg=redirect_prefix,
                    timeout=45000,
                )
            except Exception as exc:
                title = ""
                try:
                    title = await page.title()
                except Exception:
                    pass
                raise HTTPException(
                    status_code=502,
                    detail={
                        "service": "amocrm",
                        "stage": "playwright_redirect",
                        "error": str(exc),
                        "url": page.url,
                        "title": title,
                    },
                ) from exc

            code = parse_qs(urlparse(page.url).query).get("code", [None])[0]
            if not code:
                raise HTTPException(status_code=502, detail={"service": "amocrm", "stage": "playwright_code", "error": "Failed to extract amoCRM authorization code from redirect URL", "url": page.url})
            self.logger.info("Received a new amoCRM authorization code via persistent Playwright session")
            return str(code)

    async def _authorize(self, code: str | None = None) -> None:
        candidate_code = (code or self.auth_code or "").strip() or None
        if candidate_code:
            try: await self.transport.authorize_with_code(candidate_code); self.auth_code = candidate_code; return
            except HTTPException as exc: self.logger.warning("Stored amoCRM authorization code failed; requesting a fresh code | detail=%s", exc.detail)
        new_code = await self._get_new_auth_code()
        self.auth_code = new_code
        await self.transport.authorize_with_code(new_code)

    async def _refresh(self) -> None:
        if not self.transport.refresh_token: await self._authorize(); return
        try: await self.transport.refresh()
        except HTTPException as exc: self.logger.warning("amoCRM refresh token failed; falling back to authorization flow | detail=%s", exc.detail); await self._authorize()

    async def _ensure_token_valid(self) -> None:
        try: await self.transport.ensure_token_valid()
        except HTTPException: await self._refresh()

    async def _request_with_auth_recovery(self, method: str, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        await self._ensure_token_valid()
        transport_call = getattr(self.transport, method.lower())
        try:
            return await transport_call(endpoint, **kwargs)
        except HTTPException as exc:
            if exc.status_code == 502 and str(exc.detail) == "amoCRM authentication failed":
                self.logger.warning(
                    "amoCRM transport authentication failed during %s %s; retrying via full reauthorization flow",
                    method,
                    endpoint,
                )
                await self._refresh()
                return await transport_call(endpoint, **kwargs)
            raise

    async def _get(self, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        return await self._request_with_auth_recovery("GET", endpoint, **kwargs)

    async def _post(self, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        return await self._request_with_auth_recovery("POST", endpoint, **kwargs)

    async def _patch(self, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        return await self._request_with_auth_recovery("PATCH", endpoint, **kwargs)

    async def get_contact(self, contact_id: int) -> dict[str, Any] | None:
        try: return await self._get(f"/api/v4/contacts/{contact_id}")
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, dict) else {}
            if isinstance(detail, dict) and detail.get("status_code") == 404: return None
            raise

    async def get_lead(self, lead_id: int) -> dict[str, Any]: return await self._get(f"/api/v4/leads/{lead_id}")

    async def search_contacts(self, query: str, *, limit: int = 50) -> list[dict[str, Any]]:
        if not query: return []
        data = await self._get("/api/v4/contacts", params={"query": query, "limit": limit})
        return (data.get("_embedded") or {}).get("contacts") or []

    async def create_contact(self, *, name: str, phone: str | None, email: str | None) -> dict[str, Any]:
        payload = build_contact_create_payload(name=name, phone=phone, email=email)
        data = await self._post("/api/v4/contacts", json=[self.transport.dump_payload(payload)])
        return ((data.get("_embedded") or {}).get("contacts") or [{}])[0]

    async def update_contact(self, contact_id: int, *, name: str | None = None, phone: str | None = None, email: str | None = None) -> dict[str, Any]:
        payload = build_contact_update_payload(contact_id=contact_id, name=name, phone=phone, email=email)
        data = await self._patch("/api/v4/contacts", json=[self.transport.dump_payload(payload)])
        return ((data.get("_embedded") or {}).get("contacts") or [{"id": contact_id}])[0]

    async def find_or_create_contact(self, *, lead_name: str, phone: str | None, email: str | None, contact_id: int | None = None) -> dict[str, Any]:
        normalized_phone = normalize_phone(phone)
        normalized_email = email.strip().lower() if email else None
        if contact_id:
            existing_contact = await self.get_contact(contact_id)
            if existing_contact: await self.update_contact(contact_id, name=lead_name, phone=normalized_phone, email=normalized_email); refreshed_contact = await self.get_contact(contact_id); return refreshed_contact or existing_contact

        candidates: dict[int, dict[str, Any]] = {}
        queries = [candidate for candidate in [normalized_phone, phone, normalized_email] if candidate]
        for query in queries:
            for candidate in await self.search_contacts(query):
                raw_id = candidate.get("id")
                if raw_id: candidates[int(raw_id)] = candidate

        for candidate_id, candidate in candidates.items():
            full_contact = candidate if candidate.get("custom_fields_values") else await self.get_contact(candidate_id)
            if not full_contact: continue
            candidate_phone = extract_phone_from_contact_obj(full_contact)
            candidate_email = extract_email_from_contact_obj(full_contact)
            if normalized_phone and candidate_phone == normalized_phone: await self.update_contact(candidate_id, name=lead_name, phone=normalized_phone, email=normalized_email); refreshed_contact = await self.get_contact(candidate_id); return refreshed_contact or full_contact
            if normalized_email and candidate_email == normalized_email: await self.update_contact(candidate_id, name=lead_name, phone=normalized_phone, email=normalized_email); refreshed_contact = await self.get_contact(candidate_id); return refreshed_contact or full_contact

        return await self.create_contact(name=lead_name, phone=normalized_phone, email=normalized_email)

    async def find_lead_by_order_number(self, order_number: str | int) -> dict[str, Any] | None:
        code_str = str(order_number).strip()
        needle = f"№{code_str} "
        pattern = re.compile(rf"№{re.escape(code_str)}\s")
        page, limit, max_pages = 1, 50, 20
        while page <= max_pages:
            data = await self._get("/api/v4/leads", params={"query": needle, "limit": limit, "page": page})
            leads = (data.get("_embedded") or {}).get("leads") or []
            if not leads: return None

            for lead in leads:
                name = lead.get("name") or ""
                if not pattern.search(name): continue
                pipeline_id = lead.get("pipeline_id")
                if pipeline_id is not None and pipeline_id != self.PIPELINE_ID: continue
                return lead

            page += 1
        return None

    async def create_lead(self, *, name: str, status_id: int, price: int | None = None, custom_fields: dict[int, object] | None = None) -> dict[str, Any]:
        payload = build_lead_create_payload(name=name, pipeline_id=self.PIPELINE_ID, status_id=status_id, price=price, custom_fields=custom_fields)
        data = await self._post("/api/v4/leads", json=[self.transport.dump_payload(payload)])
        return ((data.get("_embedded") or {}).get("leads") or [{}])[0]

    async def add_lead_note(self, lead_id: int, text: str) -> dict[str, Any]:
        payload = build_lead_note_payload(lead_id=lead_id, text=text)
        return await self._post("/api/v4/leads/notes", json=[self.transport.dump_payload(payload)])

    async def update_lead_status(self, lead_id: int, status_id: int) -> dict[str, Any]:
        payload = LeadStatusUpdatePayload(id=lead_id, pipeline_id=self.PIPELINE_ID, status_id=status_id)
        data = await self._patch("/api/v4/leads", json=[self.transport.dump_payload(payload)])
        return ((data.get("_embedded") or {}).get("leads") or [{"id": lead_id, "status_id": status_id}])[0]

    async def link_contact_to_lead(self, lead_id: int, contact_id: int) -> dict[str, Any]:
        payload = build_lead_link_payload(contact_id=contact_id)
        return await self._post(f"/api/v4/leads/{lead_id}/link", json=[self.transport.dump_payload(payload)])

    async def create_lead_with_contact_and_note(self, *, lead_name: str, price: int, address_str: str, phone: str, email: str | None, order_number: str, delivery_service: str, note_text: str, payment_method: str, tg_nick: str | None = None, status_id: int | None = None, delivery_sum: Decimal | float | int | None = None, contact_id: int | None = None) -> dict[str, Any]:
        lead_custom_fields = build_order_lead_custom_fields(cf=self.CF, address_str=address_str, order_number=order_number, delivery_service=delivery_service, payment_method=payment_method, tg_nick=tg_nick, delivery_sum=delivery_sum)
        lead = await self.create_lead(name=f"Заказ №{order_number} с Приложения", price=price, custom_fields=lead_custom_fields, status_id=status_id or self.STATUS_IDS["main"])
        lead_id = int(lead["id"])
        if contact_id: await self.link_contact_to_lead(lead_id, contact_id)
        await self.add_lead_note(lead_id, note_text)
        return lead

amocrm_client = AsyncAmoCRM()
