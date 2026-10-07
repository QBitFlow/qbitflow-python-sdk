"""
Local webhook signature verification.

Verifying locally needs your webhook secret but no network call, so it keeps working when
the API is unreachable and costs nothing per webhook. The alternative,
``client.webhooks.verify()``, asks QBitFlow to check the signature for you: no secret
required, but one round-trip per webhook.
"""

from __future__ import annotations

import hmac
import json
import math
import re
import time
from hashlib import sha256
from typing import Any, Mapping, Optional, Type, TypedDict, TypeVar, Union

import pydantic

from qbitflow.dto.base_model import validation_error_from_pydantic
from qbitflow.dto.transaction.session import SessionWebhookResponse
from qbitflow.dto.transaction.subscription import SubscriptionWebhook
from qbitflow.exceptions.exceptions import ValidationError

#: Header carrying the HMAC signature, formatted ``sha256=<hex>``.
HEADER_SIGNATURE = "X-Webhook-Signature-256"
#: Header carrying the send time, in unix seconds.
HEADER_TIMESTAMP = "X-Webhook-Timestamp"
#: Header carrying the transaction id, e.g. ``pay@<uuid>``.
HEADER_WEBHOOK_ID = "X-Webhook-Id"

#: The dashboard "Test webhook" id.
TEST_WEBHOOK_ID = "test-webhook-id"

#: How far a webhook's timestamp may be from the current clock before it is rejected as a
#: replay. Must match the server's ``MaxTimestampAge``.
DEFAULT_MAX_TIMESTAMP_AGE_SECONDS = 300

_SIGNATURE_PREFIX = "sha256="
# Go's strconv.ParseInt: an optional sign and ASCII digits, nothing else (no whitespace).
_TIMESTAMP_RE = re.compile(r"[+-]?[0-9]+")
_INT64_MIN, _INT64_MAX = -(2**63), 2**63 - 1
# A lone UTF-16 surrogate code point (a valid pair is a single code point in a Python str).
_SURROGATE_RE = re.compile("[\ud800-\udfff]")


def _replace_surrogates(value: str) -> str:
    """Replace lone surrogates with U+FFFD, as Go's JSON decoder does."""
    return _SURROGATE_RE.sub("\ufffd", value)


def normalise_payload(value: Any) -> Any:
    """
    Return a decoded JSON value with every lone surrogate replaced by U+FFFD (in keys and
    strings, at any depth) — what the Go API sees once it has decoded the same payload.
    Objects stay dicts and arrays stay lists, so ``{}`` and ``[]`` are preserved.
    """
    if isinstance(value, str):
        return _replace_surrogates(value)
    if isinstance(value, dict):
        return {_replace_surrogates(str(k)): normalise_payload(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalise_payload(item) for item in value]
    return value


def _reject_constant(name: str) -> Any:
    """Refuse ``NaN`` / ``Infinity``: JSON has no such literals and Go rejects them too."""
    raise ValidationError(f"webhook payload contains a non-JSON number literal: {name}")


def _format_number(value: float) -> str:
    """
    Render a float64 exactly the way Go's ``encoding/json`` (and JavaScript) do.

    The QBitFlow API is written in Go and decodes every JSON number into a ``float64`` before
    re-encoding it for signing. Its output rules are ECMAScript's: the shortest digit string
    that round-trips, written in plain decimal for exponents in ``[-6, 21)`` and in ``d.ddde±x``
    form outside that range, with no ``.0`` on whole numbers and no zero-padded exponent.

    Python's ``repr`` picks the same shortest digits but formats them differently (``1e-06``
    instead of ``0.000001``, ``1.234e-05`` instead of ``0.00001234``, ``1e+16`` instead of
    ``10000000000000000``), so a payload carrying e.g. a small token price would hash to a
    different signature. This function re-lays-out ``repr``'s digits under Go's rules.
    """
    if math.isnan(value) or math.isinf(value):
        raise ValidationError("webhook payload contains a non-finite number")

    if value == 0:
        # Go preserves the sign of a negative zero.
        return "-0" if math.copysign(1.0, value) < 0 else "0"

    mantissa, _, exponent = repr(abs(value)).partition("e")
    int_part, _, frac_part = mantissa.partition(".")
    digits = int_part + frac_part
    # value == 0.<digits> x 10**position
    position = len(int_part) + (int(exponent) if exponent else 0)

    stripped = digits.lstrip("0")
    position -= len(digits) - len(stripped)
    digits = stripped.rstrip("0")
    count = len(digits)

    if count <= position <= 21:
        rendered = digits + "0" * (position - count)
    elif 0 < position <= 21:
        rendered = digits[:position] + "." + digits[position:]
    elif -6 < position <= 0:
        rendered = "0." + "0" * (-position) + digits
    else:
        exp = position - 1
        rendered = digits[0] + ("." + digits[1:] if count > 1 else "")
        rendered += "e" + ("+" if exp > 0 else "-") + str(abs(exp))

    return ("-" if value < 0 else "") + rendered


def _encode_string(value: str) -> str:
    """
    Quote a string the way Go's ``encoding/json`` does.

    ``json.dumps`` already matches Go for quotes, backslashes and control characters
    (``\\n``, ``\\t``, ``\\u001f`` …) and, with ``ensure_ascii=False``, leaves other Unicode
    literal. Go additionally escapes ``<``, ``>`` and ``&`` (HTML-safe output) and the line
    terminators U+2028 / U+2029; those are applied here.
    """
    return (
        json.dumps(_replace_surrogates(value), ensure_ascii=False)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def _encode_canonical(value: Any) -> str:
    """
    Serialize an already-decoded payload into its canonical form.

    Objects are emitted with keys in code-point order (identical to Go's UTF-8 byte order once
    lone surrogates are replaced with U+FFFD, as Go's decoder does; a later duplicate key
    wins), arrays keep their order, and every number goes through :func:`_format_number`.
    """
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        return _encode_string(value)
    if isinstance(value, (int, float)):
        try:
            return _format_number(float(value))
        except OverflowError as exc:
            raise ValidationError("webhook payload contains a number too large for JSON") from exc
    if isinstance(value, dict):
        normalised = {}
        for key, item in value.items():
            normalised[_replace_surrogates(str(key))] = item
        items = sorted(normalised.items())
        return "{" + ",".join(f"{_encode_string(k)}:{_encode_canonical(v)}" for k, v in items) + "}"
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_encode_canonical(item) for item in value) + "]"

    raise ValidationError(
        f"webhook payload contains a value that is not JSON: {type(value).__name__}"
    )


def canonical_json(payload: Union[str, bytes, bytearray, Mapping[str, Any], Any]) -> str:
    """
    Render a webhook payload the way QBitFlow signs it.

    The signature covers a *canonical* rendering rather than the bytes as they arrived,
    because JSON key order is not significant and intermediaries (proxies, frameworks,
    logging layers) routinely re-serialize a body and reorder keys. Signing raw bytes would
    make verification fail for a payload that is in fact identical.

    Canonical means: object keys sorted at every level, no insignificant whitespace,
    non-ASCII left as literal UTF-8, ``<``, ``>``, ``&``, U+2028 and U+2029 escaped as
    ``\\u003c``, ``\\u003e``, ``\\u0026``, ``\\u2028``, ``\\u2029``, and every number
    rendered from its float64 value under Go's formatting rules (see :func:`_format_number`).

    Those rules come from Go: the QBitFlow API is written in Go and its ``encoding/json``
    behaves exactly so. Every QBitFlow SDK reproduces them, so all four compute an identical
    signature for the same payload, and each SDK's test suite pins the same Go-generated
    reference vectors.

    Args:
        payload: Raw JSON (``str``/``bytes``) or an already-decoded value.

    Returns:
        The canonical JSON string that gets signed.

    Raises:
        ValidationError: If the payload is missing or is not valid JSON.
    """
    if payload is None:
        raise ValidationError("webhook payload is required")

    if isinstance(payload, (bytes, bytearray)):
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValidationError(f"webhook payload is not valid JSON: {exc}") from exc
    elif isinstance(payload, str):
        text = payload
    else:
        text = None

    if text is not None:
        try:
            # Go decodes every JSON number into float64; ``parse_int=float`` reproduces that,
            # so an integer beyond 2**53 rounds exactly as it does on the server.
            decoded = json.loads(text, parse_int=float, parse_constant=_reject_constant)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"webhook payload is not valid JSON: {exc}") from exc
    else:
        decoded = payload

    return _encode_canonical(decoded)


def compute_webhook_signature(secret: str, timestamp: str, payload: Any) -> str:
    """
    Compute the signature QBitFlow would send for a payload.

    The signed message is ``<timestamp>.<canonical-json>``; the result is the hex-encoded
    HMAC-SHA256 of that message under your webhook secret, prefixed with ``sha256=`` -
    exactly the value delivered in the ``X-Webhook-Signature-256`` header.

    Exported mainly so you can generate valid webhooks in your own tests. To check an
    incoming webhook use :func:`verify_webhook_signature`, which also enforces the replay
    window and compares in constant time.

    Args:
        secret: Your webhook secret, from the QBitFlow dashboard.
        timestamp: The ``X-Webhook-Timestamp`` value.
        payload: The webhook body.

    Returns:
        The signature, formatted ``sha256=<hex>``.
    """
    if not secret:
        raise ValidationError("webhook secret is required")
    if not timestamp:
        raise ValidationError("webhook timestamp is required")

    message = f"{timestamp}.{canonical_json(payload)}".encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), message, sha256).hexdigest()

    return _SIGNATURE_PREFIX + digest


def verify_webhook_signature(
    secret: str,
    timestamp: str,
    signature: str,
    payload: Any,
    *,
    max_timestamp_age_seconds: int = DEFAULT_MAX_TIMESTAMP_AGE_SECONDS,
    now_seconds: Optional[int] = None,
    skip_timestamp_check: bool = False,
) -> None:
    """
    Verify a webhook locally, without calling the QBitFlow API.

    Performs the same three checks the server does:

    1. The timestamp is within ``max_timestamp_age_seconds`` of now, which is what stops a
       captured webhook from being replayed later.
    2. The HMAC-SHA256 of ``<timestamp>.<canonical-json>`` under your secret matches.
    3. The comparison is constant-time, so a timing side channel cannot be used to guess
       the signature byte by byte.

    The secret comes from the QBitFlow dashboard. Treat it like a password: keep it in your
    environment or secret manager, never in source control, and never send it anywhere.

    Returns ``None`` when the webhook is authentic. Any exception means do not trust the
    payload.

    Args:
        secret: Your webhook secret.
        timestamp: The ``X-Webhook-Timestamp`` header value.
        signature: The ``X-Webhook-Signature-256`` header value.
        payload: The webhook body, raw or decoded.
        max_timestamp_age_seconds: Replay window. Must match the server's setting. ``0`` or a
            negative value means the default (:data:`DEFAULT_MAX_TIMESTAMP_AGE_SECONDS`).
        now_seconds: Override the clock. Test-only.
        skip_timestamp_check: Disable the replay check. Leave this off in production -
            without it a captured webhook can be replayed forever. It exists for replaying
            stored webhooks in a test harness.

    Raises:
        ValidationError: If the webhook is not authentic.

    Example:
        >>> from qbitflow.webhooks import verify_webhook_signature, extract_webhook_headers
        >>> @app.post("/webhooks")
        ... def handle(request):
        ...     headers = extract_webhook_headers(request.headers)
        ...     verify_webhook_signature(
        ...         os.environ["QBITFLOW_WEBHOOK_SECRET"],
        ...         headers["timestamp"],
        ...         headers["signature"],
        ...         request.body,
        ...     )
        ...     event = json.loads(request.body)
    """
    if not signature:
        raise ValidationError("webhook signature is required")

    if not skip_timestamp_check:
        _verify_timestamp(timestamp, max_timestamp_age_seconds, now_seconds)

    expected = compute_webhook_signature(secret, timestamp, payload)

    # compare_digest does not leak how many leading bytes matched.
    if not hmac.compare_digest(expected.encode("utf-8"), signature.encode("utf-8")):
        raise ValidationError("webhook signature mismatch")


def _verify_timestamp(timestamp: str, max_age_seconds: int, now_seconds: Optional[int]) -> None:
    """
    Enforce the replay window.

    The comparison is absolute, so a webhook from a clock slightly ahead of ours is treated
    the same as one slightly behind.
    """
    if not timestamp:
        raise ValidationError("webhook timestamp is required")

    if not isinstance(timestamp, str) or not _TIMESTAMP_RE.fullmatch(timestamp):
        raise ValidationError("webhook timestamp is not a unix-seconds integer")
    sent = int(timestamp)
    if sent < _INT64_MIN or sent > _INT64_MAX:
        raise ValidationError("webhook timestamp is not a unix-seconds integer")

    if max_age_seconds <= 0:
        max_age_seconds = DEFAULT_MAX_TIMESTAMP_AGE_SECONDS

    now = int(time.time()) if now_seconds is None else now_seconds
    # Python integers do not overflow, so this is safe for any int64 timestamp.
    age = abs(now - sent)

    if age > max_age_seconds:
        raise ValidationError(
            f"webhook timestamp expired: age {age}s exceeds the maximum of " f"{max_age_seconds}s"
        )


class WebhookHeaders(TypedDict):
    """The QBitFlow headers of an incoming webhook, as returned by extract_webhook_headers."""

    signature: str
    timestamp: str
    webhook_id: str
    is_test: bool


def extract_webhook_headers(headers: Mapping[str, Any]) -> WebhookHeaders:
    """
    Pull the QBitFlow headers out of an incoming request.

    Accepts any mapping, so it works across frameworks without the SDK having to know about
    them: Flask's ``request.headers``, Django's ``request.headers``, FastAPI/Starlette's
    ``request.headers``, or a plain dict. Lookup is case-insensitive, since HTTP header
    names are, and a list value (some frameworks expose repeated headers that way) yields
    its first entry.

    Returns:
        A dict with ``signature``, ``timestamp``, ``webhook_id`` and ``is_test`` keys.
        Missing headers come back as empty strings rather than raising, so you can report a
        clear error yourself.

    Example:
        >>> headers = extract_webhook_headers(request.headers)
        >>> if headers["is_test"]:
        ...     return 200  # connectivity check, nothing to process
    """
    lowered = {str(key).lower(): value for key, value in headers.items()}

    def get(name: str) -> str:
        value = lowered.get(name.lower(), "")
        if isinstance(value, (list, tuple)):
            return str(value[0]) if value else ""
        return "" if value is None else str(value)

    webhook_id = get(HEADER_WEBHOOK_ID)

    return {
        "signature": get(HEADER_SIGNATURE),
        "timestamp": get(HEADER_TIMESTAMP),
        "webhook_id": webhook_id,
        "is_test": webhook_id == TEST_WEBHOOK_ID,
    }


def _decode_webhook_body(body: Any) -> Any:
    """Parse a raw webhook body (bytes/str) as JSON; an already-decoded value passes through."""
    if body is None:
        raise ValidationError("webhook payload is required")
    if isinstance(body, (bytes, bytearray, str)):
        try:
            return json.loads(body, parse_constant=_reject_constant)
        except (ValueError, TypeError) as exc:
            raise ValidationError(f"webhook payload is not valid JSON: {exc}") from exc
    return body


def parse_session_webhook(body: Any) -> SessionWebhookResponse:
    """
    Parse a transaction webhook delivery into a :class:`SessionWebhookResponse`.

    Verify the signature first (:func:`verify_webhook_signature` or
    ``client.webhooks.verify``). The payload is decoded with the same policy as API responses:
    absent or ``null`` non-pointer fields become their zero value, ``session`` is resolved to a
    :class:`~qbitflow.dto.transaction.session.OneTimePaymentSession` or
    :class:`~qbitflow.dto.transaction.session.SubscriptionSession` from its ``txType``, and
    unknown enum values are kept as plain strings.

    Args:
        body: The raw request body (``bytes``/``str``) or the already-decoded JSON object.

    Raises:
        ValidationError: If the body is not JSON, or a field has the wrong JSON type.
    """
    return _parse_webhook(SessionWebhookResponse, body)


def parse_subscription_webhook(body: Any) -> SubscriptionWebhook:
    """
    Parse a subscription webhook delivery into a :class:`SubscriptionWebhook`.

    Verify the signature first. ``data`` is resolved from ``type``: a
    :class:`~qbitflow.dto.transaction.subscription.SubscriptionStatusTransition` for
    ``status_transition``, a :class:`~qbitflow.dto.transaction.subscription.SubscriptionHistory`
    for ``billing``, and the raw ``dict`` for a type this SDK does not know yet.

    Args:
        body: The raw request body (``bytes``/``str``) or the already-decoded JSON object.

    Raises:
        ValidationError: If the body is not JSON, or a field has the wrong JSON type.
    """
    return _parse_webhook(SubscriptionWebhook, body)


_WebhookT = TypeVar("_WebhookT", SessionWebhookResponse, SubscriptionWebhook)


def _parse_webhook(model: Type[_WebhookT], body: Any) -> _WebhookT:
    decoded = _decode_webhook_body(body)
    if not isinstance(decoded, dict):
        raise ValidationError(
            f"webhook payload must be a JSON object, got {type(decoded).__name__}"
        )
    try:
        return model.model_validate(decoded)
    except pydantic.ValidationError as exc:
        raise validation_error_from_pydantic(exc, "webhook payload does not match") from exc
