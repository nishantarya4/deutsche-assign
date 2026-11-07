from datetime import date

import pytest

from app.rules import (
    LowerVersionError,
    MaturityDateInPastError,
    check_maturity_date,
    decide_action,
    is_expired,
)

TODAY = date(2026, 11, 7)


# ---------- check_maturity_date ----------

def test_maturity_date_in_past_is_rejected():
    """A maturity date before today must raise MaturityDateInPastError."""
    with pytest.raises(MaturityDateInPastError):
        check_maturity_date(date(2026, 11, 6), TODAY)


def test_maturity_date_today_is_accepted():
    """A maturity date equal to today is allowed (it is not earlier than today)."""
    check_maturity_date(TODAY, TODAY)


def test_maturity_date_in_future_is_accepted():
    """A maturity date after today is allowed."""
    check_maturity_date(date(2027, 5, 20), TODAY)


# ---------- decide_action ----------

def test_first_version_of_a_trade_is_inserted():
    """When nothing is stored for this trade id yet, the trade is inserted."""
    assert decide_action(new_version=1, highest_stored_version=None) == "insert"


def test_higher_version_is_inserted():
    """A version higher than the stored one is inserted as a new row."""
    assert decide_action(new_version=3, highest_stored_version=2) == "insert"


def test_same_version_replaces():
    """A version equal to the stored one replaces the existing record."""
    assert decide_action(new_version=2, highest_stored_version=2) == "replace"


def test_lower_version_is_rejected():
    """A version lower than the stored one must raise LowerVersionError."""
    with pytest.raises(LowerVersionError):
        decide_action(new_version=1, highest_stored_version=2)


# ---------- is_expired ----------

def test_trade_past_maturity_is_expired():
    """A trade whose maturity date is before today is expired."""
    assert is_expired(date(2026, 11, 6), TODAY) is True


def test_trade_maturing_today_is_not_expired():
    """A trade maturing today is not expired yet."""
    assert is_expired(TODAY, TODAY) is False


def test_trade_maturing_in_future_is_not_expired():
    """A trade maturing after today is not expired."""
    assert is_expired(date(2027, 5, 20), TODAY) is False
