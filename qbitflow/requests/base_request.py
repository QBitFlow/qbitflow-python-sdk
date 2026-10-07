"""
Base request handler for QBitFlow SDK.

This module provides the base class for all API request handlers: URL building,
authentication, the retry policy, HTTP-status → exception mapping and response hydration.

Retry policy (identical across every QBitFlow SDK)
--------------------------------------------------
* Only idempotent requests are retried: HTTP ``GET``. ``POST``, ``PUT`` and ``DELETE`` are
  never retried, so a timed-out session creation is never silently sent twice.
* Three ``GET`` routes are actions, not reads, and are explicitly non-retriable:
  ``force-cancel`` and ``execute-billing`` on subscriptions, and the claim-funds
  ``test-trigger``.
* A retry is triggered by any transport failure (connection, read/write, timeout, protocol
  error such as "server disconnected") or any ``5xx`` response. A ``4xx``, a ``429`` or a
  ``3xx`` is never retried, and neither is a configuration error (an unsupported URL scheme).
* Backoff is exponential: 1s, 2s, 4s (``1 * 2**attempt``). ``max_retries`` defaults to 3;
  ``max_retries=0`` disables retries.
"""

import json
import math
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Literal, Mapping, Optional, Tuple, Type, TypeVar
from urllib.parse import quote

import httpx
import pydantic
from pydantic import Field

from qbitflow import config
from qbitflow._version import __version__
from qbitflow.dto.base_model import RequestModel, ResponseModel, Str
from qbitflow.exceptions import (
    AuthenticationError,
    ConflictError,
    FieldError,
    ForbiddenException,
    InvalidRequestError,
    NetworkError,
    NotFoundException,
    QBitFlowError,
    RateLimitError,
    ServerError,
    ValidationError,
)
from qbitflow.utils.helpers import is_valid_email

HttpMethod = Literal["GET", "POST", "PUT", "DELETE"]

ModelT = TypeVar("ModelT", bound=pydantic.BaseModel)
RequestT = TypeVar("RequestT", bound=RequestModel)
HandlerT = TypeVar("HandlerT", bound="BaseRequest")

#: ``User-Agent`` sent with every request, e.g. ``qbitflow-python/2.5.0``.
USER_AGENT = f"qbitflow-python/{__version__}"

#: Base of the exponential backoff, in seconds: the n-th retry waits ``BACKOFF_BASE * 2**n``.
BACKOFF_BASE_SECONDS = 1.0

# Indirection so tests can stub the wait without touching ``time.sleep`` globally.
_sleep = time.sleep


class SuccessResponse(ResponseModel):
    """
    Standard success response model (the API's ``JSONMessage``).

    Attributes:
        message: Success message from the API.
    """

    message: Str = Field(default="", description="Success message")


class ErrorResponse(ResponseModel):
    """
    Standard error response model.

    Attributes:
        error: Error message or code.
    """

    error: Str = Field(default="", description="Error message or code")


def validate_api_key(api_key: Any) -> str:
    """Reject a missing, non-string, empty or whitespace-only API key."""
    if not isinstance(api_key, str) or not api_key.strip():
        raise ValueError("API key is required and cannot be blank")
    return api_key


def validate_timeout(timeout: Any) -> Optional[float]:
    """``None`` (the default) or a finite, non-negative number of seconds (``0`` = no timeout)."""
    if timeout is None:
        return None
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
        raise ValidationError("timeout must be a number of seconds")
    if not math.isfinite(timeout) or timeout < 0:
        raise ValidationError("timeout must be zero or positive")
    return timeout


def validate_max_retries(max_retries: Any) -> Optional[int]:
    """``None`` (the default) or a non-negative integer (``0`` disables retries)."""
    if max_retries is None:
        return None
    if isinstance(max_retries, bool) or not isinstance(max_retries, int):
        raise ValidationError("max_retries must be an integer")
    if max_retries < 0:
        raise ValidationError("max_retries must be zero or positive")
    return max_retries


def on_behalf_of_headers(user_id: Any) -> Dict[str, str]:
    """
    The ``On-Behalf-Of`` header for ``user_id``: none for ``0`` (organization level).

    Raises:
        ValidationError: If ``user_id`` is not a non-negative integer (booleans, floats and
            strings are rejected).
    """
    if isinstance(user_id, bool) or not isinstance(user_id, int):
        raise ValidationError("user_id must be a non-negative integer")
    if user_id < 0:
        raise ValidationError("user_id must be zero or positive")
    return {"On-Behalf-Of": str(user_id)} if user_id > 0 else {}


class BaseRequest:
    """
    Base class for all API request handlers.

    This class provides common functionality for making HTTP requests to the
    QBitFlow API, including authentication, error handling, and retries.

    Attributes:
        api_key: API key for authentication.
        headers: HTTP headers to include in requests.
        timeout: Request timeout in seconds.
        max_retries: Maximum number of retry attempts for idempotent requests.
        base_url: Base URL this handler sends to, or ``None`` to follow
            :func:`qbitflow.config.get_base_url` at request time.
    """

    def __init__(
        self,
        api_key: str,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
        headers: Optional[Dict[str, str]] = None,
        base_url: Optional[str] = None,
        http_client: Optional[httpx.Client] = None,
    ):
        """
        Initialize the request handler.

        Args:
            api_key: API key for authentication.
            timeout: Optional request timeout in seconds (defaults to config.DEFAULT_TIMEOUT).
                An explicit ``0`` is honoured and means "no timeout".
            max_retries: Optional maximum retry attempts for idempotent requests (defaults
                to config.MAX_RETRIES). An explicit ``0`` disables retries.
            headers: Optional HTTP headers to include in requests.
            base_url: Optional base URL. When omitted, the module-level configuration
                (``QBITFLOW_BASE_URL`` / ``config.set_base_url``) is consulted on every
                request. A trailing slash is stripped.
            http_client: Optional shared ``httpx.Client``. When given it is reused and never
                closed by this handler; otherwise the handler owns its own client.

        Raises:
            ValueError: If api_key is empty, blank or not a string.
            ValidationError: If ``max_retries`` or ``timeout`` is negative or not a number.
        """
        validate_api_key(api_key)
        timeout = validate_timeout(timeout)
        max_retries = validate_max_retries(max_retries)

        self.api_key = api_key
        self.timeout: float = config.DEFAULT_TIMEOUT if timeout is None else timeout
        self.max_retries: int = config.MAX_RETRIES if max_retries is None else max_retries
        self.base_url: Optional[str] = self._normalise_base_url(base_url)

        self.headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        }

        if headers:
            self.headers.update(headers)

        self._owns_client = http_client is None
        # ``timeout=0`` means "no timeout" to httpx, which is what an explicit zero asks for.
        self._client = http_client or httpx.Client(timeout=self.timeout or None)

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def close(self) -> None:
        """Close the underlying HTTP client if this handler owns it."""
        if self._owns_client:
            self._client.close()

    def __enter__(self: HandlerT) -> HandlerT:
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()

    # ── Scoping ──────────────────────────────────────────────────────────────

    def on_behalf_of(self: HandlerT, user_id: int) -> HandlerT:
        """
        Act on behalf of a specific user within the same organization, scoping the
        request to that user's resources. Requires an organization-level admin/owner
        API key.

        Passing ``0`` means "act at the organization level": the header is omitted
        entirely rather than sent as ``0``.

        Args:
            user_id: ID of the user to act for, or 0 to act at the organization level.

        Returns:
            A new handler of the same type with the On-Behalf-Of header set. It shares this
            handler's HTTP connection pool; closing the copy is a no-op.

        Raises:
            ValidationError: If ``user_id`` is not a non-negative integer.
        """
        headers = on_behalf_of_headers(user_id)
        return self.__class__(
            api_key=self.api_key,
            timeout=self.timeout,
            max_retries=self.max_retries,
            headers=headers,
            base_url=self.base_url,
            http_client=self._client,
        )

    # ── URL helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _normalise_base_url(base_url: Optional[str]) -> Optional[str]:
        """Strip surrounding whitespace and any trailing slashes; ``None`` stays ``None``."""
        if base_url is None:
            return None
        if not isinstance(base_url, str):
            raise ValidationError("base_url must be a string")
        normalised = base_url.strip().rstrip("/")
        if not normalised:
            raise ValidationError("base_url cannot be empty")
        return normalised

    def _effective_base_url(self) -> str:
        """The base URL for the next request: the handler's own, else the module setting."""
        if self.base_url is not None:
            return self.base_url
        return config.get_base_url().strip().rstrip("/")

    def _build_url(self, endpoint: str) -> str:
        if not endpoint.startswith("/"):
            endpoint = "/" + endpoint
        return f"{self._effective_base_url()}{endpoint}"

    @staticmethod
    def _escape_path(segment: Any) -> str:
        """
        Percent-encode a value for safe interpolation into a URL path segment.

        References, emails and customer identifiers come from the caller's own systems
        and routinely contain characters such as ``/``, ``#`` and ``?`` that would
        otherwise change the shape of the request: a reference such as ``ORD?x=1``
        interpolated raw would send ``x=1`` as a query parameter.

        ``safe=""`` escapes ``/`` as well. Note that the API currently cannot route a
        reference containing ``/`` even when it is escaped (it answers 404).

        Args:
            segment: The value to interpolate. Numbers are accepted and pass through.

        Returns:
            The percent-encoded segment.
        """
        return quote(str(segment), safe="")

    # ── Argument guards (one wording across the SDK) ─────────────────────────

    @staticmethod
    def _require_identifier(value: Any, name: str) -> str:
        """Reject an empty/blank identifier (uuid, reference, ...) before any request."""
        if not isinstance(value, str) or not value.strip():
            raise ValidationError(f"{name} cannot be empty")
        return value

    @staticmethod
    def _require_positive_id(value: Any, name: str) -> int:
        """Reject a non-positive numeric identifier before any request."""
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValidationError(f"{name} must be a positive integer")
        return value

    @staticmethod
    def _require_email(value: Any, name: str = "email") -> str:
        """Reject a malformed email address before any request."""
        if not isinstance(value, str) or not is_valid_email(value):
            raise ValidationError(f"{name} is not a valid email address")
        return value

    @staticmethod
    def _body(model: Type[RequestT], data: Any) -> Dict[str, Any]:
        """
        Validate a request DTO (or a plain mapping of its fields) and build the JSON body.

        The DTO is validated again here, so a value assigned after construction is still
        checked; a failure raises the SDK's :class:`ValidationError`.
        """
        if isinstance(data, model):
            instance = model.model_validate(data)
        elif isinstance(data, Mapping):
            instance = model.model_validate(dict(data))
        else:
            raise ValidationError(
                f"expected a {model.__name__} (or a mapping of its fields), "
                f"got {type(data).__name__}"
            )
        return instance.to_body()

    # ── Response hydration ───────────────────────────────────────────────────

    @staticmethod
    def _hydrate(model: Type[ModelT], data: Any, status_code: Optional[int] = None) -> ModelT:
        """
        Build a response model, reporting a mismatch as :class:`ServerError`.

        A response the SDK cannot decode is a server-side problem (or a documented shape the
        SDK has not caught up with), never a caller error — so it surfaces as the same type
        as a 5xx rather than as a bare pydantic exception outside the SDK's hierarchy. The
        HTTP status is kept on the error and the original pydantic error is attached as
        ``__cause__``.
        """
        if not isinstance(data, dict):
            raise ServerError(
                f"API response did not match the expected {model.__name__} shape: a JSON "
                f"object was expected, got {type(data).__name__}",
                status_code=status_code,
                response={"raw": data},
            )
        try:
            return model.model_validate(data)
        except pydantic.ValidationError as exc:
            details = "; ".join(
                f"{'.'.join(str(p) for p in err.get('loc', ()))}: {err.get('msg', '')}"
                for err in exc.errors()[:5]
            )
            raise ServerError(
                f"API response did not match the expected {model.__name__} shape: "
                f"{exc.error_count()} field(s) could not be decoded ({details})",
                status_code=status_code,
                response={"raw": data},
            ) from exc

    @classmethod
    def _hydrate_list(
        cls, model: Type[ModelT], data: Any, status_code: Optional[int] = None
    ) -> List[ModelT]:
        """
        Hydrate a JSON array into a list of models (see :meth:`_hydrate`).

        ``null`` is an empty list: the API is written in Go, where an empty slice can be
        serialized as ``null``.
        """
        if data is None:
            return []
        if not isinstance(data, list):
            raise ServerError(
                f"API response did not match the expected shape: a list of "
                f"{model.__name__} was expected, got {type(data).__name__}",
                status_code=status_code,
                response={"raw": data},
            )
        return [cls._hydrate(model, item, status_code) for item in data]

    @staticmethod
    def _decode_json(response: httpx.Response) -> Any:
        """
        Decode a 2xx JSON body. ``204 No Content`` decodes to ``None``; an empty or non-JSON
        body is a :class:`ServerError` carrying the status code.
        """
        if response.status_code == 204:
            return None
        if not response.content.strip():
            raise ServerError(
                f"API returned an empty body with status {response.status_code}",
                status_code=response.status_code,
            )
        try:
            return response.json()
        except ValueError as exc:
            raise ServerError(
                f"API returned a non-JSON body with status {response.status_code}",
                status_code=response.status_code,
                response={"raw": response.text},
            ) from exc

    # ── Requests ─────────────────────────────────────────────────────────────

    def _make_request(
        self,
        endpoint: str,
        method: HttpMethod,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        *,
        retriable: Optional[bool] = None,
    ) -> Any:
        """
        Make an HTTP request to the API and return the decoded JSON body.

        Args:
            endpoint: API endpoint path.
            method: HTTP method to use.
            data: Optional request body data.
            params: Optional query parameters.
            retriable: Override the retry policy for this call. Defaults to "retry if the
                method is GET". Pass ``False`` for a GET that performs an action.

        Returns:
            Parsed JSON response from the API (``None`` for a 204).

        Raises:
            ValidationError: The API rejected the request (400/422), or the body could not
                be encoded as JSON.
            AuthenticationError: If authentication fails (401).
            ForbiddenException: The key is valid but not permitted (403).
            NotFoundException: If the resource is not found (404).
            ConflictError: The request conflicts with the resource's state (409).
            RateLimitError: If the rate limit is exceeded (429).
            InvalidRequestError: Any other 4xx, or SDK misuse.
            ServerError: A 5xx, an unexpected redirect, or an empty / non-JSON 2xx body.
            NetworkError: If a transport error persists after the retry budget.
        """
        response = self._send(endpoint, method, data, params, retriable=retriable)
        return self._decode_json(response)

    def _make_raw_request(
        self,
        endpoint: str,
        method: HttpMethod,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        *,
        retriable: Optional[bool] = None,
    ) -> str:
        """
        Make an HTTP request and return the raw response text.

        Same retry/error logic as :meth:`_make_request` — an error response's JSON body is
        still parsed into the typed exception — but a 2xx body is returned as text instead of
        being decoded; used for the CSV accounting export.
        """
        return self._send(endpoint, method, data, params, retriable=retriable).text

    def _request_model(
        self,
        model: Type[ModelT],
        endpoint: str,
        method: HttpMethod = "GET",
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        *,
        retriable: Optional[bool] = None,
    ) -> ModelT:
        """Send a request and hydrate its JSON object body into ``model``."""
        response = self._send(endpoint, method, data, params, retriable=retriable)
        if response.status_code == 204:
            return model()
        return self._hydrate(model, self._decode_json(response), response.status_code)

    def _request_list(
        self,
        model: Type[ModelT],
        endpoint: str,
        method: HttpMethod = "GET",
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        *,
        retriable: Optional[bool] = None,
    ) -> List[ModelT]:
        """Send a request and hydrate its JSON array body into a list of ``model``."""
        response = self._send(endpoint, method, data, params, retriable=retriable)
        return self._hydrate_list(model, self._decode_json(response), response.status_code)

    @staticmethod
    def _encode_body(data: Any) -> bytes:
        """Encode a request body as compact UTF-8 JSON; an unencodable value is a caller error."""
        try:
            return json.dumps(
                data, ensure_ascii=False, separators=(",", ":"), allow_nan=False
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            # ValueError covers NaN/Infinity (allow_nan=False) and UnicodeEncodeError (a lone
            # surrogate, i.e. a string that is not valid UTF-8).
            raise ValidationError(f"request body cannot be encoded as JSON: {exc}") from exc

    def _send(
        self,
        endpoint: str,
        method: HttpMethod,
        data: Optional[Dict[str, Any]],
        params: Optional[Dict[str, Any]],
        *,
        retriable: Optional[bool],
    ) -> httpx.Response:
        """Issue the request, applying the retry policy, and return a 2xx response."""
        if method not in ("GET", "POST", "PUT", "DELETE"):
            raise InvalidRequestError(f"Invalid HTTP method: {method}")
        if method in ("POST", "PUT") and data is None:
            raise InvalidRequestError(f"{method} requests require data")

        content = self._encode_body(data) if method in ("POST", "PUT") else None
        url = self._build_url(endpoint)
        can_retry = method == "GET" if retriable is None else retriable
        attempts = self.max_retries + 1 if can_retry else 1

        for attempt in range(attempts):
            is_last = attempt == attempts - 1
            try:
                response = self._client.request(
                    method,
                    url,
                    headers=self.headers,
                    params=params or None,
                    content=content,
                )
            except httpx.UnsupportedProtocol as exc:
                # A configuration error (e.g. a base_url without http:// or https://): retrying
                # cannot help.
                raise NetworkError(f"Invalid request URL {url!r} - check base_url: {exc}") from exc
            except httpx.TransportError as exc:
                if is_last:
                    if isinstance(exc, httpx.TimeoutException):
                        raise NetworkError(
                            f"Request timeout after {self.timeout} seconds: {exc}"
                        ) from exc
                    raise NetworkError(f"Network error: {exc}") from exc
                _sleep(BACKOFF_BASE_SECONDS * 2**attempt)
                continue
            except httpx.InvalidURL as exc:
                raise NetworkError(f"Invalid request URL {url!r} - check base_url: {exc}") from exc
            except QBitFlowError:
                raise
            except Exception as exc:  # pragma: no cover - defensive
                raise NetworkError(f"Unexpected transport error: {exc}") from exc

            if 500 <= response.status_code < 600 and not is_last:
                _sleep(BACKOFF_BASE_SECONDS * 2**attempt)
                continue

            self._handle_http_status(response)
            return response

        raise AssertionError("unreachable: the retry loop always returns or raises")

    # ── Status mapping ───────────────────────────────────────────────────────

    def _handle_http_status(self, response: httpx.Response) -> None:
        """
        Handle HTTP response status codes and raise the matching exception.

        Args:
            response: HTTP response object.

        Raises:
            ValidationError: If the request failed validation (400, 422).
            AuthenticationError: If authentication fails (401).
            ForbiddenException: If the key is valid but not permitted (403).
            NotFoundException: If the resource is not found (404).
            ConflictError: If the request conflicts with the resource's state (409).
            RateLimitError: If the rate limit is exceeded (429).
            InvalidRequestError: For any other 4xx.
            ServerError: For 5xx, and for 3xx (a redirect means a misconfigured base URL).
        """
        status_code = response.status_code

        # Success codes
        if 200 <= status_code < 300:
            return

        # Extract the message and any per-field failures from the response
        error_message, fields = self._extract_error(response)

        if status_code in (400, 422):
            # The same type the SDK raises for client-side validation, so one `except`
            # covers a field rejected locally and the same field rejected by the API.
            raise ValidationError(error_message, status_code=status_code, fields=fields)

        if status_code == 401:
            raise AuthenticationError(error_message, status_code=status_code, fields=fields)

        if status_code == 403:
            # A permissions failure, not a malformed request — most often an admin-level
            # operation (including on_behalf_of) called with a user-level key.
            raise ForbiddenException(error_message, status_code=status_code, fields=fields)

        if status_code == 404:
            raise NotFoundException(error_message, status_code=status_code, fields=fields)

        if status_code == 409:
            raise ConflictError(error_message, status_code=status_code, fields=fields)

        if status_code == 429:
            retry_after = self._parse_retry_after(response.headers.get("Retry-After"))
            response_data = {"retry_after": retry_after} if retry_after is not None else None
            raise RateLimitError(
                error_message,
                status_code=status_code,
                response=response_data,
                fields=fields,
                retry_after=retry_after,
            )

        if 400 <= status_code < 500:
            # Anything else in the 4xx range (405, 415, 425, …).
            raise InvalidRequestError(error_message, status_code=status_code, fields=fields)

        if 300 <= status_code < 400:
            location = response.headers.get("Location")
            where = f" to {location}" if location else ""
            raise ServerError(
                f"Unexpected redirect ({status_code}){where} - check the configured base_url: "
                f"{error_message}",
                status_code=status_code,
                fields=fields,
            )

        raise ServerError(error_message, status_code=status_code, fields=fields)

    @staticmethod
    def _parse_retry_after(value: Optional[str], now: Optional[datetime] = None) -> Optional[int]:
        """
        ``Retry-After`` as whole seconds, or ``None`` when absent or unparseable.

        Both forms are accepted: delta-seconds (``"120"``) and an HTTP-date
        (``"Wed, 21 Oct 2026 07:28:00 GMT"``), which becomes the seconds from now, floored at 0.
        """
        if value is None:
            return None
        value = value.strip()
        if not value:
            return None
        if value.isascii() and value.isdigit():
            return int(value)
        try:
            when = parsedate_to_datetime(value)
        except (TypeError, ValueError, IndexError):
            return None
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        current = now or datetime.now(timezone.utc)
        return max(0, int((when - current).total_seconds()))

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

        Precedence: ``error`` → joined ``errors[]`` → ``message`` → the raw non-JSON body →
        the HTTP status text.

        Args:
            response: HTTP response object.

        Returns:
            A ``(message, fields)`` pair. ``fields`` is empty unless the API reported
            per-field validation failures.
        """
        fallback = response.reason_phrase or f"HTTP {response.status_code}"

        try:
            data = response.json()
        except ValueError:
            body = response.text.strip()
            return (body[:500] if body else fallback), []

        if not isinstance(data, dict):
            return (str(data) if data not in (None, "", []) else fallback), []

        fields = self._extract_field_errors(data.get("errors"))

        # Single-message envelope, used for everything that is not a validation failure.
        if data.get("error"):
            return str(data["error"]), fields

        # Validation envelope: report every field, not just the first.
        if fields:
            return "; ".join(str(field_error) for field_error in fields), fields

        # `message` is the *success* envelope's key and does not appear on error
        # responses, but honour it in case a gateway synthesises one.
        if data.get("message"):
            return str(data["message"]), fields

        return fallback, fields
