from app import db

# The `client` and `conn` fixtures live in conftest.py.
# In these tests "today" is always 2026-11-07.


def trade_body(trade_id="T1", version=1, counterparty_id="CP-1",
               portfolio_id="B1", maturity_date="2027-05-20"):
    """Build a JSON request body for POST /trades with sensible defaults."""
    return {
        "trade_id": trade_id,
        "version": version,
        "counterparty_id": counterparty_id,
        "portfolio_id": portfolio_id,
        "maturity_date": maturity_date,
    }


# ---------- GET /health ----------

def test_health_returns_ok(client):
    """Check that GET /health answers 200 with status ok."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ---------- POST /trades: accepted ----------

def test_new_trade_is_created(client):
    """A brand-new trade is stored and returned with 201, today's created date and expired false."""
    response = client.post("/trades", json=trade_body())
    assert response.status_code == 201
    assert response.json() == {
        "trade_id": "T1",
        "version": 1,
        "counterparty_id": "CP-1",
        "portfolio_id": "B1",
        "maturity_date": "2027-05-20",
        "created_date": "2026-11-07",
        "expired": False,
    }


def test_maturity_date_today_is_accepted(client):
    """A trade maturing today is not earlier than today, so it is accepted."""
    response = client.post("/trades", json=trade_body(maturity_date="2026-11-07"))
    assert response.status_code == 201


def test_same_version_replaces_existing_trade(client, conn):
    """Sending the same trade id and version again replaces the record and answers 200."""
    client.post("/trades", json=trade_body(counterparty_id="CP-1"))
    response = client.post("/trades", json=trade_body(counterparty_id="CP-9"))
    assert response.status_code == 200
    stored = db.get_trades_by_id(conn, "T1")
    assert len(stored) == 1
    assert stored[0]["counterparty_id"] == "CP-9"


def test_higher_version_is_added_alongside_old_one(client, conn):
    """A higher version is stored as a new row and the old version is kept."""
    client.post("/trades", json=trade_body(version=1))
    response = client.post("/trades", json=trade_body(version=2))
    assert response.status_code == 201
    versions = [t["version"] for t in db.get_trades_by_id(conn, "T1")]
    assert versions == [2, 1]


# ---------- POST /trades: rejected ----------

def test_lower_version_is_rejected(client, conn):
    """A lower version than the stored one is rejected with 409 and nothing changes."""
    client.post("/trades", json=trade_body(version=2, counterparty_id="CP-2"))
    response = client.post("/trades", json=trade_body(version=1, counterparty_id="CP-1"))
    assert response.status_code == 409
    assert response.json() == {
        "detail": "Trade T1: Version 1 is lower than stored version 2"
    }
    stored = db.get_trades_by_id(conn, "T1")
    assert len(stored) == 1
    assert stored[0]["version"] == 2


def test_maturity_date_in_past_is_rejected(client, conn):
    """A trade maturing before today is rejected with 400 and not stored."""
    response = client.post("/trades", json=trade_body(maturity_date="2026-11-06"))
    assert response.status_code == 400
    assert response.json() == {
        "detail": "Maturity date 2026-11-06 is earlier than today 2026-11-07"
    }
    assert db.get_trades_by_id(conn, "T1") == []


def test_missing_field_is_rejected(client):
    """A body without a required field is rejected with 422."""
    body = trade_body()
    del body["portfolio_id"]
    response = client.post("/trades", json=body)
    assert response.status_code == 422


def test_badly_formatted_date_is_rejected(client):
    """A maturity date that is not a real ISO date is rejected with 422."""
    response = client.post("/trades", json=trade_body(maturity_date="20/05/2027"))
    assert response.status_code == 422


# ---------- GET /trades ----------

def test_list_trades_is_empty_when_nothing_stored(client):
    """With no trades stored, GET /trades returns an empty list."""
    response = client.get("/trades")
    assert response.status_code == 200
    assert response.json() == []


def test_list_trades_returns_problem_statement_rows_in_order(client):
    """The four trades from the problem statement come back sorted by id, then highest version first."""
    # Same ids, versions, counterparties and portfolios as the problem statement.
    # Maturity dates are moved into the future, because past dates are now rejected.
    client.post("/trades", json=trade_body("T3", 3, "CP-3", "B2", "2028-05-20"))
    client.post("/trades", json=trade_body("T2", 1, "CP-1", "B1", "2027-05-20"))
    client.post("/trades", json=trade_body("T1", 1, "CP-1", "B1", "2027-05-20"))
    client.post("/trades", json=trade_body("T2", 2, "CP-2", "B1", "2027-05-20"))

    response = client.get("/trades")

    assert response.status_code == 200
    rows = []
    for trade in response.json():
        rows.append((trade["trade_id"], trade["version"], trade["counterparty_id"], trade["portfolio_id"]))
    assert rows == [
        ("T1", 1, "CP-1", "B1"),
        ("T2", 2, "CP-2", "B1"),
        ("T2", 1, "CP-1", "B1"),
        ("T3", 3, "CP-3", "B2"),
    ]


# ---------- GET /trades/{trade_id} ----------

def test_get_one_trade_returns_all_versions_highest_first(client):
    """GET /trades/T2 returns both versions of T2, highest version first."""
    client.post("/trades", json=trade_body("T2", 1, "CP-1"))
    client.post("/trades", json=trade_body("T2", 2, "CP-2"))
    client.post("/trades", json=trade_body("T1", 1, "CP-1"))

    response = client.get("/trades/T2")

    assert response.status_code == 200
    versions = [t["version"] for t in response.json()]
    assert versions == [2, 1]


def test_get_unknown_trade_returns_404(client):
    """Asking for a trade id that was never stored answers 404."""
    response = client.get("/trades/NOPE")
    assert response.status_code == 404
    assert response.json() == {"detail": "Trade NOPE not found"}
