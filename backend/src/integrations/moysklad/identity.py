from fastapi import HTTPException

from src.normalize import coerce_uuid


class CounterpartyReviewRequired(HTTPException):
    def __init__(self, field, candidates=()):
        self.field = field
        self.candidates = tuple(sorted({str(cid) for row in candidates
            if isinstance(row, dict) and (cid := coerce_uuid(row.get("id"))) is not None}))
        super().__init__(409, "Нужна сверка карточки клиента МойСклад. Обратитесь в поддержку.")


def unique_contact(page, field, matches):
    rows = page.get("rows") if isinstance(page, dict) else None
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise HTTPException(503, "Не удалось проверить карточку клиента в МойСклад.")
    meta = page.get("meta") or {}
    size = meta.get("size", len(rows)) if isinstance(meta, dict) else None
    if type(size) is not int or size < len(rows):
        raise HTTPException(503, "Не удалось проверить полноту поиска в МойСклад.")
    hits = [row for row in rows if matches(row)]
    if (len(rows) >= 100 or size > len(rows) or meta.get("nextHref")
            or any(not row.get("id") for row in hits) or len({row["id"] for row in hits}) > 1):
        raise CounterpartyReviewRequired(field, hits)
    return hits[0] if hits else None
