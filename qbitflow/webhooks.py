"""
Webhook verification and parsing, usable without a client (a webhook receiver may not hold an
API key)::

    from qbitflow import webhooks

    event = webhooks.construct_event(raw_body, request.headers["QBitFlow-Signature"], secret)

:func:`verify` checks the ``QBitFlow-Signature`` header (``t=<unix seconds>,v1=<hex>``, two
``v1`` during a secret rotation) over the **raw body**: never re-serialize it.
:func:`construct_event` verifies, then parses; :func:`parse_event` only parses (for a body already
verified, e.g. by ``client.webhooks.verify_remote``).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import time
from datetime import datetime
from typing import Any, Callable, List, Optional, Tuple, Union

import pydantic

from ._transport import adapter
from .errors import (
    WebhookSignatureReason,
    field_error,
    signature_error,
)
from .models.enums import WebhookPayloadVersion
from .models.events import Event

__all__ = [
    "SIGNATURE_HEADER",
    "EVENT_ID_HEADER",
    "EVENT_TYPE_HEADER",
    "WEBHOOK_VERSION_HEADER",
    "DEFAULT_TOLERANCE",
    "MAX_BODY_BYTES",
    "verify",
    "construct_event",
    "parse_event",
]

#: Carries ``t=<unix seconds>,v1=<hex>`` (two ``v1`` during a secret rotation).
SIGNATURE_HEADER = "QBitFlow-Signature"
#: Carries the event's id (``evt_…``): deduplicate on it.
EVENT_ID_HEADER = "QBitFlow-Event-Id"
#: Carries the event's type.
EVENT_TYPE_HEADER = "QBitFlow-Event-Type"
#: Carries the payload version (``v1`` or ``v2``).
WEBHOOK_VERSION_HEADER = "QBitFlow-Webhook-Version"
#: How far a signature's timestamp may be from now, in seconds.
DEFAULT_TOLERANCE = 300
#: The largest webhook body the SDK accepts (the API's own limit): 1 MiB.
MAX_BODY_BYTES = 1 << 20

RawBody = Union[bytes, bytearray, memoryview, str]
#: A point in time (an aware ``datetime`` or unix seconds), or a callable returning one.
Clock = Union[datetime, float, int, Callable[[], Union[datetime, float, int]]]

_DIGITS = re.compile(r"[0-9]+")
_MAX_INT64 = 2**63 - 1


def _body_bytes(raw_body: Any) -> bytes:
    if isinstance(raw_body, str):
        try:
            return raw_body.encode("utf-8")
        except UnicodeEncodeError:
            raise field_error("body", "must be valid UTF-8") from None
    if isinstance(raw_body, (bytes, bytearray, memoryview)):
        return bytes(raw_body)
    raise field_error("body", "must be the raw body (bytes or str)")


def _now_seconds(now: Optional[Clock]) -> float:
    value = now() if callable(now) else now
    if value is None:
        return time.time()
    if isinstance(value, datetime):
        return value.timestamp()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    raise field_error("now", "must be a datetime, unix seconds, or a callable returning one")


def _parse_signature_header(header: str) -> Optional[Tuple[str, List[str]]]:
    """Split ``t=…,v1=…[,v1=…]``: parts on ``,``, each on its first ``=``, spaces trimmed, other
    keys ignored. It needs exactly one ``t`` made of ASCII digits, and a ``v1``."""
    timestamp: Optional[str] = None
    signatures: List[str] = []
    for part in header.split(","):
        key, sep, value = part.partition("=")
        if not sep:
            continue
        key, value = key.strip(), value.strip()
        if key == "t":
            if timestamp is not None or _DIGITS.fullmatch(value) is None:
                return None
            if int(value) > _MAX_INT64:
                return None
            timestamp = value
        elif key == "v1":
            signatures.append(value)
    if timestamp is None or not signatures:
        return None
    return timestamp, signatures


def verify(
    raw_body: RawBody,
    signature_header: Optional[str],
    secret: str,
    *,
    tolerance: float = DEFAULT_TOLERANCE,
    now: Optional[Clock] = None,
) -> None:
    """Check a webhook delivery's signature.

    It accepts the delivery when ``t`` (ASCII digits) is within ``tolerance`` seconds of now
    (either direction) and any ``v1`` equals ``hex(HMAC-SHA256(secret, t + "." + raw_body))``,
    compared in constant time (``t`` as received, leading zeros kept); during a secret rotation
    either secret's signature matches.

    Args:
        raw_body: The body exactly as received (bytes, or the str it decodes to).
        signature_header: The ``QBitFlow-Signature`` header.
        secret: The endpoint's ``whsec_…`` secret (the whole string is the key).
        tolerance: Seconds the timestamp may be from now (default 300; 0 or less keeps it).
        now: The clock (tests, replays): an aware datetime, unix seconds, or a callable.

    Raises:
        WebhookSignatureError: with ``reason`` ``missingHeader``, ``malformedHeader``,
            ``timestampOutsideTolerance`` or ``noMatchingSignature``.
        ValidationError: an empty ``secret`` (a configuration error).
    """
    if not isinstance(secret, str) or secret == "":
        raise field_error("secret", "is required (the endpoint's whsec_… secret)")
    body = _body_bytes(raw_body)
    if signature_header is None or (
        isinstance(signature_header, str) and signature_header.strip() == ""
    ):
        raise signature_error(
            WebhookSignatureReason.MISSING_HEADER, "missing QBitFlow-Signature header"
        )
    if not isinstance(signature_header, str):
        raise field_error("signatureHeader", "must be a string")
    if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)):
        raise field_error("tolerance", "must be a number of seconds")
    window = float(tolerance) if tolerance > 0 else float(DEFAULT_TOLERANCE)

    parsed = _parse_signature_header(signature_header)
    if parsed is None:
        raise signature_error(
            WebhookSignatureReason.MALFORMED_HEADER,
            "malformed QBitFlow-Signature header: it needs one t=<unix seconds> and at least one "
            "v1=<signature>",
        )
    timestamp, signatures = parsed

    if abs(_now_seconds(now) - int(timestamp)) > window:
        raise signature_error(
            WebhookSignatureReason.TIMESTAMP_OUTSIDE_TOLERANCE,
            f"webhook timestamp is outside the tolerance ({window:g}s)",
        )

    expected = hmac.new(
        # The signed text is t exactly as received (leading zeros kept).
        secret.encode("utf-8"),
        timestamp.encode("ascii") + b"." + body,
        hashlib.sha256,
    ).hexdigest()
    matched = False
    for signature in signatures:
        # Every v1 is compared, in constant time: never stop at the first.
        if hmac.compare_digest(expected.encode("ascii"), signature.encode("utf-8")):
            matched = True
    if not matched:
        raise signature_error(
            WebhookSignatureReason.NO_MATCHING_SIGNATURE, "no webhook signature matches"
        )


def parse_event(raw_body: RawBody) -> Event:
    """Parse a webhook body (or an event of the log) **without** verifying it: use it on a body
    already verified.

    Returns:
        The event, typed by its ``type`` (:class:`~qbitflow.UnknownEvent` for a type this SDK
        does not know: never an error).

    Raises:
        ValidationError: a body that is not a JSON object, whose ``version`` is not ``v2`` (an
            endpoint still on v1: move it to v2 in the dashboard), or that does not match its
            event type.
    """
    body = _body_bytes(raw_body).strip()
    if not body or not body.startswith(b"{"):
        raise field_error("body", "must be a JSON object (a webhook event)")
    try:
        data = json.loads(body)
    except ValueError:
        raise field_error("body", "is not a valid webhook event") from None
    if not isinstance(data, dict):  # pragma: no cover - guarded by the "{" check
        raise field_error("body", "must be a JSON object (a webhook event)")
    if data.get("version") != WebhookPayloadVersion.V2:
        raise field_error(
            "version", "must be v2: the endpoint is still on v1, move it to v2 in the dashboard"
        )
    try:
        event: Event = adapter(Event).validate_python(data)
    except pydantic.ValidationError as exc:
        errors = exc.errors()
        where = ".".join(str(p) for p in errors[0]["loc"][1:]) if errors else ""
        detail = str(errors[0]["msg"]).removeprefix("Value error, ") if errors else ""
        raise field_error(
            "body", f"is not a valid webhook event ({where + ': ' if where else ''}{detail})"
        ) from None
    return event


def construct_event(
    raw_body: RawBody,
    signature_header: Optional[str],
    secret: str,
    *,
    tolerance: float = DEFAULT_TOLERANCE,
    now: Optional[Clock] = None,
) -> Event:
    """Verify a webhook delivery (:func:`verify`), then parse it (:func:`parse_event`)."""
    verify(raw_body, signature_header, secret, tolerance=tolerance, now=now)
    return parse_event(raw_body)
