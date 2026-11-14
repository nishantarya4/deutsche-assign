import asyncio
from contextlib import asynccontextmanager
from datetime import date

from fastapi import Depends, FastAPI, HTTPException, Response
from pydantic import BaseModel

from app import db, rules, scheduler

DATABASE_PATH = "trades.db"


class TradeIn(BaseModel):
    """The fields a client sends when submitting a trade."""

    trade_id: str
    version: int
    counterparty_id: str
    portfolio_id: str
    maturity_date: date


def get_today():
    """Return today's date (tests replace this with a fixed date)."""
    return date.today()


def get_conn():
    """Open a database connection for one request and close it afterwards."""
    conn = db.connect(DATABASE_PATH)
    try:
        yield conn
    finally:
        conn.close()


@asynccontextmanager
async def lifespan(app):
    """On startup expire matured trades and start the daily expiry job; stop the job on shutdown."""
    scheduler.run_expiry_job(DATABASE_PATH, get_today())
    daily_job = asyncio.create_task(scheduler.run_daily_expiry(DATABASE_PATH, get_today))
    yield
    daily_job.cancel()


app = FastAPI(title="Trade Store", lifespan=lifespan)


@app.get("/health")
def health():
    """Tell the caller the service is up and running."""
    return {"status": "ok"}


@app.post("/trades", status_code=201)
def add_trade(trade_in: TradeIn, response: Response,
              conn=Depends(get_conn), today=Depends(get_today)):
    """Validate an incoming trade, then store it as new or replace the same version."""
    try:
        rules.check_maturity_date(trade_in.maturity_date, today)
    except rules.MaturityDateInPastError as error:
        raise HTTPException(status_code=400, detail=str(error))

    highest_version = db.get_highest_version(conn, trade_in.trade_id)
    try:
        action = rules.decide_action(trade_in.version, highest_version)
    except rules.LowerVersionError as error:
        raise HTTPException(status_code=409, detail=f"Trade {trade_in.trade_id}: {error}")

    trade = {
        "trade_id": trade_in.trade_id,
        "version": trade_in.version,
        "counterparty_id": trade_in.counterparty_id,
        "portfolio_id": trade_in.portfolio_id,
        "maturity_date": trade_in.maturity_date,
        "created_date": today,
        "expired": rules.is_expired(trade_in.maturity_date, today),
    }

    if action == "replace":
        db.replace_trade(conn, trade)
        response.status_code = 200
    else:
        db.insert_trade(conn, trade)

    return trade


@app.get("/trades")
def list_trades(conn=Depends(get_conn), today=Depends(get_today)):
    """Mark matured trades as expired, then return every trade ordered by id and highest version first."""
    db.mark_expired_trades(conn, today)
    return db.list_trades(conn)


@app.get("/trades/{trade_id}")
def get_trade(trade_id: str, conn=Depends(get_conn), today=Depends(get_today)):
    """Mark matured trades as expired, then return all versions of one trade, or 404 if it does not exist."""
    db.mark_expired_trades(conn, today)
    trades = db.get_trades_by_id(conn, trade_id)
    if not trades:
        raise HTTPException(status_code=404, detail=f"Trade {trade_id} not found")
    return trades
