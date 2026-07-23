import csv
import zipfile

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable, Literal
from xml.sax.saxutils import escape

from sqlalchemy import func, or_, select
from pydantic import BaseModel, Field
from sqlalchemy.orm import selectinload

from config import PRIVATE_MEDIA_DIR
from src.database import SessionLocal
from src.database.models import Admin, AdminAuditLog, Order, Product, ProductByCategory, Review, User, Variant
from src.database.models.orders.history import build_status_code_clause, get_order_status_code


MAX_EXPORT_ROWS = 20_000
EXPORT_ROOT = PRIVATE_MEDIA_DIR / "admin_exports"


class ExportJobPayload(BaseModel):
    resource: Literal["orders", "customers", "products", "reviews", "audit"]
    format: Literal["csv", "xlsx"]
    columns: list[str] = Field(min_length=1, max_length=32)
    filters: dict[str, Any] = Field(default_factory=dict)
    selected_ids: list[int] = Field(default_factory=list, max_length=5000)
    locale: Literal["ru", "en"] = "ru"
    idempotency_key: str = Field(min_length=8, max_length=160)

RESOURCE_PERMISSIONS = {
    "orders": "orders.read",
    "customers": "customers.read",
    "products": "catalog.read",
    "reviews": "reviews.read",
    "audit": "audit.read",
}

EXPORT_COLUMNS: dict[str, dict[str, tuple[str, str]]] = {
    "orders": {
        "id": ("ID", "ID"),
        "order_code": ("Заказ", "Order"),
        "status": ("Статус", "Status"),
        "customer": ("Клиент", "Customer"),
        "email": ("Email", "Email"),
        "phone": ("Телефон", "Phone"),
        "items_count": ("Позиций", "Items"),
        "total_quantity": ("Количество", "Quantity"),
        "grand_total": ("Сумма", "Total"),
        "payment_status": ("Оплата", "Payment status"),
        "delivery_service": ("Доставка", "Delivery"),
        "created_at": ("Создан", "Created"),
    },
    "customers": {
        "id": ("ID", "ID"),
        "customer": ("Клиент", "Customer"),
        "email": ("Email", "Email"),
        "phone": ("Телефон", "Phone"),
        "telegram": ("Telegram", "Telegram"),
        "orders_count": ("Заказов", "Orders"),
        "paid_total": ("LTV", "LTV"),
        "is_active": ("Активен", "Active"),
        "is_verified": ("Подтверждён", "Verified"),
        "last_order_at": ("Последний заказ", "Last order"),
        "created_at": ("Регистрация", "Registered"),
    },
    "products": {
        "id": ("ID", "ID"),
        "sku": ("SKU", "SKU"),
        "name": ("Товар", "Product"),
        "in_stock": ("В наличии", "In stock"),
        "stock": ("Остаток", "Stock"),
        "price": ("Цена от", "Price from"),
        "priority": ("Приоритет", "Priority"),
        "archived": ("Архив", "Archived"),
        "updated_at": ("Обновлён", "Updated"),
    },
    "reviews": {
        "id": ("ID", "ID"),
        "product": ("Товар", "Product"),
        "author": ("Автор", "Author"),
        "email": ("Email", "Email"),
        "rating": ("Оценка", "Rating"),
        "text": ("Отзыв", "Review"),
        "status": ("Статус", "Status"),
        "created_at": ("Создан", "Created"),
    },
    "audit": {
        "id": ("ID", "ID"),
        "actor": ("Сотрудник", "Staff member"),
        "action": ("Действие", "Action"),
        "entity_type": ("Сущность", "Entity"),
        "entity_id": ("ID сущности", "Entity ID"),
        "ip": ("IP", "IP"),
        "request_id": ("Request ID", "Request ID"),
        "created_at": ("Время", "Time"),
    },
}

FILTER_KEYS = {
    "orders": frozenset(("q", "status_code", "payment_status", "created_from", "created_to")),
    "customers": frozenset(("q", "is_active", "is_verified")),
    "products": frozenset(("q", "archived", "in_stock", "category_id")),
    "reviews": frozenset(("status", "product_id")),
    "audit": frozenset(("q", "entity_type", "actor_user_id")),
}
ORDER_STATUS_CODES = frozenset((
    "created", "invoice_sent", "paid", "waiting_response", "packaged", "sent",
    "delivered", "canceled", "completed", "refund_declined",
))


def normalize_export_payload(payload: ExportJobPayload | Any) -> dict[str, Any]:
    allowed_columns = EXPORT_COLUMNS[payload.resource]
    columns = list(dict.fromkeys(payload.columns))
    invalid_columns = [column for column in columns if column not in allowed_columns]
    if invalid_columns:
        raise ValueError(f"Unsupported export columns: {', '.join(invalid_columns)}")

    unknown_filters = sorted(set(payload.filters) - FILTER_KEYS[payload.resource])
    if unknown_filters:
        raise ValueError(f"Unsupported export filters: {', '.join(unknown_filters)}")

    filters = dict(payload.filters)
    if "q" in filters and (not isinstance(filters["q"], str) or len(filters["q"]) > 100):
        raise ValueError("Export search filter must be a string up to 100 characters")
    if payload.resource == "orders":
        if filters.get("status_code") and filters["status_code"] not in ORDER_STATUS_CODES:
            raise ValueError("Unsupported order status filter")
        for key in ("created_from", "created_to"):
            if filters.get(key) and _parse_datetime(filters[key]) is None:
                raise ValueError(f"Invalid date filter: {key}")
    if payload.resource in {"customers", "products"}:
        for key in FILTER_KEYS[payload.resource] & {"is_active", "is_verified", "archived", "in_stock"}:
            if key in filters and _parse_bool(filters[key]) is None:
                raise ValueError(f"Invalid boolean filter: {key}")
    if payload.resource == "reviews" and filters.get("status") not in {None, "pending", "published", "rejected"}:
        raise ValueError("Unsupported review status filter")
    for key in ("category_id", "product_id", "actor_user_id"):
        if key in filters:
            try:
                numeric_value = int(filters[key])
            except (TypeError, ValueError):
                raise ValueError(f"Invalid numeric filter: {key}") from None
            if numeric_value <= 0:
                raise ValueError(f"Invalid numeric filter: {key}")
            filters[key] = numeric_value

    selected_ids = list(dict.fromkeys(payload.selected_ids))
    if any(item_id <= 0 for item_id in selected_ids):
        raise ValueError("Selected IDs must be positive")
    return {
        **payload.model_dump(mode="json"),
        "columns": columns,
        "filters": filters,
        "selected_ids": selected_ids,
    }


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.lower() in {"true", "false"}:
        return value.lower() == "true"
    return None


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    return str(value)


def _yes_no(value: bool, locale: str) -> str:
    if locale == "en":
        return "Yes" if value else "No"
    return "Да" if value else "Нет"


def _review_status(review: Review) -> str:
    if review.rejected_at is not None:
        return "rejected"
    return "published" if review.moderated else "pending"


async def _order_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    filters = payload["filters"]
    clauses = []
    if q := str(filters.get("q") or "").strip():
        pattern = f"%{q}%"
        clauses.append(or_(
            Order.order_code.ilike(pattern),
            Order.payment_invoice_id.ilike(pattern),
            User.email.ilike(pattern),
            User.phone_number.ilike(pattern),
            User.name.ilike(pattern),
            User.surname.ilike(pattern),
        ))
    if status_code := filters.get("status_code"):
        clauses.append(build_status_code_clause(Order, status_code))
    if payment_status := filters.get("payment_status"):
        clauses.append(Order.payment_status == str(payment_status))
    if created_from := _parse_datetime(filters.get("created_from")):
        clauses.append(Order.created_at >= created_from)
    if created_to := _parse_datetime(filters.get("created_to")):
        clauses.append(Order.created_at <= created_to)
    if payload["selected_ids"]:
        clauses.append(Order.id.in_(payload["selected_ids"]))

    async with SessionLocal() as db:
        rows = (await db.execute(
            select(Order, User)
            .join(User, User.id == Order.user_id)
            .where(*clauses)
            .order_by(Order.created_at.desc(), Order.id.desc())
            .limit(MAX_EXPORT_ROWS)
        )).all()
    return [{
        "id": order.id,
        "order_code": order.order_code,
        "status": get_order_status_code(order),
        "customer": f"{user.name} {user.surname}".strip(),
        "email": user.email,
        "phone": user.phone_number,
        "items_count": order.items_count,
        "total_quantity": order.total_quantity,
        "grand_total": order.grand_total,
        "payment_status": order.payment_status,
        "delivery_service": order.selected_delivery_service,
        "created_at": order.created_at,
    } for order, user in rows]


async def _customer_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    filters = payload["filters"]
    aggregate = select(
        Order.user_id.label("user_id"),
        func.count(Order.id).label("orders_count"),
        func.coalesce(
            func.sum(Order.grand_total).filter(Order.is_paid.is_(True), Order.is_canceled.is_(False)),
            0,
        ).label("paid_total"),
        func.max(Order.created_at).label("last_order_at"),
    ).group_by(Order.user_id).subquery()
    clauses = []
    if q := str(filters.get("q") or "").strip():
        pattern = f"%{q}%"
        clauses.append(or_(
            User.email.ilike(pattern),
            User.phone_number.ilike(pattern),
            User.name.ilike(pattern),
            User.surname.ilike(pattern),
            User.telegram_username.ilike(pattern),
        ))
    for key, field in (("is_active", User.is_active), ("is_verified", User.is_verified)):
        value = _parse_bool(filters.get(key))
        if value is not None:
            clauses.append(field.is_(value))
    if payload["selected_ids"]:
        clauses.append(User.id.in_(payload["selected_ids"]))

    async with SessionLocal() as db:
        rows = (await db.execute(
            select(User, aggregate.c.orders_count, aggregate.c.paid_total, aggregate.c.last_order_at)
            .outerjoin(aggregate, aggregate.c.user_id == User.id)
            .where(*clauses)
            .order_by(User.created_at.desc(), User.id.desc())
            .limit(MAX_EXPORT_ROWS)
        )).all()
    locale = payload["locale"]
    return [{
        "id": user.id,
        "customer": f"{user.name} {user.surname}".strip(),
        "email": user.email,
        "phone": user.phone_number,
        "telegram": user.telegram_username,
        "orders_count": int(orders_count or 0),
        "paid_total": paid_total or 0,
        "is_active": _yes_no(user.is_active, locale),
        "is_verified": _yes_no(user.is_verified, locale),
        "last_order_at": last_order_at,
        "created_at": user.created_at,
    } for user, orders_count, paid_total, last_order_at in rows]


async def _product_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    filters = payload["filters"]
    variants = select(
        Variant.product_id.label("product_id"),
        func.coalesce(func.sum(Variant.stock), 0).label("stock"),
        func.min(Variant.price).label("price"),
    ).where(Variant.archived.is_(False)).group_by(Variant.product_id).subquery()
    clauses = []
    if q := str(filters.get("q") or "").strip():
        pattern = f"%{q}%"
        clauses.append(or_(Product.name.ilike(pattern), Product.sku.ilike(pattern)))
    for key, field in (("archived", Product.archived), ("in_stock", Product.in_stock)):
        value = _parse_bool(filters.get(key))
        if value is not None:
            clauses.append(field.is_(value))
    if payload["selected_ids"]:
        clauses.append(Product.id.in_(payload["selected_ids"]))

    statement = select(Product, variants.c.stock, variants.c.price).outerjoin(
        variants, variants.c.product_id == Product.id
    ).where(*clauses)
    category_id = filters.get("category_id")
    if category_id:
        statement = statement.join(ProductByCategory).where(ProductByCategory.category_id == int(category_id))
    async with SessionLocal() as db:
        rows = (await db.execute(
            statement.order_by(Product.in_stock.desc(), Product.priority.desc(), Product.id.desc()).limit(MAX_EXPORT_ROWS)
        )).all()
    locale = payload["locale"]
    return [{
        "id": product.id,
        "sku": product.sku,
        "name": product.name,
        "in_stock": _yes_no(product.in_stock, locale),
        "stock": int(stock or 0),
        "price": price,
        "priority": product.priority,
        "archived": _yes_no(product.archived, locale),
        "updated_at": product.updated_at,
    } for product, stock, price in rows]


async def _review_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    filters = payload["filters"]
    clauses = []
    review_status = filters.get("status")
    if review_status == "pending":
        clauses.extend((Review.moderated.is_(False), Review.rejected_at.is_(None)))
    elif review_status == "published":
        clauses.extend((Review.moderated.is_(True), Review.rejected_at.is_(None)))
    elif review_status == "rejected":
        clauses.append(Review.rejected_at.is_not(None))
    if product_id := filters.get("product_id"):
        clauses.append(Review.product_id == int(product_id))
    if payload["selected_ids"]:
        clauses.append(Review.id.in_(payload["selected_ids"]))

    async with SessionLocal() as db:
        rows = (await db.execute(
            select(Review, Product.name, User)
            .join(Product, Product.id == Review.product_id)
            .outerjoin(User, User.id == Review.user_id)
            .where(*clauses)
            .order_by(Review.created_at.desc(), Review.id.desc())
            .limit(MAX_EXPORT_ROWS)
        )).all()
    return [{
        "id": review.id,
        "product": product_name,
        "author": f"{user.name} {user.surname}".strip() if user else review.guest_name,
        "email": user.email if user else review.guest_email,
        "rating": review.value,
        "text": review.text,
        "status": _review_status(review),
        "created_at": review.created_at,
    } for review, product_name, user in rows]


async def _audit_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    filters = payload["filters"]
    clauses = []
    if q := str(filters.get("q") or "").strip():
        pattern = f"%{q}%"
        clauses.append(or_(AdminAuditLog.action.ilike(pattern), AdminAuditLog.entity_id.ilike(pattern)))
    if entity_type := filters.get("entity_type"):
        clauses.append(AdminAuditLog.entity_type == str(entity_type))
    if actor_user_id := filters.get("actor_user_id"):
        clauses.append(AdminAuditLog.actor_user_id == int(actor_user_id))
    if payload["selected_ids"]:
        clauses.append(AdminAuditLog.id.in_(payload["selected_ids"]))

    async with SessionLocal() as db:
        rows = list((await db.execute(
            select(AdminAuditLog)
            .options(selectinload(AdminAuditLog.actor).joinedload(Admin.user))
            .where(*clauses)
            .order_by(AdminAuditLog.created_at.desc(), AdminAuditLog.id.desc())
            .limit(MAX_EXPORT_ROWS)
        )).scalars().all())
    return [{
        "id": row.id,
        "actor": f"{row.actor.user.name} {row.actor.user.surname}".strip() if row.actor else "System",
        "action": row.action,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "ip": row.ip_address,
        "request_id": row.request_id,
        "created_at": row.created_at,
    } for row in rows]


ROW_BUILDERS = {
    "orders": _order_rows,
    "customers": _customer_rows,
    "products": _product_rows,
    "reviews": _review_rows,
    "audit": _audit_rows,
}


def _safe_spreadsheet_text(value: Any) -> str:
    result = _text(value)
    if result.lstrip().startswith(("=", "+", "-", "@")):
        return f"'{result}"
    return result


def _write_csv(path: Path, headers: list[str], rows: Iterable[list[Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.writer(output)
        writer.writerow(headers)
        for row in rows:
            writer.writerow([_safe_spreadsheet_text(value) for value in row])


def _column_letter(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _xlsx_cell(reference: str, value: Any) -> str:
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        return f'<c r="{reference}"><v>{escape(_text(value))}</v></c>'
    text_value = escape(_safe_spreadsheet_text(value))
    return f'<c r="{reference}" t="inlineStr"><is><t xml:space="preserve">{text_value}</t></is></c>'


def _write_xlsx(path: Path, headers: list[str], rows: list[list[Any]]) -> None:
    sheet_rows = [headers, *rows]
    sheet_xml = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
                 '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>']
    for row_index, row in enumerate(sheet_rows, start=1):
        cells = "".join(
            _xlsx_cell(f"{_column_letter(column_index)}{row_index}", value)
            for column_index, value in enumerate(row, start=1)
        )
        sheet_xml.append(f'<row r="{row_index}">{cells}</row>')
    sheet_xml.append("</sheetData></worksheet>")

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as workbook:
        workbook.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '</Types>')
        workbook.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>')
        workbook.writestr("xl/workbook.xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Export" sheetId="1" r:id="rId1"/></sheets></workbook>')
        workbook.writestr("xl/_rels/workbook.xml.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '</Relationships>')
        workbook.writestr("xl/worksheets/sheet1.xml", "".join(sheet_xml))


async def generate_admin_export(input_json: dict[str, Any], run_id: int) -> dict[str, Any]:
    payload_model = ExportJobPayload.model_validate(input_json)
    payload = normalize_export_payload(payload_model)
    rows = await ROW_BUILDERS[payload["resource"]](payload)
    columns = payload["columns"]
    locale_index = 1 if payload["locale"] == "en" else 0
    headers = [EXPORT_COLUMNS[payload["resource"]][column][locale_index] for column in columns]
    values = [[row.get(column) for column in columns] for row in rows]

    EXPORT_ROOT.mkdir(parents=True, exist_ok=True)
    suffix = payload["format"]
    file_name = f"{payload['resource']}-{run_id}.{suffix}"
    destination = EXPORT_ROOT / file_name
    temporary = destination.with_suffix(f".{suffix}.tmp")
    if suffix == "csv":
        _write_csv(temporary, headers, values)
    else:
        _write_xlsx(temporary, headers, values)
    temporary.replace(destination)
    return {
        "rows": len(rows),
        "file_name": file_name,
        "format": suffix,
        "resource": payload["resource"],
        "truncated": len(rows) >= MAX_EXPORT_ROWS,
    }


def resolve_export_file(file_name: str) -> Path | None:
    candidate = (EXPORT_ROOT / Path(file_name).name).resolve()
    if candidate.parent != EXPORT_ROOT.resolve() or not candidate.is_file():
        return None
    return candidate
