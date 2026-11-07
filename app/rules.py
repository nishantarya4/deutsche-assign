class MaturityDateInPastError(Exception):
    """Raised when a trade's maturity date is earlier than today."""


class LowerVersionError(Exception):
    """Raised when a trade arrives with a lower version than the one already stored."""


def check_maturity_date(maturity_date, today):
    """Raise MaturityDateInPastError if the maturity date is before today."""
    if maturity_date < today:
        raise MaturityDateInPastError(
            f"Maturity date {maturity_date} is earlier than today {today}"
        )


def decide_action(new_version, highest_stored_version):
    """Return 'insert' or 'replace' for an incoming version, or raise LowerVersionError."""
    if highest_stored_version is None:
        return "insert"
    if new_version < highest_stored_version:
        raise LowerVersionError(
            f"Version {new_version} is lower than stored version {highest_stored_version}"
        )
    if new_version == highest_stored_version:
        return "replace"
    return "insert"


def is_expired(maturity_date, today):
    """Return True if the maturity date is before today, otherwise False."""
    return maturity_date < today
