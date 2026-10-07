"""
Custom exception classes for QBitFlow SDK.

This module defines a hierarchy of exceptions that can be raised during SDK operations.
All exceptions inherit from QBitFlowError for easy catching of all SDK-related errors.

HTTP status → exception type:

================  =====================================================================
Status            Exception
================  =====================================================================
400, 422          :class:`ValidationError` (same type as client-side validation)
401               :class:`AuthenticationError`
403               :class:`ForbiddenException`
404               :class:`NotFoundException`
409               :class:`ConflictError`
429               :class:`RateLimitError` (``retry_after`` in seconds when the API sent it)
other 4xx         :class:`InvalidRequestError`
5xx, 3xx, a 2xx   :class:`ServerError` (a subclass of :class:`APIError`)
with an empty,
non-JSON or
wrongly-typed
body
network/timeout   :class:`NetworkError` (after the retry budget is exhausted)
================  =====================================================================

Every exception carries ``message``, ``status_code`` (whenever an HTTP response was involved,
including response-shape failures) and ``fields`` (the per-field failures, empty otherwise).
Client-side validation — including request DTO construction — raises :class:`ValidationError`
with ``status_code=None``.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class FieldError:
    """
    A single field-level validation failure.

    The API reports validation failures as a list, one entry per offending field::

        {"errors": [{"field": "ProductName", "message": "ProductName is too short"},
                    {"field": "Price", "message": "Price is too short"}]}

    Attributes:
        field: Name of the offending field, as the API names it. Empty when the API
            reported a bare message with no field attached.
        message: The API's explanation for that field.
    """

    field: str
    message: str

    def __str__(self) -> str:
        """Render as ``field: message``, or just the message when there is no field."""
        return f"{self.field}: {self.message}" if self.field else self.message


class QBitFlowError(Exception):
    """
    Base exception class for all QBitFlow SDK errors.

    All exceptions raised by the SDK inherit from this class, making it easy
    to catch all SDK-related errors with a single except clause.

    Attributes:
        message: Human-readable error message.
        status_code: HTTP status code if applicable.
        response: Raw response data if available.
        fields: Per-field validation failures, when the API reported them; empty
            otherwise. Prefer this over parsing ``message`` when you need to map
            failures back onto form fields.
    """

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response: Optional[Dict[str, Any]] = None,
        fields: Optional[List[FieldError]] = None,
    ):
        """
        Initialize the exception.

        Args:
            message: Human-readable error message.
            status_code: HTTP status code if applicable.
            response: Raw response data if available.
            fields: Per-field validation failures, when the API reported them.
        """
        self.message = message
        self.status_code = status_code
        self.response = response
        self.fields = fields or []
        super().__init__(self.message)

    def __str__(self) -> str:
        """Return a string representation of the error."""
        if self.status_code:
            return f"[{self.status_code}] {self.message}"
        return self.message


class APIError(QBitFlowError):
    """
    Raised when the API returns an error response that fits no more specific category.

    :class:`ServerError` (5xx, unexpected redirects, malformed bodies) is a subclass, so an
    ``except APIError`` continues to catch server-side failures.

    Example:
        >>> try:
        ...     client.products.get_all()
        ... except APIError as e:  # also catches ServerError
        ...     print(f"API error: {e.message}")
        ...     print(f"Status code: {e.status_code}")
    """

    pass


class ServerError(APIError):
    """
    Raised when the API failed or answered with something the SDK cannot use.

    Covers a ``5xx`` response (after the retry budget for idempotent requests is spent), a
    ``3xx`` reaching the SDK (redirects are never followed; almost always a misconfigured
    ``base_url``), a ``2xx`` whose body is empty or not JSON (a proxy's HTML error page served
    with a 200), and a JSON body with a field of the wrong type. ``status_code`` is set.

    These are never the caller's fault, so they are kept apart from the request-side
    errors. Nothing was necessarily done wrong on your side; retry later or check
    ``base_url``.

    Example:
        >>> try:
        ...     client.products.get_all()
        ... except ServerError as e:
        ...     print(f"QBitFlow is unavailable: {e.message} (status {e.status_code})")
    """

    pass


class AuthenticationError(QBitFlowError):
    """
    Raised when authentication fails (HTTP 401).

    This typically indicates an invalid, expired or deleted API key.

    Example:
        >>> try:
        ...     client = QBitFlow(api_key="invalid_key")
        ...     client.products.get_all()
        ... except AuthenticationError:
        ...     print("Invalid API key provided")
    """

    pass


class ValidationError(QBitFlowError):
    """
    Raised when input validation fails.

    Covers both sides of the same problem: a value the SDK rejects before sending (including
    when a request DTO such as ``CreateProductDto`` is constructed), and a value the API
    rejects with a 400/422. One ``except`` therefore handles a field rejected locally and the
    same field rejected by the server, and ``.fields`` carries the per-field detail.

    Example:
        >>> try:
        ...     client.one_time_payments.create_session(
        ...         product_name="Coffee", description="A cup", price=0
        ...     )
        ... except ValidationError as e:
        ...     print(f"Validation failed: {e.message}")
        ...     for failure in e.fields:
        ...         print(failure.field, failure.message)
    """

    pass


class ForbiddenException(QBitFlowError):
    """
    Raised when the API key is valid but not permitted to perform the request (403).

    This is a *permissions* failure, not a malformed request: the credential was accepted
    but its role is too low for the operation. The most common cause is calling an
    admin-level operation — including ``on_behalf_of`` — with a user-level API key.

    Example:
        >>> try:
        ...     client.products.on_behalf_of(123).get_all()
        ... except ForbiddenException:
        ...     print("This API key is not admin-level")
    """

    pass


class NotFoundException(QBitFlowError):
    """
    Raised when a requested resource is not found (404).

    This typically occurs when trying to access a resource that doesn't exist, has been
    deleted, or belongs to another organization or user (existence is never revealed
    across tenants, so those also answer 404).

    Example:
        >>> try:
        ...     payment = client.one_time_payments.get("pay@non-existent")
        ... except NotFoundException:
        ...     print("Payment not found")
    """

    pass


class ConflictError(QBitFlowError):
    """
    Raised when the request conflicts with the current state of the resource (409).

    The API uses it for operations that are valid but not applicable right now — for
    example triggering a test billing cycle on a subscription that is not yet due.

    Example:
        >>> try:
        ...     client.subscriptions.execute_test_billing_cycle("sub@...")
        ... except ConflictError as e:
        ...     print(f"Not applicable yet: {e.message}")
    """

    pass


class RateLimitError(QBitFlowError):
    """
    Raised when API rate limit is exceeded (429).

    This occurs when too many requests are made in a short period. Rate-limited requests
    are not retried automatically.

    Attributes:
        retry_after: Seconds to wait before retrying, from the ``Retry-After`` header,
            or ``None`` when the API did not send one.

    Example:
        >>> try:
        ...     for i in range(1000):
        ...         client.products.get_all()
        ... except RateLimitError as e:
        ...     print(f"Rate limit exceeded: {e.message}")
        ...     if e.retry_after is not None:
        ...         time.sleep(e.retry_after)
    """

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response: Optional[Dict[str, Any]] = None,
        fields: Optional[List[FieldError]] = None,
        retry_after: Optional[int] = None,
    ):
        """
        Initialize the exception.

        Args:
            message: Human-readable error message.
            status_code: HTTP status code (429).
            response: Raw response data if available.
            fields: Per-field validation failures, when the API reported them.
            retry_after: Seconds to wait before retrying, when the API sent ``Retry-After``.
        """
        super().__init__(message, status_code=status_code, response=response, fields=fields)
        self.retry_after = retry_after


class NetworkError(QBitFlowError):
    """
    Raised when a network error occurs during API communication.

    This includes connection timeouts, DNS failures, and other network-related issues.
    Idempotent (``GET``) requests are retried before this is raised; ``POST``/``PUT``/
    ``DELETE`` requests are never retried, so the caller decides whether to resend.

    Example:
        >>> try:
        ...     payment = client.one_time_payments.get("pay@...")
        ... except NetworkError as e:
        ...     print(f"Network error: {e.message}")
    """

    pass


class InvalidRequestError(QBitFlowError):
    """
    Raised for a 4xx that has no more specific type, and for SDK misuse.

    Validation failures (400/422) raise :class:`ValidationError`, permissions
    failures (403) raise :class:`ForbiddenException`, conflicts (409) raise
    :class:`ConflictError`; this covers the remainder (405, 415, 425, …) plus local
    misuse such as a POST with no body.

    Example:
        >>> try:
        ...     client.products.get_all()
        ... except InvalidRequestError as e:  # e.g. a 405 from a misrouted proxy
        ...     print(f"Invalid request ({e.status_code}): {e.message}")
    """

    pass
