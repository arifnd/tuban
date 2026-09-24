from datetime import UTC, datetime, timedelta


def utc_day_start() -> datetime:
    now = datetime.now(UTC)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def utc_month_start() -> datetime:
    return utc_day_start().replace(day=1)


def utc_week_start() -> datetime:
    day = utc_day_start()
    return day - timedelta(days=day.weekday())
