from datetime import date, datetime

from fastapi.testclient import TestClient

from app import db, main
from app.scheduler import run_expiry_job, seconds_until_next_midnight


def make_trade(trade_id, maturity_date):
    """Build a not-yet-expired trade dict with the given id and maturity date."""
    return {
        "trade_id": trade_id,
        "version": 1,
        "counterparty_id": "CP-1",
        "portfolio_id": "B1",
        "maturity_date": maturity_date,
        "created_date": date(2026, 11, 7),
        "expired": False,
    }


def store_trades(db_path, trades):
    """Save the given trades into the database file at db_path."""
    conn = db.connect(db_path)
    for trade in trades:
        db.insert_trade(conn, trade)
    conn.close()


def read_expired_flag(db_path, trade_id):
    """Return the stored expired flag of one trade in the database file at db_path."""
    conn = db.connect(db_path)
    trades = db.get_trades_by_id(conn, trade_id)
    conn.close()
    return trades[0]["expired"]


# ---------- seconds_until_next_midnight ----------

def test_one_hour_before_midnight():
    """At 23:00 there is one hour (3600 seconds) until midnight."""
    assert seconds_until_next_midnight(datetime(2026, 11, 7, 23, 0, 0)) == 3600


def test_exactly_at_midnight_waits_a_full_day():
    """At exactly 00:00 the next midnight is a full day (86400 seconds) away."""
    assert seconds_until_next_midnight(datetime(2026, 11, 7, 0, 0, 0)) == 86400


# ---------- run_expiry_job ----------

def test_expiry_job_marks_only_matured_trades(tmp_path):
    """The job opens the database, expires only trades past maturity, and says how many changed."""
    db_path = tmp_path / "job.db"
    store_trades(db_path, [
        make_trade("OLD", date(2026, 11, 10)),
        make_trade("FUTURE", date(2027, 1, 1)),
    ])

    changed = run_expiry_job(db_path, date(2026, 11, 11))

    assert changed == 1
    assert read_expired_flag(db_path, "OLD") is True
    assert read_expired_flag(db_path, "FUTURE") is False


# ---------- runs automatically when the app starts ----------

def test_app_startup_marks_matured_trades_without_any_request(tmp_path, monkeypatch):
    """Starting the app expires matured trades in the database, with no GET call at all."""
    db_path = tmp_path / "startup.db"
    store_trades(db_path, [make_trade("T1", date(2026, 11, 10))])

    def fixed_today():
        """Pretend today is the day after the trade matured."""
        return date(2026, 11, 11)

    monkeypatch.setattr(main, "DATABASE_PATH", db_path)
    monkeypatch.setattr(main, "get_today", fixed_today)

    with TestClient(main.app):
        pass  # entering starts the app, leaving shuts it down; no request is sent

    assert read_expired_flag(db_path, "T1") is True
