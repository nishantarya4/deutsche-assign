from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app, get_conn, get_today

TODAY = date(2026, 11, 7)


@pytest.fixture
def conn(tmp_path):
    """Give each test its own fresh database file, and close it afterwards."""
    connection = db.connect(tmp_path / "test.db")
    yield connection
    connection.close()


@pytest.fixture
def client(conn):
    """Give each test an HTTP client that uses the test database and a fixed 'today'."""

    def use_test_conn():
        """Hand the endpoints the test database instead of the real one."""
        return conn

    def use_fixed_today():
        """Hand the endpoints a fixed date so tests never depend on the real clock."""
        return TODAY

    app.dependency_overrides[get_conn] = use_test_conn
    app.dependency_overrides[get_today] = use_fixed_today
    yield TestClient(app)
    app.dependency_overrides.clear()
