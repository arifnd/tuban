from datetime import datetime, timedelta

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from src.tickets.models import TicketNumberSeq

BUSINESS_START = 9
BUSINESS_END = 17


def _next_business_day(moment: datetime) -> datetime:
    nxt = moment + timedelta(days=1)
    while nxt.weekday() >= 5:  # Saturday/Sunday
        nxt += timedelta(days=1)
    return nxt.replace(hour=BUSINESS_START, minute=0, second=0, microsecond=0)


def business_hours_add(start: datetime, hours: int) -> datetime:
    """Add ``hours`` working hours (Mon-Fri, 09:00-17:00) to ``start``."""
    if hours <= 0:
        return start
    current = start
    remaining = float(hours)
    while remaining > 0:
        if current.weekday() >= 5:
            current = _next_business_day(current - timedelta(days=1))
            continue
        if current.hour < BUSINESS_START:
            current = current.replace(hour=BUSINESS_START, minute=0, second=0, microsecond=0)
        elif current.hour >= BUSINESS_END:
            current = _next_business_day(current)
            continue
        end_of_day = current.replace(hour=BUSINESS_END, minute=0, second=0, microsecond=0)
        available = (end_of_day - current).total_seconds() / 3600
        if remaining <= available:
            return current + timedelta(hours=remaining)
        remaining -= available
        current = _next_business_day(current)
    return current


async def next_ticket_number(db: AsyncSession) -> str:
    """Atomically increment the sequence and return a ``TKT-000123`` style number."""
    if await db.get(TicketNumberSeq, 1) is None:
        db.add(TicketNumberSeq(id=1, value=0))
        await db.flush()
    value = await db.scalar(update(TicketNumberSeq).where(TicketNumberSeq.id == 1).values(value=TicketNumberSeq.value + 1).returning(TicketNumberSeq.value))
    return f"TKT-{int(value or 1):06d}"
