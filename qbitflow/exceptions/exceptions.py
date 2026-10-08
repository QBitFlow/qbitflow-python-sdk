"""
Custom exception classes for QBitFlow SDK.

This module defines a hierarchy of exceptions that can be raised during SDK operations.
All exceptions inherit from QBitFlowError for easy catching of all SDK-related errors.
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
    Raised when the API returns an error response.

    This is a general API error that doesn't fit into more specific categories.

    Example:
        >>> try:
        ...     client.products.get(999999)
        ... except APIError as e:
        ...     print(f"API error: {e.message}")
        ...     print(f"Status code: {e.status_code}")
    """

    pass


class AuthenticationError(QBitFlowError):
    """
    Raised when authentication fails.

    This typically indicates an invalid or missing API key.

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

    Covers both sides of the same problem: a value the SDK rejects before sending,
    and a value the API rejects with a 400/422. One ``except`` therefore handles a
    field rejected locally and the same field rejected by the server, and
    ``.fields`` carries the per-field detail when the API supplied it.

    Example:
        >>> try:
        ...     client.one_time_payments.create_session(price=-10)
        ... except ValidationError as e:
        ...     print(f"Validation failed: {e.message}")
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
    Raised when a requested resource is not found.

    This typically occurs when trying to access a resource that doesn't exist
    or has been deleted.

    Example:
        >>> try:
        ...     payment = client.one_time_payments.get("non-existent-uuid")
        ... except NotFoundException:
        ...     print("Payment not found")
    """

    pass


class RateLimitError(QBitFlowError):
    """
    Raised when API rate limit is exceeded.

    This occurs when too many requests are made in a short period.
    The response may include a retry_after field indicating when to retry.

    Example:
        >>> try:
        ...     for i in range(1000):
        ...         client.products.get_all()
        ... except RateLimitError as e:
        ...     print(f"Rate limit exceeded: {e.message}")
        ...     if e.response and 'retry_after' in e.response:
        ...         print(f"Retry after {e.response['retry_after']} seconds")
    """

    pass


class NetworkError(QBitFlowError):
    """
    Raised when a network error occurs during API communication.

    This includes connection timeouts, DNS failures, and other network-related issues.

    Example:
        >>> try:
        ...     payment = client.one_time_payments.get("uuid")
        ... except NetworkError as e:
        ...     print(f"Network error: {e.message}")
    """

    pass


class InvalidRequestError(QBitFlowError):
    """
    Raised for a 4xx that has no more specific type, and for SDK misuse.

    Validation failures (400/422) raise :class:`ValidationError`, permissions
    failures (403) raise :class:`ForbiddenException`; this covers the remainder
    (405, 409, 415, 425, …) plus local misuse such as a POST with no body.

    Example:
        >>> try:
        ...     client.one_time_payments.create_session()  # Missing required params
        ... except InvalidRequestError as e:
        ...     print(f"Invalid request: {e.message}")
    """

    pass
