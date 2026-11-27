from fastapi import APIRouter, Depends, HTTPException, Request
from src.app.services.platform_availability import mobile_shop_request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from config import LOYALTY_PHOTO_REVIEW_BONUS_POINTS, LOYALTY_TEXT_REVIEW_BONUS_POINTS
from .schemas.benefits import AppRewardsRead, BenefitCheckPayload, BenefitCheckRead
from src.app.modules.auth.dependencies import get_current_user
from src.app.services.benefits import app_welcome
from src.app.services.benefits.service import resolve_benefits_for_user
from src.app.services.catalog_merchandising import catalog_unit_price
from src.app.services.delivery_quotes import build_bitrix_delivery_items
from src.app.services.discounts import discountable_subtotal_for_lines
from src.database import get_db
from src.database.crud import get_basket_by_user_id, get_order_draft_by_id
from src.database.models.auth.user import User

my_benefits_router = APIRouter(prefix="/benefits", tags=["my_benefits"])


@my_benefits_router.get("/welcome-notice")
async def get_welcome_notice(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    from src.app.services.notifications.welcome import pending_notice
    return await pending_notice(db, current_user.id)


@my_benefits_router.post("/welcome-notice/{credit_id}/seen", status_code=204)
async def mark_welcome_notice_seen(credit_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    from src.app.services.notifications.welcome import acknowledge_notice
    await acknowledge_notice(db, current_user.id, credit_id)


@my_benefits_router.post("/welcome-reminder")
async def get_daily_welcome_reminder(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    from src.app.services.notifications.welcome import claim_in_app_reminder
    return await claim_in_app_reminder(db, current_user.id)


@my_benefits_router.get("/rewards", response_model=AppRewardsRead)
async def get_my_app_rewards(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> AppRewardsRead:
    credit, available = await app_welcome.wallet(db, current_user.id)
    return AppRewardsRead(
        welcome_balance_rubles=available,
        welcome_expires_at=credit.expires_at if credit else None,
        text_review_points=LOYALTY_TEXT_REVIEW_BONUS_POINTS,
        photo_review_points=LOYALTY_PHOTO_REVIEW_BONUS_POINTS,
    )


@my_benefits_router.post("/check", response_model=BenefitCheckRead, status_code=status.HTTP_200_OK)
async def check_my_benefits(payload: BenefitCheckPayload, request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> BenefitCheckRead:
    subtotal = payload.subtotal
    discountable_subtotal = payload.discountable_subtotal
    currency = payload.currency
    quote_items = None
    delivery_total = None

    if payload.use_basket and payload.draft_id is not None:
        raise HTTPException(status_code=422, detail="Choose the basket or a draft")

    if payload.draft_id is not None:
        draft = await get_order_draft_by_id(db, payload.draft_id, user_id=current_user.id)
        if draft is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Черновик заказа не найден / Order draft was not found",
            )
        if not draft.items:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Черновик заказа пуст / Order draft is empty",
            )

        subtotal = draft.basket_subtotal
        discountable_subtotal = await discountable_subtotal_for_lines(
            db,
            ((item.product_id, item.line_total) for item in draft.items),
        )
        currency = draft.currency
        delivery_total = draft.delivery_total
        quote_items = await build_bitrix_delivery_items(db, draft.items)
    elif payload.use_basket:
        basket = await get_basket_by_user_id(db, current_user.id)
        if basket is None or not basket.items:
            raise HTTPException(status_code=409, detail="Корзина пуста / Basket is empty")
        lines = [(item.product_id, catalog_unit_price(item.variant.price, item.product) * item.quantity) for item in basket.items]
        subtotal = sum(amount for _, amount in lines)
        discountable_subtotal = await discountable_subtotal_for_lines(db, lines)
        currency = basket.currency
        delivery_total = basket.delivery_total
        quote_items = [{
            "variant_system_id": str(item.variant.system_id),
            "product_system_id": str(item.product.system_id),
            "sku": item.variant.sku or item.product.sku,
            "quantity": item.quantity,
        } for item in basket.items]

    resolved = await resolve_benefits_for_user(
        db,
        user=current_user,
        entered_code=payload.code,
        subtotal=subtotal,
        discountable_subtotal=discountable_subtotal,
        delivery_total=delivery_total,
        currency=currency,
        quote_items=quote_items,
        bonus_rubles_to_use=payload.bonus_rubles_to_use, use_bonus_rubles=payload.use_bonus_rubles,
        reward_mode=payload.reward_mode,
        mobile_welcome=mobile_shop_request(request.headers),
    )
    await db.commit()
    return BenefitCheckRead.model_validate(resolved)
