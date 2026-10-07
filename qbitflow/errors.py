"""
The SDK's errors.

Every error the SDK raises derives from :class:`QBitFlowError` and, through it, from
:class:`ApiError`, which carries the fields every error has: ``status`` (the HTTP status, ``None``
when no response was received), ``code`` (the API's machine-readable code, ``""`` when absent),
``message``, ``details`` (never ``None``), ``request_id``, ``field_errors`` and ``raw_body``.

Catch the most specific class you can act on (``except qbitflow.NotFoundError``), and
:class:`ApiError` for the rest. Branch on ``code``, never on ``message``.
"""

from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus
from typing import Any, Dict, Iterable, List, Optional

from ._compat import StrEnum

__all__ = [
    "FieldError",
    "QBitFlowError",
    "ApiError",
    "ValidationError",
    "BadRequestError",
    "AuthenticationError",
    "PermissionDeniedError",
    "NotFoundError",
    "ConflictError",
    "GoneError",
    "IdempotencyError",
    "RateLimitError",
    "ServerError",
    "NetworkError",
    "WebhookSignatureError",
    "WebhookSignatureReason",
    "is_retryable",
]

# Error codes the SDK branches on (the API's stable ``code`` values).
CODE_VALIDATION_FAILED = "validation_failed"
CODE_IDEMPOTENCY_KEY_IN_USE = "idempotency_key_in_use"
CODE_IDEMPOTENCY_KEY_REUSED = "idempotency_key_reused"
CODE_INVALID_SIGNATURE = "invalid_signature"


@dataclass(frozen=True)
class FieldError:
    """One failing input of a validation error.

    Attributes:
        field: The input's wire name, dotted when nested (e.g. ``frequency.unit``).
        message: What is wrong with it.
    """

    field: str
    message: str

    def __str__(self) -> str:
        return f"{self.field}: {self.message}"


class QBitFlowError(Exception):
    """Base of every error the SDK raises."""

    status: Optional[int]
    code: str
    message: str
    details: Dict[str, Any]
    request_id: str
    field_errors: List[FieldError]
    raw_body: bytes

    def __init__(
        self,
        message: str = "",
        *,
        status: Optional[int] = None,
        code: str = "",
        details: Optional[Dict[str, Any]] = None,
        request_id: str = "",
        field_errors: Optional[Iterable[FieldError]] = None,
        raw_body: bytes = b"",
    ) -> None:
        self.status = status
        self.code = code
        self.message = message
        self.details = details if details is not None else {}
        self.request_id = request_id
        self.field_errors = list(field_errors or [])
        self.raw_body = raw_body
        super().__init__(message)

    def __str__(self) -> str:
        """``"<message> (status <status>, code <code>, request <requestId>)"`` followed by
        ``"; <field>: <message>"`` per field error; parts without a value are left out."""
        text = self.message or "qbitflow error"
        meta = []
        if self.status:
            meta.append(f"status {self.status}")
        if self.code:
            meta.append(f"code {self.code}")
        if self.request_id:
            meta.append(f"request {self.request_id}")
        if meta:
            text += " (" + ", ".join(meta) + ")"
        for fe in self.field_errors:
            text += f"; {fe.field}: {fe.message}"
        if self.__cause__ is not None:
            text += f": {self.__cause__}"
        return text

    def __repr__(self) -> str:
        return f"{type(self).__name__}({str(self)!r})"


class ApiError(QBitFlowError):
    """An HTTP error answer of the API, and the base of every typed error below.

    Raised as is for an HTTP error without a more specific class (e.g. 413
    ``request_too_large``). ``except ApiError`` catches every SDK error, like Go's ``*APIError``.
    """


class ValidationError(ApiError):
    """A 400 ``validation_failed``, or an input the SDK refused before sending anything
    (``status`` is ``None``). ``field_errors`` names each failing input by its wire name."""


class BadRequestError(ApiError):
    """Any other 400 (``bad_request``, ``foreign_key_violation``, …)."""


class AuthenticationError(ApiError):
    """A 401: the API key is missing, unknown, expired or revoked."""


class PermissionDeniedError(ApiError):
    """A 403 (``forbidden``, ``policy_disabled`` with ``details["policy"]``, ``plan_required``)."""


class NotFoundError(ApiError):
    """A 404: the resource does not exist, or is outside the request's space."""


class ConflictError(ApiError):
    """A 409 (``unique_violation`` with ``details["field"]``, ``tx_already_sent``,
    ``merchant_not_ready`` with ``details["reason"]``, ``refund_already_exists`` with
    ``details["refundUuid"]``, ``held_funds_pending``, ``already_joined``, ``payment_not_due``,
    ``conflict``, ``idempotency_key_in_use``, …)."""


class GoneError(ApiError):
    """A 410 (``merchant_closed``): the merchant's space is closed."""


class IdempotencyError(ApiError):
    """A 422 ``idempotency_key_reused``: the Idempotency-Key was already used for a different
    request. A caller bug; never retried."""


class RateLimitError(ApiError):
    """A 429, raised once the retries are exhausted, or at once when the API asks to wait more
    than 60 seconds.

    Attributes:
        retry_after: How long the API asked to wait, in seconds (the ``Retry-After`` header,
            else ``details.retryAfterSeconds``); ``None`` when unknown.
        limit: The number of requests allowed per period (``details.limit``); ``None`` when unknown.
        period_seconds: The limit's period, in seconds (``details.periodSeconds``); ``None``
            when unknown.
    """

    retry_after: Optional[float]
    limit: Optional[int]
    period_seconds: Optional[int]

    def __init__(
        self,
        message: str = "",
        *,
        retry_after: Optional[float] = None,
        limit: Optional[int] = None,
        period_seconds: Optional[int] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.retry_after = retry_after
        self.limit = limit
        self.period_seconds = period_seconds


class ServerError(ApiError):
    """A 5xx (503 ``network_unavailable`` and 504 ``timeout`` included), an unexpected 3xx
    (redirects are never followed), or a 2xx whose body is not the expected JSON."""


class NetworkError(ApiError):
    """No response was received (DNS, connection, TLS, timeout). The cause is chained
    (``__cause__``)."""


class WebhookSignatureReason(StrEnum):
    """Why a webhook signature was refused (:attr:`WebhookSignatureError.reason`)."""

    #: The ``QBitFlow-Signature`` header is empty.
    MISSING_HEADER = "missingHeader"
    #: No ``t``, a ``t`` that is not an integer, a duplicate ``t``, or no ``v1``.
    MALFORMED_HEADER = "malformedHeader"
    #: ``t`` is too far from now (either direction).
    TIMESTAMP_OUTSIDE_TOLERANCE = "timestampOutsideTolerance"
    #: No ``v1`` matches the expected signature.
    NO_MATCHING_SIGNATURE = "noMatchingSignature"
    #: The API's check (``POST /webhooks/verify``) refused it.
    INVALID_SIGNATURE = "invalidSignature"


class WebhookSignatureError(ApiError):
    """A webhook's signature could not be verified: locally (``status`` ``None``) or by the API
    (400 ``invalid_signature``). ``reason`` says why."""

    reason: WebhookSignatureReason

    def __init__(self, message: str = "", *, reason: WebhookSignatureReason, **kwargs: Any) -> None:
        super().__init__(message, **kwargs)
        self.reason = reason


def is_retryable(error: Optional[BaseException]) -> bool:
    """Whether ``error`` is a failure the SDK's retry policy treats as transient: a network error
    or timeout, a 5xx, a 429, or a 409 ``idempotency_key_in_use``.

    It does not say whether the method may be retried (only reads and the 7 idempotent creates
    are retried automatically).
    """
    if isinstance(error, (NetworkError, RateLimitError)):
        return True
    if isinstance(error, ServerError):
        return (error.status or 0) >= 500
    if isinstance(error, ConflictError):
        return error.code == CODE_IDEMPOTENCY_KEY_IN_USE
    return False


# ── Constructors used by the SDK ──────────────────────────────────────────────


def validation_error(message: str, fields: Iterable[FieldError] = ()) -> ValidationError:
    """A client-side ValidationError: no request was sent."""
    return ValidationError(message, field_errors=fields)


def field_error(field: str, message: str) -> ValidationError:
    """A client-side ValidationError for one input; ``message`` follows the field's name."""
    return validation_error("validation failed", [FieldError(field, f"{field} {message}")])


def signature_error(reason: WebhookSignatureReason, message: str) -> WebhookSignatureError:
    """A local webhook signature failure."""
    return WebhookSignatureError(message, reason=reason)


def status_message(status: int) -> str:
    """The default message for a status without a body message ("not found")."""
    try:
        return HTTPStatus(status).phrase.lower()
    except ValueError:
        return f"http status {status}"
