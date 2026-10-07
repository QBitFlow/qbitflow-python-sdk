"""
The SDK's one set of client-side checks (the API's binding rules, docs ``validators.md``).

They run before any request, so a bad input fails without a round trip, with a
:class:`~qbitflow.ValidationError` naming each failing input by its wire name. Lengths count
Unicode code points. Rules that depend on the key's mode or on server state (the test-mode price
cap, https-only URLs in live mode, the frequency minimum, the 95-day export window, uniqueness)
are left to the API.
"""

from __future__ import annotations

import math
import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional, Sequence
from urllib.parse import urlsplit

from .errors import FieldError, ValidationError, field_error, validation_error
from .models.common import Duration
from .models.enums import DurationUnit, EventType

MAX_UINT32 = 4294967295

#: The characters names and free text refuse.
_TEXT_DISALLOWED = frozenset('<>{}[]`\\|;"~^')

#: Go's ``unicode.IsSpace`` (what ``strings.TrimSpace`` trims).
_GO_SPACES = "\t\n\v\f\r \x85\xa0           " "     　"

_REFERENCE = re.compile(r"[A-Za-z0-9._:@-]+")
_PHONE = re.compile(r"\+?[0-9][0-9 ().-]{4,}[0-9]")
_UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_REQUEST_ID = re.compile(r"[A-Za-z0-9\-_.:]{1,128}")
_NIL_UUID = "00000000-0000-0000-0000-000000000000"
_TX_PREFIXES = ("pay", "sub", "payg", "sub-hist", "refund", "transfer")

#: Each DurationUnit's length in seconds (months = 30 days, years = 365 days).
_UNIT_SECONDS: Dict[str, int] = {
    DurationUnit.SECONDS: 1,
    DurationUnit.MINUTES: 60,
    DurationUnit.HOURS: 3600,
    DurationUnit.DAYS: 86400,
    DurationUnit.WEEKS: 7 * 86400,
    DurationUnit.MONTHS: 30 * 86400,
    DurationUnit.YEARS: 365 * 86400,
}
_YEAR_SECONDS = 365 * 86400


def trim_space(value: str) -> str:
    """``strings.TrimSpace``: strip Unicode white space."""
    return value.strip(_GO_SPACES)


def is_uuid(value: Any) -> bool:
    """Whether ``value`` is a UUID in its 8-4-4-4-12 hex form (any case)."""
    return isinstance(value, str) and _UUID.fullmatch(value) is not None


def is_tx_id(value: Any) -> bool:
    """Whether ``value`` is a transaction id: ``<pay|sub|payg|sub-hist|refund|transfer>@<uuid>``,
    or a bare UUID."""
    if not isinstance(value, str):
        return False
    prefix, sep, rest = value.partition("@")
    if not sep:
        return is_uuid(value)
    return prefix in _TX_PREFIXES and is_uuid(rest)


def is_text(value: str, multiline: bool) -> bool:
    """The API's text rule: not blank, no control character (line breaks and tabs only when
    multiline), none of ``< > { } [ ] ` \\ | ; " ~ ^``."""
    if trim_space(value) == "":
        return False
    for char in value:
        if multiline and char in "\n\r\t":
            continue
        if unicodedata.category(char) == "Cc" or char in _TEXT_DISALLOWED:
            return False
    return True


def is_name(value: str) -> bool:
    """The API's name rule: the text rule on one line, without bidirectional controls."""
    if not is_text(value, False):
        return False
    return not any(0x202A <= ord(c) <= 0x202E or 0x2066 <= ord(c) <= 0x2069 for c in value)


def is_email(value: str) -> bool:
    """The structural email check: one ``@``, a non-empty local part, a dotted domain that
    neither starts nor ends with a dot, no white space. Never normalised."""
    if value.count("@") != 1 or any(c in _GO_SPACES for c in value):
        return False
    local, _, domain = value.partition("@")
    return bool(local) and "." in domain and not domain.startswith(".") and not domain.endswith(".")


def is_http_url(value: str) -> bool:
    """Whether ``value`` is an absolute http(s) URL with a host."""
    if any(unicodedata.category(c) == "Cc" or c == " " for c in value):
        return False
    try:
        parts = urlsplit(value)
    except ValueError:
        return False
    host = parts.netloc.rpartition("@")[2]
    return parts.scheme.lower() in ("http", "https") and host != ""


def is_idempotency_key(key: Any) -> bool:
    """1 to 255 printable ASCII characters without spaces (0x21-0x7E)."""
    return (
        isinstance(key, str) and 1 <= len(key) <= 255 and all(0x21 <= ord(c) <= 0x7E for c in key)
    )


def is_request_id(value: Any) -> bool:
    """1 to 128 of ``A-Z a-z 0-9 - _ . :``."""
    return isinstance(value, str) and _REQUEST_ID.fullmatch(value) is not None


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def has_at_most_two_decimals(value: float) -> bool:
    """Whether the shortest decimal form of ``value`` has at most 2 decimals."""
    text = format(Decimal(repr(float(value))), "f")
    _, _, fraction = text.partition(".")
    return len(fraction.rstrip("0")) <= 2 if fraction else True


class Validator:
    """Collects the field errors of one call's inputs."""

    def __init__(self) -> None:
        self.fields: List[FieldError] = []

    def add(self, field: str, message: str) -> None:
        """Record a failing input; the message starts with the field's name."""
        self.fields.append(FieldError(field, f"{field} {message}"))

    def error(self) -> Optional[ValidationError]:
        """The collected failures, or ``None``."""
        if not self.fields:
            return None
        return validation_error("validation failed", self.fields)

    def check(self) -> None:
        """Raise the collected failures, if any."""
        error = self.error()
        if error is not None:
            raise error

    # ── Types ──

    def string(self, field: str, value: Any) -> bool:
        """Whether ``value`` is a non-empty ``str``; a non-``str`` (other than ``None``) fails."""
        if value is None:
            return False
        if not isinstance(value, str):
            self.add(field, "must be a string")
            return False
        return value != ""

    def boolean(self, field: str, value: Any) -> None:
        """A flag: ``None`` or a ``bool``."""
        if value is not None and not isinstance(value, bool):
            self.add(field, "must be a boolean")

    def integer(self, field: str, value: Any) -> None:
        """A page size or count: ``None`` or an ``int`` (sent as given)."""
        if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
            self.add(field, "must be an integer")

    def timestamp(self, field: str, value: Any) -> None:
        """A time filter: ``None`` or a timezone-aware ``datetime``."""
        if value is None:
            return
        if not isinstance(value, datetime) or value.tzinfo is None:
            self.add(field, "must be a timezone-aware datetime")
        elif value.utcoffset() is None:
            self.add(field, "must be a timezone-aware datetime")

    # ── Rules ──

    def required(self, field: str, value: Any) -> bool:
        """A required string is set (not blank). Reports whether it is."""
        if value is None or (isinstance(value, str) and trim_space(value) == ""):
            self.add(field, "is required")
            return False
        if not isinstance(value, str):
            self.add(field, "must be a string")
            return False
        return True

    def length(self, field: str, value: str, min_len: int, max_len: int) -> bool:
        """A code-point length (``max_len`` 0 = no maximum). Reports whether it passed."""
        n = len(value)
        if max_len > 0 and min_len > 0 and (n < min_len or n > max_len):
            self.add(field, f"must be {min_len} to {max_len} characters")
        elif min_len > 0 and n < min_len:
            self.add(field, f"must be at least {min_len} characters")
        elif max_len > 0 and n > max_len:
            self.add(field, f"must be at most {max_len} characters")
        else:
            return True
        return False

    def name(self, field: str, value: Any, min_len: int, max_len: int) -> None:
        """A name (product, customer) when set: the name rule and its length."""
        if not self.string(field, value) or not self.length(field, value, min_len, max_len):
            return
        if not is_name(value):
            self.add(field, 'must be one line, not blank, without < > { } [ ] ` \\ | ; " ~ ^')

    def text(self, field: str, value: Any, min_len: int, max_len: int) -> None:
        """Free text (descriptions, addresses, messages) when set: the text rule and length."""
        if not self.string(field, value) or not self.length(field, value, min_len, max_len):
            return
        if not is_text(value, True):
            self.add(
                field,
                'must not be blank nor contain control characters or < > { } [ ] ` \\ | ; " ~ ^',
            )

    def reference(self, field: str, value: Any) -> None:
        """A merchant reference when set: 1 to 100 of ``A-Z a-z 0-9 . _ : @ -``."""
        if not self.string(field, value) or not self.length(field, value, 1, 100):
            return
        if _REFERENCE.fullmatch(value) is None:
            self.add(field, "must contain only letters, digits and . _ : @ -")

    def phone(self, field: str, value: Any) -> None:
        """A phone number when set: at most 32 characters, an optional +, digits and the
        separators space . - ( ), starting and ending with a digit."""
        if not self.string(field, value) or not self.length(field, value, 0, 32):
            return
        if _PHONE.fullmatch(value) is None:
            self.add(field, "must be a valid phone number")

    def email(self, field: str, value: Any) -> None:
        """An email address when set: at most 254 characters, structurally valid."""
        if not self.string(field, value) or not self.length(field, value, 0, 254):
            return
        if not is_email(value):
            self.add(field, "must be a valid email address")

    def url(self, field: str, value: Any) -> None:
        """A URL when set: at most 2048 characters, absolute http or https with a host."""
        if not self.string(field, value) or not self.length(field, value, 0, 2048):
            return
        if not is_http_url(value):
            self.add(field, "must be an absolute http or https URL")

    def price(self, field: str, value: Any) -> None:
        """A price in USD: a finite number above 0."""
        if not _is_number(value) or not math.isfinite(value) or value <= 0:
            self.add(field, "must be a number above 0")

    def percent(self, field: str, value: Any, max_percent: float, positive: bool) -> None:
        """A rate in percent: finite, from 0 (above 0 when ``positive``) to ``max_percent``, with
        at most 2 decimals."""
        low = "above 0" if positive else "0"
        if (
            not _is_number(value)
            or not math.isfinite(value)
            or value < 0
            or (positive and value == 0)
            or value > max_percent
            or not has_at_most_two_decimals(value)
        ):
            high = format(Decimal(repr(float(max_percent))).normalize(), "f")
            self.add(field, f"must be a percentage from {low} to {high}, with at most 2 decimals")

    def duration(self, field: str, value: Any, frequency: bool) -> None:
        """A Duration: a unit (one of the 7) is required when value > 0, and a unit given with 0
        must be one of them too. A frequency is at least 1 unit and at most 1 year."""
        if not isinstance(value, Duration):
            self.add(field, "must be a Duration")
            return
        if value.value > MAX_UINT32:
            self.add(f"{field}.value", f"must be from 0 to {MAX_UINT32}")
            return
        unit = value.unit
        seconds = _UNIT_SECONDS.get(unit) if isinstance(unit, str) else None
        if value.value > 0 and not unit:
            self.add(f"{field}.unit", "is required when value is above 0")
            return
        if unit and seconds is None:
            self.add(
                f"{field}.unit",
                "must be one of seconds, minutes, hours, days, weeks, months, years",
            )
            return
        if not frequency:
            return
        if value.value < 1:
            self.add(f"{field}.value", "must be at least 1")
        elif seconds is not None and value.value * seconds > _YEAR_SECONDS:
            self.add(field, "must be at most 1 year")

    def int_range(self, field: str, value: Any, min_value: int, max_value: int) -> None:
        """An integer bound."""
        if isinstance(value, bool) or not isinstance(value, int):
            self.add(field, "must be an integer")
        elif value < min_value or value > max_value:
            self.add(field, f"must be from {min_value} to {max_value}")

    def uuid(self, field: str, value: Any) -> None:
        """A UUID when set."""
        if self.string(field, value) and not is_uuid(value):
            self.add(field, "must be a UUID")

    def tx_id(self, field: str, value: Any) -> None:
        """A transaction id (``pay@…``, ``sub@…``, ``sub-hist@…``, ``refund@…``, or a UUID) when
        set."""
        if self.string(field, value) and not is_tx_id(value):
            self.add(field, "must be a transaction id (pay@…, sub@…, sub-hist@… or a UUID)")

    def date(self, field: str, value: Any) -> Optional[date]:
        """A ``YYYY-MM-DD`` calendar date (a ``datetime.date`` is accepted too)."""
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if not self.required(field, value):
            return None
        if _DATE.fullmatch(value) is None:
            self.add(field, "must be a date (YYYY-MM-DD)")
            return None
        try:
            return date.fromisoformat(value)
        except ValueError:
            self.add(field, "must be a date (YYYY-MM-DD)")
            return None

    def date_range(self, from_field: str, from_value: Any, to_field: str, to_value: Any) -> None:
        """An export window: two ``YYYY-MM-DD`` dates, from <= to (the API enforces the
        window's maximum)."""
        start = self.date(from_field, from_value)
        end = self.date(to_field, to_value)
        if start is not None and end is not None and start > end:
            self.add(to_field, f"must not be before {from_field}")

    def exclusive(self, field_a: str, a: bool, field_b: str, b: bool) -> None:
        """Two filters that cannot both be set."""
        if a and b:
            self.add(field_b, f"cannot be combined with {field_a}")

    def one_of(self, field: str, value: Any, allowed: Sequence[str]) -> None:
        """An enum value when set."""
        if not self.string(field, value):
            return
        if value not in allowed:
            self.add(field, "must be one of " + ", ".join(str(a) for a in allowed))

    def endpoint_events(self, field: str, events: Any) -> None:
        """A webhook endpoint's event list: at most 20, never ``webhook.test``."""
        if events is None:
            return
        if isinstance(events, str) or not isinstance(events, (list, tuple)):
            self.add(field, "must be a list of event types")
            return
        if len(events) > 20:
            self.add(field, "must list at most 20 event types")
        for i, event in enumerate(events):
            if not isinstance(event, str):
                self.add(f"{field}[{i}]", "must be a string")
            elif event == "":
                self.add(f"{field}[{i}]", "is required")
            elif event == EventType.WEBHOOK_TEST:
                self.add(f"{field}[{i}]", "cannot be webhook.test (sent by the endpoint test only)")

    def list_filters(
        self,
        customer_uuid: Any,
        product_uuid: Any,
        created_after: Any,
        created_before: Any,
        include_members: Any,
        user_uuid: Any,
    ) -> None:
        """The filters every transaction list shares."""
        self.uuid("customerUuid", customer_uuid)
        self.uuid("productUuid", product_uuid)
        self.timestamp("createdAfter", created_after)
        self.timestamp("createdBefore", created_before)
        self.boolean("includeMembers", include_members)
        self.uuid("userUuid", user_uuid)
        self.exclusive("includeMembers", include_members is True, "userUuid", bool(user_uuid))

    def page(self, limit: Any, cursor: Any) -> None:
        """A page's size and cursor."""
        self.integer("limit", limit)
        self.string("cursor", cursor)


# ── Path parameters and headers ──────────────────────────────────────────────


def check_path_uuid(field: str, value: Any) -> None:
    """A UUID path parameter: an empty one would address another route."""
    if value is None or value == "":
        raise field_error(field, "is required")
    if not is_uuid(value):
        raise field_error(field, "must be a UUID")


def check_path_tx_id(field: str, value: Any) -> None:
    """A transaction id path parameter (payments, subscriptions, bills, sessions)."""
    if value is None or value == "":
        raise field_error(field, "is required")
    if not is_tx_id(value):
        raise field_error(field, "must be a transaction id (pay@…, sub@…, sub-hist@… or a UUID)")


def check_path_required(field: str, value: Any) -> None:
    """A free-form path parameter (a reference, an email, an event id): only its presence."""
    if not isinstance(value, str) or trim_space(value) == "":
        raise field_error(field, "is required")


def check_on_behalf_of(value: Any) -> None:
    """An ``On-Behalf-Of`` value: ``""``/``None`` (none) or a non-nil UUID."""
    if value is None or value == "":
        return
    if not is_uuid(value) or value == _NIL_UUID:
        raise field_error("onBehalfOf", "must be a member's userUuid (a UUID, not the nil UUID)")


def check_request_id(value: Any) -> None:
    """An ``X-Request-Id`` value."""
    if not is_request_id(value):
        raise field_error("X-Request-Id", "must be 1 to 128 characters among A-Z a-z 0-9 - _ . :")


def check_idempotency_key(value: Any) -> None:
    """An ``Idempotency-Key`` value."""
    if not is_idempotency_key(value):
        raise field_error(
            "Idempotency-Key", "must be 1 to 255 printable ASCII characters without spaces"
        )


def known(values: Iterable[str]) -> List[str]:
    """The values of an enum, as a list (for :meth:`Validator.one_of`)."""
    return [str(v) for v in values]
