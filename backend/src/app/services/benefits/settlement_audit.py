"""Read-only reconciliation export: python -m src.app.services.benefits.settlement_audit."""

import asyncio
from collections import Counter
from datetime import datetime, timezone
import json
import time
from uuid import UUID

import httpx
from sqlalchemy import text

from src.database import engine
from src.integrations.moysklad.client import get_moysklad_client
from src.normalize import normalize_email, normalize_phone
from .settlement import parse_settlement


def identity_issues(user: dict, card: dict, *, link_count: int) -> list[str]:
    issues = []
    if link_count > 1:
        issues.append("shared_local_link")
    if card.get("archived"):
        issues.append("archived_counterparty")
    if card.get("companyType") not in {None, "individual"}:
        issues.append("non_individual_counterparty")
    for local_key, remote_key, normalizer in [
        ("email", "email", normalize_email),
        ("phone_number", "phone", normalize_phone),
    ]:
        local = normalizer(user.get(local_key))
        remote = normalizer(card.get(remote_key))
        if local and remote and local != remote:
            issues.append(f"{remote_key}_mismatch")
    return issues


async def run_audit() -> dict:
    # Use SQL mappings rather than ORM objects: no lazy loads, updates or commits.
    async with engine.connect() as db:
        await db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        await db.execute(text("SET LOCAL statement_timeout = '30s'"))
        async def rows(query):
            return [dict(row) for row in (await db.execute(text(query))).mappings()]
        users = await rows("SELECT id, email, phone_number, moysklad_counterparty_id FROM users ORDER BY id")
        credits = await rows("""SELECT id, user_id, order_id, source_kind, points, spent_points, status,
            earned_at, available_at, expires_at, expired_at, reversed_at,
            moysklad_bonus_program_id, moysklad_bonus_transaction_id, moysklad_debit_transaction_id,
            (sync_error IS NOT NULL) AS has_sync_error FROM loyalty_bonus_credits ORDER BY id""")
        accruals = await rows("""SELECT id, purchase_id, beneficiary_user_id, commission_amount, currency,
            status, wallet_sync_status, bonus_points_credited, bonus_rubles_credited,
            moysklad_bonus_transaction_id, wallet_reversal_transaction_id
            FROM app_referral_accruals ORDER BY id""")
        orders = await rows("""SELECT id, user_id, status, payment_status, payment_paid_at, grand_total,
            currency, moysklad_customerorder_id, moysklad_invoiceout_id FROM orders ORDER BY id""")
        await db.rollback()

    client = get_moysklad_client()
    if not client.is_configured():
        raise RuntimeError("MoySklad is not configured")
    http = await client.client()
    async def read(path, **params):
        await asyncio.sleep(0.25)
        response = await http.get(path, params=params, timeout=15)
        response.raise_for_status()
        return response.json()

    links = Counter(str(user["moysklad_counterparty_id"]) for user in users if user["moysklad_counterparty_id"])
    records, failures = [], []
    snapshots = {}
    try:
        for user in users:
            cid = user["moysklad_counterparty_id"]
            record = {"user_id": user["id"], "counterparty_id": str(cid) if cid else None, "issues": []}
            records.append(record)
            try:
                if not cid:
                    record["issues"].append("unlinked")
                    candidates = {}
                    for field, normalizer in [("email", normalize_email), ("phone_number", normalize_phone)]:
                        value = normalizer(user.get(field))
                        if not value:
                            continue
                        data = await read("/entity/counterparty", search=value, limit=100, expand="contactpersons")
                        matches = []
                        matcher = client._counterparty_email_matches if field == "email" else client._counterparty_phone_matches
                        for row in data.get("rows", []):
                            if matcher(row, value):
                                matches.append(row.get("id"))
                        candidates[field] = matches
                        if len(data.get("rows", [])) >= 100:
                            record["issues"].append("truncated_contact_search")
                    record["exact_contact_candidates"] = candidates
                    # Candidates are evidence for review, never instructions to relink.
                    continue
                if str(cid) not in snapshots:
                    card = await read(f"/entity/counterparty/{cid}")
                    report = await read(f"/report/counterparty/{cid}")
                    snapshots[str(cid)] = (card, parse_settlement(card, report, expected_id=UUID(str(cid)), now=time.time()))
                card, value = snapshots[str(cid)]
                record["issues"] += identity_issues(user, card, link_count=links[str(cid)])
                record.update({
                    "balance_rubles": str(value.balance_rubles),
                    "purchases_rubles": str(value.total_purchases_rubles),
                    "program": value.loyalty_program,
                    "legacy_bonus_points": card.get("bonusPoints"),
                    "fetched_at": value.fetched_at.isoformat(),
                })
                if value.issue:
                    record["issues"].append(value.issue)
            except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
                status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
                record["issues"].append("read_failed")
                failures.append({"user_id": user["id"], "status": status, "type": type(exc).__name__})
                if status in {401, 403, 429}:
                    break

        paid_orders = []
        if not failures:
            for order in orders:
                if order["payment_status"] != "paid":
                    continue
                row = {"order_id": order["id"], "customerorder_id": order["moysklad_customerorder_id"]}
                paid_orders.append(row)
                if not order["moysklad_customerorder_id"]:
                    row["issue"] = "unlinked_paid_order"
                    continue
                try:
                    data = await read(f"/entity/customerorder/{order['moysklad_customerorder_id']}")
                    row.update({key: data.get(key) for key in ("sum", "payedSum", "shippedSum", "invoicedSum")})
                    row["amount_unit"] = "minor_currency_units"
                except httpx.HTTPError as exc:
                    status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
                    row["issue"] = "read_failed"
                    failures.append({"order_id": order["id"], "status": status, "type": type(exc).__name__})
                    if status in {401, 403, 429}:
                        break
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "read_only": True,
            "complete": not failures and len(records) == len(users),
            "summary": {"users": len(users), "linked": sum(links.values()), "unique_links": len(links),
                "review_required": sum(bool(row["issues"]) for row in records),
                "local_credits": len(credits), "local_referral_accruals": len(accruals), "orders": len(orders)},
            "customers": records, "local_credits": credits, "local_referral_accruals": accruals,
            "orders": orders, "paid_order_shipping_evidence": paid_orders, "failures": failures,
            "migration_instruction": "NO AUTOMATIC TRANSFER: points and signed settlement balance are different ledgers; reconcile existing MS payment documents before approving any amount.",
        }
    finally:
        await http.aclose()


async def main():
    try:
        print(json.dumps(await run_audit(), ensure_ascii=False, indent=2, default=str))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
