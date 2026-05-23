from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.app.modules.auth.dependencies import get_current_user
from src.app.modules.users.me.schemas.referrals import DepositRead
from src.app.services.referrals import get_deposit_balance
from src.app.services.referrals.ledger import DEPOSIT_ENTRY_TYPES
from src.database import get_db
from src.database.models import BusinessLedgerEntry, User

my_deposit_router = APIRouter(prefix="/deposit", tags=["my_deposit"])


@my_deposit_router.get("", response_model=DepositRead, status_code=status.HTTP_200_OK)
async def get_my_deposit(limit: int = Query(default=50, ge=1, le=200), db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> DepositRead:
    balance = await get_deposit_balance(db, current_user.id)
    ledger_entries = list((await db.execute(select(BusinessLedgerEntry).where(BusinessLedgerEntry.user_id == current_user.id, BusinessLedgerEntry.entry_type.in_(DEPOSIT_ENTRY_TYPES)).order_by(BusinessLedgerEntry.effective_at.desc(), BusinessLedgerEntry.id.desc()).limit(limit))).scalars().all())
    return DepositRead(balance=balance, currency=ledger_entries[0].currency if ledger_entries else "RUB", ledger_entries=ledger_entries)
