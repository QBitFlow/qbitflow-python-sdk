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
import re
import time
from hashlib import sha256
from typing import Any, Mapping, Optional, Union

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
_INTEGER_RE = re.compile(r"^-?\d+$")


def _normalise(value: Any) -> Any:
    """
    Recursively prepare a decoded payload for canonical serialization.

    Two things happen here:

    * Nested structures are walked so every mapping can be sorted on the way out.
    * A float that holds a whole number becomes an int.

    That second rule matters more than it looks. The API is written in Go, which decodes
    JSON numbers into ``float64`` and re-encodes ``1.0`` as ``1``. Python's ``json`` keeps
    ``1.0`` a float and would emit ``1.0``, producing a different byte string and therefore
    a different signature for a payload that is in fact identical.
    """
    if isinstance(value, bool):
        # bool is a subclass of int; check it first so True does not become 1.
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, dict):
        return {key: _normalise(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        # Arrays are ordered by definition: sorting them would change meaning.
        return [_normalise(item) for item in value]
    return value


def canonical_json(payload: Union[str, bytes, bytearray, Mapping[str, Any], Any]) -> str:
    """
    Render a webhook payload the way QBitFlow signs it.

    The signature covers a *canonical* rendering rather than the bytes as they arrived,
    because JSON key order is not significant and intermediaries (proxies, frameworks,
    logging layers) routinely re-serialize a body and reorder keys. Signing raw bytes would
    make verification fail for a payload that is in fact untouched.

    Canonical means: object keys sorted lexicographically at every level, no insignificant
    whitespace, non-ASCII left as literal UTF-8, and ``<``, ``>`` and ``&`` escaped as
    ``\\u003c``, ``\\u003e`` and ``\\u0026``.

    That last rule exists because Go's ``encoding/json`` escapes those three characters by
    default and the API signs with that default. Every QBitFlow SDK reproduces it so all of
    them compute an identical signature for the same payload.

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
            decoded = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValidationError(f"webhook payload is not valid JSON: {exc}") from exc
    elif isinstance(payload, str):
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"webhook payload is not valid JSON: {exc}") from exc
    else:
        decoded = payload

    rendered = json.dumps(
        _normalise(decoded),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    # These three only ever appear inside string values in JSON, so a blind replace is safe.
    return rendered.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


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
        max_timestamp_age_seconds: Replay window. Must match the server's setting.
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
    if not hmac.compare_digest(expected, signature):
        raise ValidationError("webhook signature mismatch")


def _verify_timestamp(timestamp: str, max_age_seconds: int, now_seconds: Optional[int]) -> None:
    """
    Enforce the replay window.

    The comparison is absolute, so a webhook from a clock slightly ahead of ours is treated
    the same as one slightly behind.
    """
    if not timestamp:
        raise ValidationError("webhook timestamp is required")

    if not _INTEGER_RE.match(timestamp):
        raise ValidationError("webhook timestamp is not a unix-seconds integer")

    now = int(time.time()) if now_seconds is None else now_seconds
    age = abs(now - int(timestamp))

    if age > max_age_seconds:
        raise ValidationError(
            f"webhook timestamp expired: age {age}s exceeds the maximum of " f"{max_age_seconds}s"
        )


def extract_webhook_headers(headers: Mapping[str, Any]) -> dict:
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
