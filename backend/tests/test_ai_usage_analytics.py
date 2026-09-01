from datetime import date

from src.app.services.ai.usage_analytics import _aggregate_bot_rows, _trend_buckets


def test_aggregate_bot_rows_uses_real_internal_report_fields():
    result = _aggregate_bot_rows([
        {
            "Айди Телеграм": 1001,
            "Всего запросов": 3,
            "Входящие токены": 120,
            "Кэшированные входящие токены": 40,
            "Исходящие токены": 30,
            "Стоимость всего в $": 0.02,
        },
        {
            "Айди Телеграм": 1002,
            "Всего запросов": 2,
            "Входящие токены": 80,
            "Кэшированные входящие токены": 20,
            "Исходящие токены": 10,
            "Стоимость всего в $": 0.01,
        },
    ])

    assert result == {
        "users": 2,
        "requests": 5,
        "input": 200,
        "cached": 60,
        "output": 40,
        "cost": 0.03,
    }


def test_trend_buckets_limit_remote_report_calls_for_long_periods():
    granularity, buckets = _trend_buckets(date(2025, 9, 2), date(2026, 9, 1), 365)

    assert granularity == "monthly"
    assert buckets[0] == (date(2025, 9, 2), date(2025, 9, 30))
    assert buckets[-1] == (date(2026, 9, 1), date(2026, 9, 1))
    assert len(buckets) == 13


def test_trend_buckets_are_daily_for_dashboard_default_period():
    granularity, buckets = _trend_buckets(date(2026, 8, 3), date(2026, 9, 1), 30)

    assert granularity == "daily"
    assert len(buckets) == 30
    assert all(start == end for start, end in buckets)
