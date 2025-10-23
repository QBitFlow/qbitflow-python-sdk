
"""
Custom exception classes for QBitFlow SDK.

This module defines a hierarchy of exceptions that can be raised during SDK operations.
All exceptions inherit from QBitFlowError for easy catching of all SDK-related errors.
"""

from typing import Optional, Dict, Any


class QBitFlowError(Exception):
    """
    Base exception class for all QBitFlow SDK errors.
    
    All exceptions raised by the SDK inherit from this class, making it easy
    to catch all SDK-related errors with a single except clause.
    
    Attributes:
        message: Human-readable error message.
        status_code: HTTP status code if applicable.
        response: Raw response data if available.
    """
    
    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the exception.
        
        Args:
            message: Human-readable error message.
            status_code: HTTP status code if applicable.
            response: Raw response data if available.
        """
        self.message = message
        self.status_code = status_code
        self.response = response
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
    
    This occurs when provided parameters don't meet the required criteria.
    
    Example:
        >>> try:
        ...     client.one_time_payments.create_session(price=-10)
        ... except ValidationError as e:
        ...     print(f"Validation failed: {e.message}")
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
    Raised when the request is malformed or contains invalid parameters.
    
    This typically indicates a bug in the SDK or incorrect usage.
    
    Example:
        >>> try:
        ...     client.one_time_payments.create_session()  # Missing required params
        ... except InvalidRequestError as e:
        ...     print(f"Invalid request: {e.message}")
    """
    pass
