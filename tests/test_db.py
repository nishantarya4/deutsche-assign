from datetime import date

import pytest

from app import db

TODAY = date(2026, 11, 7)


@pytest.fixture
def conn(tmp_path):
    """Give each test its own fresh database file, and close it afterwards."""
    connection = db.connect(tmp_path / "test.db")
    yield connection
    connection.close()


def make_trade(trade_id="T1", version=1, counterparty_id="CP-1",
               portfolio_id="B1", maturity_date=date(2027, 5, 20),
               created_date=TODAY, expired=False):
    """Build a trade dict with sensible defaults so tests only set what they care about."""
    return {
        "trade_id": trade_id,
        "version": version,
        "counterparty_id": counterparty_id,
        "portfolio_id": portfolio_id,
        "maturity_date": maturity_date,
        "created_date": created_date,
        "expired": expired,
    }


# ---------- insert and read back ----------

def test_inserted_trade_can_be_read_back(conn):
    """A trade we insert comes back with exactly the same fields."""
    trade = make_trade()
    db.insert_trade(conn, trade)
    assert db.get_trades_by_id(conn, "T1") == [trade]


def test_unknown_trade_id_returns_empty_list(conn):
    """Asking for a trade id that was never stored gives an empty list."""
    assert db.get_trades_by_id(conn, "NOPE") == []


# ---------- highest version ----------

def test_highest_version_is_none_when_trade_not_stored(conn):
    """No stored versions means the highest version is None."""
    assert db.get_highest_version(conn, "T1") is None


def test_highest_version_returns_the_largest(conn):
    """With versions 1 and 2 stored, the highest version is 2."""
    db.insert_trade(conn, make_trade(version=1))
    db.insert_trade(conn, make_trade(version=2))
    assert db.get_highest_version(conn, "T1") == 2


# ---------- replace ----------

def test_replace_updates_the_row_without_duplicating(conn):
    """Replacing a trade with the same id and version overwrites it, keeping one row."""
    db.insert_trade(conn, make_trade(counterparty_id="CP-1"))
    db.replace_trade(conn, make_trade(counterparty_id="CP-9"))
    stored = db.get_trades_by_id(conn, "T1")
    assert len(stored) == 1
    assert stored[0]["counterparty_id"] == "CP-9"


# ---------- ordering ----------

def test_list_trades_sorted_by_id_then_version_descending(conn):
    """All trades come back ordered by trade id, then highest version first."""
    db.insert_trade(conn, make_trade(trade_id="T2", version=1))
    db.insert_trade(conn, make_trade(trade_id="T3", version=3))
    db.insert_trade(conn, make_trade(trade_id="T1", version=1))
    db.insert_trade(conn, make_trade(trade_id="T2", version=2))
    order = [(t["trade_id"], t["version"]) for t in db.list_trades(conn)]
    assert order == [("T1", 1), ("T2", 2), ("T2", 1), ("T3", 3)]


def test_get_trades_by_id_returns_highest_version_first(conn):
    """All versions of one trade come back with the highest version first."""
    db.insert_trade(conn, make_trade(version=1))
    db.insert_trade(conn, make_trade(version=2))
    versions = [t["version"] for t in db.get_trades_by_id(conn, "T1")]
    assert versions == [2, 1]


# ---------- expiry ----------

def test_mark_expired_flags_only_trades_past_maturity(conn):
    """Only trades whose maturity date is before today get marked expired."""
    db.insert_trade(conn, make_trade(trade_id="OLD", maturity_date=date(2026, 11, 6)))
    db.insert_trade(conn, make_trade(trade_id="TODAY", maturity_date=TODAY))
    db.insert_trade(conn, make_trade(trade_id="FUTURE", maturity_date=date(2027, 1, 1)))

    changed = db.mark_expired_trades(conn, TODAY)

    assert changed == 1
    assert db.get_trades_by_id(conn, "OLD")[0]["expired"] is True
    assert db.get_trades_by_id(conn, "TODAY")[0]["expired"] is False
    assert db.get_trades_by_id(conn, "FUTURE")[0]["expired"] is False


def test_mark_expired_does_not_count_already_expired_trades(conn):
    """Running expiry twice only counts the newly expired trades the second time."""
    db.insert_trade(conn, make_trade(maturity_date=date(2026, 11, 6)))
    assert db.mark_expired_trades(conn, TODAY) == 1
    assert db.mark_expired_trades(conn, TODAY) == 0
