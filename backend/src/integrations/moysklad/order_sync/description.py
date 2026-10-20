from decimal import Decimal
from src.database.models import Order
from src.normalize import extract_dict, optional_str
from src.integrations.moysklad.settlement_checkout import order_settlement, money as settlement_money
from .address import _decimal_or_zero


def _build_order_description(order: Order) -> str:
    comment = optional_str(order.comment)
    subtotal = Decimal(order.basket_subtotal)
    delivery = Decimal(order.delivery_total)
    total = Decimal(order.grand_total)
    settlement = order_settlement(order)
    if settlement:
        gross = settlement_money(settlement["gross_rubles"])
        lines = [order.order_code, f"Товары до скидок: {subtotal:.2f}",
            f"Скидка на товары: {subtotal + delivery - gross:.2f}",
            f"Стоимость заказа с доставкой: {gross:.2f}", f"Доставка: {delivery:.2f}",
            "Клиент выбрал оплату с баланса. Точная сумма к оплате определяется связанным счётом МойСклад.",
            "Не создавать повторное списание или дополнительный входящий платёж на сумму баланса."]
    else: lines = [order.order_code, f"Товары до скидок: {subtotal:.2f}", f"Скидки и бонусы: {subtotal + delivery - total:.2f}", f"Товары после скидок: {total - delivery:.2f}", f"Доставка (отдельное поле): {delivery:.2f}", f"Итого к оплате в приложении: {total:.2f}"]
    for item in order.items: lines.append(f"{item.product_name}: {item.quantity} x {Decimal(item.unit_price):.2f} (до скидок)")
    benefits = extract_dict(extract_dict(order.checkout_snapshot).get("benefits"))
    for application in benefits.get("applications") or []:
        application = extract_dict(application)
        amount = _decimal_or_zero(application.get("discount_amount"))
        if amount <= 0: continue
        if application.get("source_kind") == "moysklad_settlement": continue
        label = "Бонусы" if application.get("source_kind") == "moysklad_bonus" else f"Промокод {application.get('code') or ''}".strip()
        lines.append(f"{label}: -{amount:.2f}")
    if comment: lines.append(comment)
    return "\n".join(lines)
