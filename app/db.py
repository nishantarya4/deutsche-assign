import sqlite3
from datetime import date

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS trades (
    trade_id        TEXT    NOT NULL,
    version         INTEGER NOT NULL,
    counterparty_id TEXT    NOT NULL,
    portfolio_id    TEXT    NOT NULL,
    maturity_date   TEXT    NOT NULL,
    created_date    TEXT    NOT NULL,
    expired         INTEGER NOT NULL,
    PRIMARY KEY (trade_id, version)
)
"""


def connect(path):
    """Open the database file at path and make sure the trades table exists."""
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute(CREATE_TABLE_SQL)
    conn.commit()
    return conn


def row_to_trade(row):
    """Turn one database row into a plain trade dict with real dates and a True/False expired flag."""
    return {
        "trade_id": row["trade_id"],
        "version": row["version"],
        "counterparty_id": row["counterparty_id"],
        "portfolio_id": row["portfolio_id"],
        "maturity_date": date.fromisoformat(row["maturity_date"]),
        "created_date": date.fromisoformat(row["created_date"]),
        "expired": bool(row["expired"]),
    }


def get_highest_version(conn, trade_id):
    """Return the highest stored version for this trade id, or None if there is none."""
    row = conn.execute(
        "SELECT MAX(version) AS highest FROM trades WHERE trade_id = ?",
        (trade_id,),
    ).fetchone()
    return row["highest"]


def insert_trade(conn, trade):
    """Save a brand-new trade row."""
    conn.execute(
        "INSERT INTO trades (trade_id, version, counterparty_id, portfolio_id,"
        " maturity_date, created_date, expired) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            trade["trade_id"],
            trade["version"],
            trade["counterparty_id"],
            trade["portfolio_id"],
            trade["maturity_date"].isoformat(),
            trade["created_date"].isoformat(),
            int(trade["expired"]),
        ),
    )
    conn.commit()


def replace_trade(conn, trade):
    """Overwrite the stored trade that has the same trade id and version."""
    conn.execute(
        "UPDATE trades SET counterparty_id = ?, portfolio_id = ?, maturity_date = ?,"
        " created_date = ?, expired = ? WHERE trade_id = ? AND version = ?",
        (
            trade["counterparty_id"],
            trade["portfolio_id"],
            trade["maturity_date"].isoformat(),
            trade["created_date"].isoformat(),
            int(trade["expired"]),
            trade["trade_id"],
            trade["version"],
        ),
    )
    conn.commit()


def list_trades(conn):
    """Return every trade, ordered by trade id and then highest version first."""
    rows = conn.execute(
        "SELECT * FROM trades ORDER BY trade_id ASC, version DESC"
    ).fetchall()
    trades = []
    for row in rows:
        trades.append(row_to_trade(row))
    return trades


def get_trades_by_id(conn, trade_id):
    """Return all versions of one trade, highest version first (empty list if none)."""
    rows = conn.execute(
        "SELECT * FROM trades WHERE trade_id = ? ORDER BY version DESC",
        (trade_id,),
    ).fetchall()
    trades = []
    for row in rows:
        trades.append(row_to_trade(row))
    return trades


def mark_expired_trades(conn, today):
    """Mark every not-yet-expired trade whose maturity date is before today, and return how many changed."""
    cursor = conn.execute(
        "UPDATE trades SET expired = 1 WHERE expired = 0 AND maturity_date < ?",
        (today.isoformat(),),
    )
    conn.commit()
    return cursor.rowcount
