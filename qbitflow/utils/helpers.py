"""
Helper functions for the QBitFlow SDK.

This module contains utility functions for string manipulation, data conversion and the
client-side validation rules that mirror the API's ``binding`` tags. Every QBitFlow SDK
implements the same rule set, so a value rejected here is a value the API would reject
with a 400 — and one the other SDKs reject too.
"""

import math
import re
import unicodedata
from datetime import date
from typing import Any, Literal, Optional, Tuple
from urllib.parse import urlsplit


def camel_to_snake_case(camel_str: str) -> str:
    """
    Convert a camel case string to snake case.

    Args:
        camel_str: String in camelCase format.

    Returns:
        String in snake_case format.

    Examples:
        >>> camel_to_snake_case("customerUUID")
        'customer_uuid'
        >>> camel_to_snake_case("productName")
        'product_name'
    """
    # Insert an underscore before any uppercase letter that follows a lowercase letter
    snake_str = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", camel_str)
    # Insert an underscore before any uppercase letter that follows a lowercase or uppercase letter
    snake_str = re.sub("([a-z0-9])([A-Z])", r"\1_\2", snake_str)
    return snake_str.lower()


def snake_to_camel_case(snake_str: str) -> str:
    """
    Convert a snake case string to camel case.

    Args:
        snake_str: String in snake_case format.

    Returns:
        String in camelCase format.

    Examples:
        >>> snake_to_camel_case("customer_uuid")
        'customerUUID'
        >>> snake_to_camel_case("product_name")
        'productName'
    """
    components = snake_str.split("_")
    # Capitalize the first letter of each component except the first one
    result = components[0] + "".join(x.title() for x in components[1:])

    # Special handling: convert 'Uuid' at the end to 'UUID'
    result = re.sub(r"Uuid$", "UUID", result)
    return result


def convert_dict_keys_to_snake_case(data: Any) -> Any:
    """
    Recursively convert all dictionary keys from camel case to snake case.

    This function traverses nested dictionaries and lists, converting all
    dictionary keys to snake_case format.

    Args:
        data: Dictionary, list, or other data structure to convert.

    Returns:
        Data structure with all dictionary keys converted to snake case.

    Examples:
        >>> data = {"customerUUID": "123", "productName": "Test"}
        >>> convert_dict_keys_to_snake_case(data)
        {'customer_uuid': '123', 'product_name': 'Test'}
    """
    if isinstance(data, dict):
        return {
            camel_to_snake_case(key): convert_dict_keys_to_snake_case(value)
            for key, value in data.items()
        }
    elif isinstance(data, list):
        return [convert_dict_keys_to_snake_case(item) for item in data]
    else:
        return data


_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE
)

#: Largest value of a Go ``uint32`` (subscription frequency, trial period, minimum periods).
MAX_UINT32 = 4294967295


def validate_uuid(uuid: Any) -> bool:
    """
    Validate that a string is a bare UUID (``8-4-4-4-12`` hex digits, any case).

    Prefixed identifiers such as ``pay@<uuid>`` are *not* bare UUIDs.

    Args:
        uuid: String to validate.

    Returns:
        True if the string is a valid UUID, False otherwise.

    Examples:
        >>> validate_uuid("01997c89-d0e9-7c9a-9886-fe7709919695")
        True
        >>> validate_uuid("invalid-uuid")
        False
    """
    return isinstance(uuid, str) and _UUID_RE.fullmatch(uuid) is not None


#: An http(s) scheme followed by a non-empty authority, as written (no leading whitespace).
_ABSOLUTE_HTTP_URL = re.compile(r"^https?://[^/?#\\\s]", re.IGNORECASE)


def validate_url(url: Any) -> bool:
    """
    Validate that a string is an absolute http(s) URL.

    Mirrors the API's ``http_url`` binding rule: an absolute URL whose scheme is ``http`` or
    ``https`` (in any case) and whose host is not empty. The TLD is deliberately not
    constrained, so ``https://shop.example.technology/ok`` and internal hosts like
    ``https://checkout-web/success`` are accepted, as the API accepts them.

    Examples:
        >>> validate_url("https://example.com/webhook")
        True
        >>> validate_url("HTTPS://checkout-web/success")
        True
        >>> validate_url("not a url")
        False
        >>> validate_url("javascript:alert(1)")
        False
    """
    if not isinstance(url, str):
        return False
    # ``urlsplit`` silently strips leading whitespace and tolerates spaces in the host, both of
    # which the API (Go's ``url.Parse``) rejects, so the scheme and authority are checked on the
    # text exactly as written.
    if not _ABSOLUTE_HTTP_URL.match(url):
        return False
    try:
        parts = urlsplit(url)
        host = parts.hostname
    except ValueError:
        return False

    if not host or any(char.isspace() or ord(char) < 0x20 or ord(char) == 0x7F for char in host):
        return False
    return parts.scheme in ("http", "https")


def is_valid_email(value: Any) -> bool:
    """
    The SDK's single email rule, used by every DTO and every email lookup.

    It is structural, like the API's ``email`` binding: exactly one ``@``, a non-empty local
    part, a domain that contains a ``.`` and does not start or end with one, and no whitespace
    anywhere. The address is never normalised — the API stores it with its case preserved.

    Args:
        value: The address to check.

    Returns:
        ``True`` when the address is acceptable.

    Examples:
        >>> is_valid_email("john@example.com")
        True
        >>> is_valid_email("john@localhost")
        False
        >>> is_valid_email("not an email")
        False
    """
    if not isinstance(value, str) or not value or value.count("@") != 1:
        return False
    if any(char.isspace() for char in value):
        return False

    local, domain = value.split("@")
    if not local or not domain:
        return False

    return "." in domain and not domain.startswith(".") and not domain.endswith(".")


#: Characters the API's ``alphanumspace`` rule allows besides letters, digits and spaces.
ALPHANUMSPACE_EXTRA = "-_'."


def validate_alphanumspace(value: Any, min_length: int, max_length: int) -> Optional[str]:
    """
    Mirror the API's ``alphanumspace`` binding rule (names of customers and users).

    Accepts a non-empty string whose every character is a Unicode letter (category ``L*``), a
    Unicode *decimal* digit (category ``Nd`` — so ``²``, ``①`` and ``Ⅻ`` are rejected, as the
    server rejects them), a space, or one of ``-`` ``_`` ``'`` ``.``. A whitespace-only value
    is accepted, as the server accepts it. Length is counted in code points, as the server
    counts runes.

    Args:
        value: The text to check.
        min_length: Minimum length, in characters.
        max_length: Maximum length, in characters.

    Returns:
        ``None`` when the value is acceptable, otherwise a message describing the problem.

    Examples:
        >>> validate_alphanumspace("Jean-Luc O'Neil", 2, 100) is None
        True
        >>> validate_alphanumspace("John & Co", 2, 100)
        "must not contain the character '&'"
    """
    if not isinstance(value, str):
        return "must be a string"
    if not value:
        return "must not be empty"

    if len(value) < min_length or len(value) > max_length:
        return f"must be between {min_length} and {max_length} characters"

    for char in value:
        if char.isalpha() or char.isdecimal() or char == " " or char in ALPHANUMSPACE_EXTRA:
            continue
        return f"must not contain the character {char!r}"

    return None


#: Characters the API's ``producttext`` rule rejects (common XSS / injection payloads).
PRODUCT_TEXT_DISALLOWED = '<>{}[]`\\|;"~^'


def _is_forbidden_control(char: str) -> bool:
    """C0 (U+0000–U+001F) and C1 (U+007F–U+009F) control characters, minus \\n \\r \\t."""
    if char in "\n\r\t":
        return False
    code = ord(char)
    return code < 0x20 or 0x7F <= code <= 0x9F or unicodedata.category(char) == "Cc"


def validate_product_text(value: Any, min_length: int, max_length: int) -> Optional[str]:
    """
    Mirror the API's ``producttext`` binding rule.

    Accepts letters (including accented and non-Latin), digits, spaces and ordinary
    punctuation; rejects a value that is blank after trimming Unicode whitespace, angle
    brackets and other markup characters, and control characters other than newline, carriage
    return and tab. Text that merely looks script-like (for example the literal
    ``javascript:alert(1)``) is allowed - the server renders these fields as escaped text.
    Length is counted in code points, as the server counts runes.

    Args:
        value: The text to check.
        min_length: Minimum length, in characters.
        max_length: Maximum length, in characters.

    Returns:
        ``None`` when the value is acceptable, otherwise a message describing the problem.

    Examples:
        >>> validate_product_text("Premium Plan", 2, 100) is None
        True
        >>> validate_product_text("<script>", 2, 100) is None
        False
    """
    if not isinstance(value, str):
        return "must be a string"
    if not value or not value.strip():
        return "must not be blank"

    if len(value) < min_length or len(value) > max_length:
        return f"must be between {min_length} and {max_length} characters"

    for char in value:
        if char in PRODUCT_TEXT_DISALLOWED:
            return f"must not contain the character {char!r}"
        if _is_forbidden_control(char):
            return "must not contain control characters"

    return None


def validate_integer(value: Any, minimum: int, maximum: int) -> Optional[str]:
    """
    Check that ``value`` is an integer (not a boolean) within ``[minimum, maximum]``.

    Returns:
        ``None`` when the value is acceptable, otherwise a message describing the problem.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        return "must be an integer"
    if value < minimum or value > maximum:
        return f"must be between {minimum} and {maximum}"
    return None


def validate_price(value: Any) -> Optional[str]:
    """
    Check that ``value`` is a finite number strictly greater than zero (the API rejects 0).

    Returns:
        ``None`` when the value is acceptable, otherwise a message describing the problem.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "must be a number"
    if not math.isfinite(value):
        return "must be a finite number"
    if value <= 0:
        return "must be greater than 0"
    return None


_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}", re.ASCII)

ExportFormat = Literal["json", "csv"]


def _parse_export_date(value: Any, name: str) -> Tuple[Optional[date], Optional[str]]:
    """Parse a ``YYYY-MM-DD`` export bound, returning ``(date, None)`` or ``(None, problem)``."""
    if not isinstance(value, str) or not value:
        return None, f"{name} cannot be empty"
    if not _DATE_RE.fullmatch(value):
        return None, f"{name} must be in YYYY-MM-DD format"
    try:
        return date.fromisoformat(value), None
    except ValueError:
        return None, f"{name} is not a valid calendar date"


def validate_export_request(from_date: Any, to_date: Any, export_format: Any) -> Optional[str]:
    """
    Mirror the validation of ``GET /accounting/export``.

    Both bounds must be real ``YYYY-MM-DD`` calendar dates, ``from_date`` must not be after
    ``to_date``, and the format must be ``json`` or ``csv``. The length of the window is left
    to the server, which decides what span it accepts.

    Returns:
        ``None`` when the request is acceptable, otherwise a message describing the problem.

    Examples:
        >>> validate_export_request("2026-01-01", "2026-03-31", "json") is None
        True
        >>> validate_export_request("2026-03-01", "2026-02-01", "csv")
        'from_date must not be after to_date'
    """
    start, problem = _parse_export_date(from_date, "from_date")
    if problem or start is None:
        return problem

    end, problem = _parse_export_date(to_date, "to_date")
    if problem or end is None:
        return problem

    if start > end:
        return "from_date must not be after to_date"

    if export_format not in ("json", "csv"):
        return "format must be 'json' or 'csv'"

    return None


#: Former name of :func:`validate_export_request`, kept for compatibility.
validate_export_window = validate_export_request
