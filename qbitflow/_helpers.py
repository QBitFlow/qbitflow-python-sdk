"""Small integration helpers: exact amount conversions and the redirect placeholders."""

from __future__ import annotations

import re
from typing import Any

from .errors import field_error

__all__ = [
    "PLACEHOLDER_UUID",
    "PLACEHOLDER_TRANSACTION_TYPE",
    "format_amount",
    "parse_amount",
]

#: In a checkout's ``success_url``/``cancel_url``: replaced by the session's (or the
#: transaction's) uuid. The SDK sends it as is (never URL-encoded): the server substitutes it.
PLACEHOLDER_UUID = "{{UUID}}"
#: In a checkout's ``success_url``/``cancel_url``: replaced by the transaction type.
PLACEHOLDER_TRANSACTION_TYPE = "{{TRANSACTION_TYPE}}"

_MAX_DECIMALS = 77
_MIN_UNITS = re.compile(r"-?[0-9]+")
_AMOUNT = re.compile(r"(-?)([0-9]+)(?:\.([0-9]+))?")


def _check_decimals(decimals: Any) -> int:
    if isinstance(decimals, bool) or not isinstance(decimals, int):
        raise field_error("decimals", "must be an integer")
    if decimals < 0 or decimals > _MAX_DECIMALS:
        raise field_error("decimals", f"must be between 0 and {_MAX_DECIMALS}")
    return decimals


def format_amount(min_units: str, decimals: int) -> str:
    """An amount in a currency's minimal units as a decimal string, exactly (string arithmetic,
    no float): ``format_amount("1500000", 6) == "1.5"``. Leading zeros and the fraction's
    trailing zeros are trimmed; never an exponent.

    Args:
        min_units: The amount in minimal units (``-?[0-9]+``), as the API's ``*_min_units``
            fields carry it.
        decimals: The currency's decimals (0 to 77; ``currency.decimals``).

    Raises:
        ValidationError: ``min_units`` is not an integer string, or ``decimals`` is out of range.
    """
    if not isinstance(min_units, str) or _MIN_UNITS.fullmatch(min_units) is None:
        raise field_error("minUnits", "must be an integer string (-?[0-9]+)")
    places = _check_decimals(decimals)
    negative = min_units.startswith("-")
    digits = min_units.lstrip("-").lstrip("0") or "0"
    if places == 0:
        whole, fraction = digits, ""
    else:
        digits = digits.rjust(places + 1, "0")
        whole, fraction = digits[:-places], digits[-places:].rstrip("0")
    text = whole + ("." + fraction if fraction else "")
    return "-" + text if negative and text != "0" else text


def parse_amount(amount: str, decimals: int) -> str:
    """A decimal amount in a currency's minimal units, exactly (string arithmetic, no float):
    ``parse_amount("1.5", 6) == "1500000"``.

    Args:
        amount: ``-?[0-9]+(\\.[0-9]+)?`` (no exponent, no grouping, no sign ``+``).
        decimals: The currency's decimals (0 to 77).

    Raises:
        ValidationError: a malformed amount, more fractional digits than ``decimals``, or
            ``decimals`` out of range.
    """
    match = _AMOUNT.fullmatch(amount) if isinstance(amount, str) else None
    if match is None:
        raise field_error("amount", "must be a decimal number (-?[0-9]+(.[0-9]+)?)")
    places = _check_decimals(decimals)
    sign, whole, fraction = match.group(1), match.group(2), match.group(3) or ""
    if len(fraction) > places:
        raise field_error("amount", f"must have at most {places} decimal places")
    digits = (whole + fraction.ljust(places, "0")).lstrip("0") or "0"
    return sign + digits if digits != "0" else "0"
