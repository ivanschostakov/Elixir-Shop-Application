"""Durable manager notifications for ambiguous accounting identities."""
from sqlalchemy.dialects.postgresql import insert
from config import ufa_now
from src.database import SessionLocal
from src.database.models import AdminAlert


async def queue_counterparty_review(error, *, user_id=None, accrual_id=None):
    entity, key = ("customer", user_id) if user_id is not None else ("referral_accrual", accrual_id)
    if key is None:
        raise ValueError("An account or accrual is required for accounting review")
    now = ufa_now()
    message = (f"Проверьте совпадения по {error.field}. Карточки МойСклад: "
               + (", ".join(error.candidates) or "поиск не дал однозначного результата")
               + ". Сверьте владельца и устраните дубли в МойСклад. Закрытие уведомления не меняет привязку.")
    stmt = insert(AdminAlert).values(severity="warning", source="moysklad", code="counterparty_identity_review",
        title_ru="Нужна сверка карточки МойСклад", title_en="Review MoySklad customer identity",
        entity_type=entity, entity_id=str(key), path=f"/customers/{key}" if user_id is not None else None,
        fingerprint=f"moysklad:identity:{entity}:{key}", message=message, last_occurred_at=now)
    # The checkout/auth transaction may roll back. The review must survive it,
    # and concurrent lookups must leave one actionable alert, not one per login.
    async with SessionLocal.begin() as db:
        await db.execute(stmt.on_conflict_do_update(index_elements=[AdminAlert.fingerprint],
            set_={"message": message, "last_occurred_at": now, "occurrence_count": AdminAlert.occurrence_count + 1,
                  "resolved_at": None, "resolved_by_user_id": None}))
