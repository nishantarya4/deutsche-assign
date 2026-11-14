import asyncio
from datetime import datetime, timedelta

from app import db

# Wake up one minute after midnight, so the new day has definitely started.
SECONDS_AFTER_MIDNIGHT = 60


def seconds_until_next_midnight(now):
    """Return how many seconds are left from now until the next midnight."""
    tomorrow = now.date() + timedelta(days=1)
    next_midnight = datetime.combine(tomorrow, datetime.min.time())
    return (next_midnight - now).total_seconds()


def run_expiry_job(database_path, today):
    """Open the database, mark trades past maturity as expired, and return how many changed."""
    conn = db.connect(database_path)
    try:
        return db.mark_expired_trades(conn, today)
    finally:
        conn.close()


async def run_daily_expiry(database_path, get_today):
    """Keep running forever: wait until just after midnight, then run the expiry job."""
    while True:
        wait = seconds_until_next_midnight(datetime.now()) + SECONDS_AFTER_MIDNIGHT
        await asyncio.sleep(wait)
        run_expiry_job(database_path, get_today())
