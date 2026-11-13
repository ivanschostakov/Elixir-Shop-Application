from decimal import Decimal
from unittest.mock import AsyncMock, Mock

import pytest

from src.app.modules.admin.schemas.referrals import AdminReferralSummaryRead
from src.app.services.admin.referrals import referral_summary


@pytest.mark.anyio
@pytest.mark.parametrize(("raw", "expected"), [("1.469387755102", "1.47"), ("1.005", "1.01"), (None, "0.00")])
async def test_referral_summary_rounds_database_average_to_api_precision(raw, expected):
    db = Mock(execute=AsyncMock(side_effect=[
        Mock(one=Mock(return_value=(49, 0, Decimal(raw) if raw else None, 5, 0))),
        Mock(all=Mock(return_value=[])),
        Mock(one=Mock(return_value=(0, 0, 0, 0))),
    ]))
    result = AdminReferralSummaryRead.model_validate(await referral_summary(db))
    assert result.average_discount_percent == Decimal(expected)
