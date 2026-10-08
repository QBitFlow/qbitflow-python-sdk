"""
Base request handler for QBitFlow SDK.

This module provides the base class for all API request handlers with
comprehensive error handling and retry logic.
"""

import time
from typing import Any, Dict, List, Literal, Optional, Tuple
from urllib.parse import quote

import httpx
from pydantic import BaseModel, Field

from qbitflow import config
from qbitflow.exceptions import (
    APIError,
    AuthenticationError,
    FieldError,
    ForbiddenException,
    InvalidRequestError,
    NetworkError,
    NotFoundException,
    RateLimitError,
    ValidationError,
)


class SuccessResponse(BaseModel):
    """
    Standard success response model.

    Attributes:
        message: Success message from the API.
    """

    message: str = Field(..., description="Success message")


class ErrorResponse(BaseModel):
    """
    Standard error response model.

    Attributes:
        error: Error message or code.
    """

    error: str = Field(..., description="Error message or code")


class BaseRequest:
    """
    Base class for all API request handlers.

    This class provides common functionality for making HTTP requests to the
    QBitFlow API, including authentication, error handling, and retries.

    Attributes:
        api_key: API key for authentication.
        headers: HTTP headers to include in requests.
        timeout: Request timeout in seconds.
        max_retries: Maximum number of retry attempts.
    """

    def __init__(
        self,
        api_key: str,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize the request handler.

        Args:
            api_key: API key for authentication.
            timeout: Optional request timeout in seconds (defaults to config.DEFAULT_TIMEOUT).
            max_retries: Optional maximum retry attempts (defaults to config.MAX_RETRIES).
            headers: Optional HTTP headers to include in requests.

        Raises:
            ValueError: If api_key is empty or None.
        """
        if not api_key:
            raise ValueError("API key cannot be empty")

        self.api_key = api_key
        self.timeout = timeout or config.DEFAULT_TIMEOUT
        self.max_retries = max_retries or config.MAX_RETRIES

        self.headers = {"X-API-Key": self.api_key, "Content-Type": "application/json"}

        if headers:
            self.headers.update(headers)

    def on_behalf_of(self, user_id: int):
        """
        Act on behalf of a specific user within the same organization, scoping the
        request to that user's resources. Requires an organization-level admin/owner
        API key.

        Passing ``0`` means "act at the organization level": the header is omitted
        entirely rather than sent as ``0``, which the API rejects with 400.

        Args:
            user_id: ID of the user to act for, or 0 to act at the organization level.

        Returns:
            A new request instance with the On-Behalf-Of header set.
        """
        headers = {"On-Behalf-Of": str(user_id)} if user_id > 0 else {}
        return self.__class__(
            api_key=self.api_key,
            timeout=self.timeout,
            max_retries=self.max_retries,
            headers=headers,
        )

    def _make_request(
        self,
        endpoint: str,
        method: Literal["GET", "POST", "PUT", "DELETE"],
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        retry_count: int = 0,
    ):
        """
        Make an HTTP request to the API with error handling and retries.

        Args:
            endpoint: API endpoint path.
            method: HTTP method to use.
            data: Optional request body data.
            params: Optional query parameters.
            retry_count: Current retry attempt number.

        Returns:
            Parsed JSON response from the API.

        Raises:
            AuthenticationError: If authentication fails (401).
            NotFoundException: If resource is not found (404).
            RateLimitError: If rate limit is exceeded (429).
            NetworkError: If a network error occurs.
            APIError: For other API errors.
            InvalidRequestError: If the request is malformed.
        """
        # Ensure endpoint starts with /
        if not endpoint.startswith("/"):
            endpoint = "/" + endpoint

        url = f"{config.get_base_url()}{endpoint}"

        try:
            with httpx.Client(timeout=self.timeout) as client:
                if method == "GET":
                    response = client.get(url, headers=self.headers, params=params)
                elif method == "POST":
                    if data is None:
                        raise InvalidRequestError("POST requests require data")
                    response = client.post(url, headers=self.headers, json=data)
                elif method == "PUT":
                    if data is None:
                        raise InvalidRequestError("PUT requests require data")
                    response = client.put(url, headers=self.headers, json=data)
                elif method == "DELETE":
                    response = client.delete(url, headers=self.headers)
                else:
                    raise InvalidRequestError(f"Invalid HTTP method: {method}")

            # Handle HTTP errors
            self._handle_http_status(response)

            # Parse and return JSON response
            try:
                return response.json()
            except Exception as e:
                raise APIError(
                    f"Failed to parse JSON response: {str(e)}",
                    status_code=response.status_code,
                    response={"raw": response.text},
                )

        except httpx.TimeoutException as e:
            if retry_count < self.max_retries:
                # Exponential backoff
                wait_time = 2**retry_count
                time.sleep(wait_time)
                return self._make_request(endpoint, method, data, params, retry_count + 1)
            raise NetworkError(f"Request timeout after {self.timeout} seconds: {str(e)}")

        except httpx.NetworkError as e:
            if retry_count < self.max_retries:
                wait_time = 2**retry_count
                time.sleep(wait_time)
                return self._make_request(endpoint, method, data, params, retry_count + 1)
            raise NetworkError(f"Network error: {str(e)}")

        except (
            AuthenticationError,
            NotFoundException,
            RateLimitError,
            APIError,
            InvalidRequestError,
        ):
            # Don't retry these errors
            raise

        except Exception as e:
            raise APIError(f"Unexpected error: {str(e)}")

    def _handle_http_status(self, response: httpx.Response) -> None:
        """
        Handle HTTP response status codes and raise appropriate exceptions.

        Args:
            response: HTTP response object.

        Raises:
            ValidationError: If the request failed validation (400, 422).
            AuthenticationError: If authentication fails (401).
            ForbiddenException: If the key is valid but not permitted (403).
            NotFoundException: If resource is not found (404).
            RateLimitError: If rate limit is exceeded (429).
            InvalidRequestError: For any other 4xx.
            APIError: For other error status codes.
        """
        status_code = response.status_code

        # Success codes
        if 200 <= status_code < 300:
            return

        # Extract the message and any per-field failures from the response
        error_message, fields = self._extract_error(response)

        # Handle specific status codes
        if status_code in (400, 422):
            # The same type the SDK raises for client-side validation, so one `except`
            # covers a field rejected locally and the same field rejected by the API.
            raise ValidationError(
                error_message or "Request failed validation",
                status_code=status_code,
                fields=fields,
            )

        elif status_code == 401:
            raise AuthenticationError(
                error_message or "Authentication failed - check your API key",
                status_code=status_code,
                fields=fields,
            )

        elif status_code == 403:
            # A permissions failure, not a malformed request — most often an admin-level
            # operation (including on_behalf_of) called with a user-level key.
            raise ForbiddenException(
                error_message or "Forbidden - this API key is not permitted",
                status_code=status_code,
                fields=fields,
            )

        elif status_code == 404:
            raise NotFoundException(
                error_message or "Resource not found",
                status_code=status_code,
                fields=fields,
            )

        elif status_code == 429:
            retry_after = response.headers.get("Retry-After")
            response_data = {"retry_after": retry_after} if retry_after else None
            raise RateLimitError(
                error_message or "Rate limit exceeded",
                status_code=status_code,
                response=response_data,
                fields=fields,
            )

        elif 400 <= status_code < 500:
            # Anything else in the 4xx range (405, 409, 415, …). Deliberately *not*
            # mapped to ValidationError: calling a 409 Conflict "validation failed" is
            # misleading, which is a wart the other SDKs still carry.
            raise InvalidRequestError(
                error_message or f"Bad request (status {status_code})",
                status_code=status_code,
                fields=fields,
            )

        else:
            raise APIError(
                error_message or f"API error (status {status_code})",
                status_code=status_code,
                fields=fields,
            )

    def _make_raw_request(
        self,
        endpoint: str,
        method: Literal["GET", "POST", "PUT", "DELETE"],
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        retry_count: int = 0,
    ) -> str:
        """
        Make an HTTP request and return the raw response text.

        Same retry/error logic as _make_request, but returns response.text
        instead of parsing JSON — useful for CSV or other non-JSON responses.
        """
        if not endpoint.startswith("/"):
            endpoint = "/" + endpoint

        url = f"{config.get_base_url()}{endpoint}"

        try:
            with httpx.Client(timeout=self.timeout) as client:
                if method == "GET":
                    response = client.get(url, headers=self.headers, params=params)
                elif method == "POST":
                    if data is None:
                        raise InvalidRequestError("POST requests require data")
                    response = client.post(url, headers=self.headers, json=data)
                elif method == "PUT":
                    if data is None:
                        raise InvalidRequestError("PUT requests require data")
                    response = client.put(url, headers=self.headers, json=data)
                elif method == "DELETE":
                    response = client.delete(url, headers=self.headers)
                else:
                    raise InvalidRequestError(f"Invalid HTTP method: {method}")

            self._handle_http_status(response)
            return response.text

        except httpx.TimeoutException as e:
            if retry_count < self.max_retries:
                wait_time = 2**retry_count
                time.sleep(wait_time)
                return self._make_raw_request(endpoint, method, data, params, retry_count + 1)
            raise NetworkError(f"Request timeout after {self.timeout} seconds: {str(e)}")

        except httpx.NetworkError as e:
            if retry_count < self.max_retries:
                wait_time = 2**retry_count
                time.sleep(wait_time)
                return self._make_raw_request(endpoint, method, data, params, retry_count + 1)
            raise NetworkError(f"Network error: {str(e)}")

        except (
            AuthenticationError,
            NotFoundException,
            RateLimitError,
            APIError,
            InvalidRequestError,
        ):
            raise

        except Exception as e:
            raise APIError(f"Unexpected error: {str(e)}")

    @staticmethod
    def _escape_path(segment: Any) -> str:
        """
        Percent-encode a value for safe interpolation into a URL path segment.

        References, emails and customer identifiers come from the caller's own systems
        and routinely contain characters such as ``/``, ``#`` and ``?`` that would
        otherwise change the shape of the request: a product reference of ``ORD/2026/17``
        interpolated raw addresses a different route entirely, so the lookup either 404s
        or resolves the wrong resource.

        ``safe=""`` escapes ``/`` as well, which is the whole point — the default would
        leave it alone.

        Args:
            segment: The value to interpolate. Numbers are accepted and pass through.

        Returns:
            The percent-encoded segment.
        """
        return quote(str(segment), safe="")

    @staticmethod
    def _extract_field_errors(errors: Any) -> List[FieldError]:
        """
        Extract the field-level failures from the ``errors`` member of an error body.

        The API reports validation failures as a list, one entry per offending field::

            {"errors": [{"field": "Price", "message": "Price is too short"}]}

        Every entry is kept — surfacing only the first hides the rest of what the
        caller has to fix.

        Args:
            errors: The raw ``errors`` member of a decoded error body.

        Returns:
            One entry per reported field failure; empty if there are none.
        """
        if not isinstance(errors, list):
            return []

        extracted: List[FieldError] = []

        for entry in errors:
            if isinstance(entry, dict):
                field = entry.get("field")
                message = entry.get("message")
                field_str = str(field) if isinstance(field, (str, int)) else ""
                message_str = str(message) if isinstance(message, (str, int)) else ""

                if field_str or message_str:
                    extracted.append(FieldError(field=field_str, message=message_str))
            elif entry not in (None, ""):
                extracted.append(FieldError(field="", message=str(entry)))

        return extracted

    def _extract_error(self, response: httpx.Response) -> Tuple[str, List[FieldError]]:
        """
        Extract the message and the field failures from an error response.

        Args:
            response: HTTP response object.

        Returns:
            A ``(message, fields)`` pair. ``fields`` is empty unless the API reported
            per-field validation failures.
        """
        try:
            data = response.json()

            if not isinstance(data, dict):
                return str(data), []

            fields = self._extract_field_errors(data.get("errors"))

            # Single-message envelope, used for everything that is not a validation
            # failure.
            if data.get("error"):
                return str(data["error"]), fields

            # Validation envelope: report every field, not just the first.
            if fields:
                return "; ".join(str(field_error) for field_error in fields), fields

            # `message` is the *success* envelope's key and does not appear on error
            # responses, but honour it in case a gateway synthesises one.
            if data.get("message"):
                return str(data["message"]), fields

            return f"API error (status {response.status_code})", fields

        except Exception:
            return f"API error (status {response.status_code})", []
