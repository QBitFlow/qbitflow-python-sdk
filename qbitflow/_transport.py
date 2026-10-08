"""
The HTTP layer: request building, the retry policy, error mapping and response decoding.

Retry policy (the same in every QBitFlow SDK):

* Retried: every GET, and the 7 idempotent creates (they send an ``Idempotency-Key``, generated
  once per call and reused on every retry). Every other write is attempted once.
* Retried on: a network error or timeout, a 5xx, a 429, and (creates only) a 409
  ``idempotency_key_in_use``. Never on another 4xx, a 3xx or an unusable response.
* Attempt ``n`` (0-based) waits ``1 s * 2**n``; a 429 waits at least its ``Retry-After`` (header,
  else ``details.retryAfterSeconds``), and a wait above 60 s is not made: the
  :class:`~qbitflow.RateLimitError` is raised at once.
* Redirects are never followed: a 3xx is a :class:`~qbitflow.ServerError`.
"""

from __future__ import annotations

import json
import math
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Mapping,
    Optional,
    Type,
    TypeVar,
    Union,
    get_origin,
)
from urllib.parse import quote, quote_plus

import httpx
import pydantic
from pydantic import TypeAdapter

from ._version import __version__
from .errors import (
    CODE_IDEMPOTENCY_KEY_IN_USE,
    CODE_IDEMPOTENCY_KEY_REUSED,
    CODE_INVALID_SIGNATURE,
    CODE_VALIDATION_FAILED,
    ApiError,
    AuthenticationError,
    BadRequestError,
    ConflictError,
    FieldError,
    GoneError,
    IdempotencyError,
    NetworkError,
    NotFoundError,
    PermissionDeniedError,
    QBitFlowError,
    RateLimitError,
    ServerError,
    ValidationError,
    WebhookSignatureError,
    WebhookSignatureReason,
    field_error,
    status_message,
    validation_error,
)

T = TypeVar("T")

#: The API root used when ``base_url`` is not given.
DEFAULT_BASE_URL = "https://api.qbitflow.app/v2"
#: Each HTTP attempt's timeout when ``timeout`` is not given, in seconds.
DEFAULT_TIMEOUT = 30.0
#: The number of retries when ``max_retries`` is not given.
DEFAULT_MAX_RETRIES = 3
#: Sent on every request.
USER_AGENT = f"qbitflow-python/{__version__}"

#: Attempt ``n`` (0-based) waits ``RETRY_BASE_DELAY * 2**n`` seconds.
RETRY_BASE_DELAY = 1.0
#: The longest the SDK waits before retrying a 429, in seconds.
MAX_RETRY_WAIT = 60.0
#: Bounds a Retry-After value (about a year: far above what the SDK is willing to wait).
_MAX_RETRY_AFTER_SECONDS = 365 * 24 * 3600


@dataclass(frozen=True)
class RequestOptions:
    """Per-call options, the last argument of every method (``options=``).

    Attributes:
        on_behalf_of: Act in this member's space for this call (a member's ``userUuid``);
            overrides the client's. ``""`` forces the organization level; ``None`` keeps the
            client's.
        idempotency_key: The ``Idempotency-Key`` of one of the 7 idempotent creates (the SDK
            otherwise generates a UUID v4 per call): 1 to 255 printable ASCII characters without
            spaces. Ignored (and not checked) by the other methods.
        request_id: Sent as ``X-Request-Id`` (1 to 128 of ``A-Z a-z 0-9 - _ . :``); the API echoes
            it and errors carry it as ``request_id``.
    """

    on_behalf_of: Optional[str] = None
    idempotency_key: Optional[str] = None
    request_id: Optional[str] = None


@dataclass
class Endpoint:
    """One API call: method, path (escaped with :func:`pathf`), query, JSON body."""

    method: str
    path: str
    query: Optional["Query"] = None
    body: Any = None
    #: The 7 idempotent creates: they send an Idempotency-Key and are retried like reads.
    idempotent: bool = False
    #: Overrides the Accept header (default ``application/json``).
    accept: Optional[str] = None


@dataclass
class Response:
    """One HTTP exchange, its body read in full."""

    status: int
    headers: httpx.Headers
    body: bytes


@dataclass
class Query:
    """A query string under construction: unset values are omitted; booleans are
    ``true``/``false``; times are RFC 3339; keys are sorted when encoded."""

    items: Dict[str, str] = field(default_factory=dict)

    def string(self, key: str, value: Optional[str]) -> "Query":
        """Set ``key`` when ``value`` is a non-empty string."""
        if value is not None and value != "":
            self.items[key] = str(value)
        return self

    def flag(self, key: str, value: Optional[bool]) -> "Query":
        """Set ``key=true`` when ``value`` is true (a flag whose absence means false)."""
        if value:
            self.items[key] = "true"
        return self

    def boolean(self, key: str, value: Optional[bool]) -> "Query":
        """Set ``key`` to ``true``/``false`` when ``value`` is not ``None``."""
        if value is not None:
            self.items[key] = "true" if value else "false"
        return self

    def integer(self, key: str, value: Optional[int]) -> "Query":
        """Set ``key`` when ``value`` is not ``None``."""
        if value is not None:
            self.items[key] = str(int(value))
        return self

    def time(self, key: str, value: Optional[datetime]) -> "Query":
        """Set ``key`` to the RFC 3339 form of ``value`` (an aware datetime)."""
        if value is not None:
            self.items[key] = format_time(value)
        return self

    def page(self, limit: Optional[int], cursor: Optional[str]) -> "Query":
        """A cursor page's limit and cursor."""
        return self.integer("limit", limit).string("cursor", cursor)

    def encode(self) -> str:
        """``key=value&…``, keys sorted, values percent-encoded (``+`` as ``%2B``)."""
        return "&".join(
            f"{quote_plus(k, safe='')}={quote_plus(v, safe='')}"
            for k, v in sorted(self.items.items())
        )


def format_time(value: datetime) -> str:
    """RFC 3339 with the value's offset (``Z`` for UTC) and only the significant fraction."""
    offset = value.utcoffset()
    text = value.strftime("%Y-%m-%dT%H:%M:%S")
    if value.microsecond:
        text += ("." + f"{value.microsecond:06d}").rstrip("0")
    if offset is None or offset.total_seconds() == 0:
        return text + "Z"
    total = int(offset.total_seconds())
    sign = "+" if total >= 0 else "-"
    hours, minutes = divmod(abs(total) // 60, 60)
    return f"{text}{sign}{hours:02d}:{minutes:02d}"


def pathf(template: str, *segments: Union[str, int]) -> str:
    """Format an API path, escaping every segment: a ``/`` inside a reference is sent as ``%2F``,
    never as a path separator; ``.`` and ``..`` segments are escaped too.

    ``pathf("/product/reference/{}", "a/b c")`` → ``/product/reference/a%2Fb%20c``.
    """
    escaped = []
    for segment in segments:
        text = quote(str(segment), safe="$&+,:;=@")
        if text.strip(".") == "":
            text = text.replace(".", "%2E")
        escaped.append(text)
    return template.format(*escaped)


# ── Body encoding ────────────────────────────────────────────────────────────


def _find_invalid_string(value: Any, path: str, depth: int = 0) -> Optional[str]:
    """The wire path of the first string that is not encodable as UTF-8 (a lone surrogate)."""
    if depth > 32:
        return None
    if isinstance(value, str):
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            return path or "body"
        return None
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            try:
                key_text.encode("utf-8")
            except UnicodeEncodeError:
                return path or "body"
            sub = f"{path}.{key_text}" if path else key_text
            found = _find_invalid_string(item, sub, depth + 1)
            if found is not None:
                return found
    elif isinstance(value, (list, tuple)):
        for i, item in enumerate(value):
            found = _find_invalid_string(item, f"{path}[{i}]", depth + 1)
            if found is not None:
                return found
    return None


def encode_body(body: Any) -> bytes:
    """Encode a request body as JSON. A value JSON cannot represent (NaN, ±Inf, a string that is
    not valid UTF-8) is the caller's: a ValidationError, and nothing is sent."""
    bad = _find_invalid_string(body, "")
    if bad is not None:
        raise field_error(bad, "must be valid UTF-8")
    try:
        text = json.dumps(body, allow_nan=False, ensure_ascii=False, separators=(",", ":"))
    except (ValueError, TypeError) as exc:
        raise validation_error("request body cannot be encoded as JSON") from exc
    return text.encode("utf-8")


# ── Errors ───────────────────────────────────────────────────────────────────


def _field_errors(details: Dict[str, Any]) -> List[FieldError]:
    """``details.errors`` (``[{field, message}]``), skipping malformed entries."""
    entries = details.get("errors")
    if not isinstance(entries, list):
        return []
    out = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name = entry.get("field")
        message = entry.get("message")
        name = name if isinstance(name, str) else ""
        message = message if isinstance(message, str) else ""
        if name == "" and message == "":
            continue
        out.append(FieldError(name, message))
    return out


def _detail_int(details: Dict[str, Any], key: str) -> Optional[int]:
    """An integer of ``details`` (a JSON number or a numeric string); ``None`` when absent."""
    value = details.get(key)
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and math.isfinite(value) and 0 <= value < 2**31:
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


_DELTA_SECONDS = re.compile(r"[+-]?[0-9]+")


def _retry_after(headers: httpx.Headers, details: Dict[str, Any], now: datetime) -> Optional[float]:
    """The ``Retry-After`` header (delta-seconds or an HTTP-date), else
    ``details.retryAfterSeconds``, in seconds; ``None`` when neither is usable."""
    value = headers.get("Retry-After", "").strip()
    if value:
        if _DELTA_SECONDS.fullmatch(value):
            seconds = int(value)
            if seconds >= 0:
                return float(min(seconds, _MAX_RETRY_AFTER_SECONDS))
        else:
            try:
                when = parsedate_to_datetime(value)
            except (TypeError, ValueError, IndexError):
                when = None
            if when is not None:
                if when.tzinfo is None:
                    when = when.replace(tzinfo=timezone.utc)
                wait = (when - now).total_seconds()
                return float(math.ceil(wait)) if wait > 0 else 0.0
    detail_seconds = _detail_int(details, "retryAfterSeconds")
    if detail_seconds is not None and detail_seconds > 0:
        return float(min(detail_seconds, _MAX_RETRY_AFTER_SECONDS))
    return None


def parse_error_fields(resp: Response) -> Dict[str, Any]:
    """The common fields of an error answer: each key read on its own so a malformed one never
    hides the others; field errors come from ``details.errors`` only."""
    message, code, details, request_id = "", "", {}, ""
    try:
        data = json.loads(resp.body)
    except (ValueError, UnicodeDecodeError):
        data = None
    if isinstance(data, dict):
        if isinstance(data.get("error"), str):
            message = data["error"]
        if isinstance(data.get("code"), str):
            code = data["code"]
        if isinstance(data.get("details"), dict):
            details = data["details"]
        if isinstance(data.get("requestId"), str):
            request_id = data["requestId"]
    return {
        "message": message or status_message(resp.status),
        "status": resp.status,
        "code": code,
        "details": details,
        "request_id": request_id or resp.headers.get("X-Request-Id", ""),
        "field_errors": _field_errors(details),
        "raw_body": resp.body,
    }


def error_from_response(resp: Response, now: datetime) -> ApiError:
    """Map a non-2xx answer to the SDK's typed error."""
    fields = parse_error_fields(resp)
    status, code = resp.status, fields["code"]
    if status == 400 and code == CODE_VALIDATION_FAILED:
        return ValidationError(**fields)
    if status == 400:
        return BadRequestError(**fields)
    if status == 401:
        return AuthenticationError(**fields)
    if status == 403:
        return PermissionDeniedError(**fields)
    if status == 404:
        return NotFoundError(**fields)
    if status == 409:
        return ConflictError(**fields)
    if status == 410:
        return GoneError(**fields)
    if status == 422 and code == CODE_IDEMPOTENCY_KEY_REUSED:
        return IdempotencyError(**fields)
    if status == 429:
        details = fields["details"]
        return RateLimitError(
            retry_after=_retry_after(resp.headers, details, now),
            limit=_detail_int(details, "limit"),
            period_seconds=_detail_int(details, "periodSeconds"),
            **fields,
        )
    if status >= 500 or status < 200 or 300 <= status < 400:
        return ServerError(**fields)
    return ApiError(**fields)


def as_webhook_signature_error(error: QBitFlowError) -> QBitFlowError:
    """The API's 400 ``invalid_signature`` (``POST /webhooks/verify``) as a
    WebhookSignatureError with reason ``invalidSignature``; any other error unchanged."""
    if isinstance(error, BadRequestError) and error.code == CODE_INVALID_SIGNATURE:
        return WebhookSignatureError(
            error.message,
            reason=WebhookSignatureReason.INVALID_SIGNATURE,
            status=error.status,
            code=error.code,
            details=error.details,
            request_id=error.request_id,
            field_errors=error.field_errors,
            raw_body=error.raw_body,
        )
    return error


def should_retry(error: QBitFlowError, idempotent: bool) -> bool:
    """Whether a failed attempt may be retried: a network error or timeout, a 5xx, a 429, or —
    for the idempotent creates — a 409 ``idempotency_key_in_use``."""
    if isinstance(error, (NetworkError, RateLimitError)):
        return True
    if isinstance(error, ServerError):
        return (error.status or 0) >= 500
    if isinstance(error, ConflictError):
        return idempotent and error.code == CODE_IDEMPOTENCY_KEY_IN_USE
    return False


def retry_delay(error: QBitFlowError, attempt: int) -> Optional[float]:
    """The wait before the retry that follows ``attempt`` (0-based): ``1 s * 2**attempt``, and
    for a 429 at least its Retry-After. ``None`` when a 429's wait exceeds 60 s."""
    delay = RETRY_BASE_DELAY * float(1 << min(attempt, 30))
    if isinstance(error, RateLimitError):
        delay = max(delay, error.retry_after or 0.0)
        if delay > MAX_RETRY_WAIT:
            return None
    return delay


# ── Decoding ─────────────────────────────────────────────────────────────────

_adapters: Dict[Any, TypeAdapter[Any]] = {}


def adapter(tp: Any) -> TypeAdapter[Any]:
    """A cached TypeAdapter for ``tp``."""
    try:
        return _adapters[tp]
    except KeyError:
        built: TypeAdapter[Any] = TypeAdapter(tp)
        _adapters[tp] = built
        return built
    except TypeError:  # pragma: no cover - unhashable type
        return TypeAdapter(tp)


def decode(tp: Type[T], resp: Response) -> T:
    """Decode a 2xx JSON answer: an empty or non-JSON body, or a value of the wrong JSON type, is
    a ServerError carrying the status."""
    if not resp.body.strip():
        raise _server_error("empty response body where JSON was expected", resp)
    try:
        data = json.loads(resp.body)
    except (ValueError, UnicodeDecodeError) as exc:
        raise _server_error("unexpected response body", resp) from exc
    if data is None and get_origin(tp) is list:
        return []  # type: ignore[return-value]
    try:
        return adapter(tp).validate_python(data)  # type: ignore[no-any-return]
    except pydantic.ValidationError as exc:
        raise _server_error(f"unexpected response body: {_pydantic_summary(exc)}", resp) from None


def _server_error(message: str, resp: Response) -> ServerError:
    return ServerError(
        message,
        status=resp.status,
        request_id=resp.headers.get("X-Request-Id", ""),
        raw_body=resp.body,
    )


def _pydantic_summary(exc: pydantic.ValidationError) -> str:
    errors = exc.errors()
    if not errors:
        return ""
    loc = ".".join(str(part) for part in errors[0]["loc"])
    msg = str(errors[0]["msg"]).removeprefix("Value error, ")
    return f"{loc}: {msg}" if loc else msg


# ── Transport ────────────────────────────────────────────────────────────────


class Transport:
    """The configuration a client and its ``on_behalf_of`` copies share."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        timeout: float,
        max_retries: int,
        http_client: Optional[httpx.Client],
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.owns_http = http_client is None
        self.http = http_client if http_client is not None else httpx.Client()
        # Test hooks.
        self.sleep: Callable[[float], None] = time.sleep
        self.monotonic: Callable[[], float] = time.monotonic
        self.now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)
        self.new_key: Callable[[], str] = lambda: str(uuid.uuid4())

    def close(self) -> None:
        """Close the HTTP client, when the SDK created it."""
        if self.owns_http:
            self.http.close()

    def send(self, endpoint: Endpoint, on_behalf_of: str, options: RequestOptions) -> Response:
        """Perform ``endpoint`` with the retry policy. Returns any 2xx response, else raises a
        typed error. ``on_behalf_of`` and ``options`` are already validated."""
        headers = {
            "X-API-Key": self.api_key,
            "User-Agent": USER_AGENT,
            "Accept": endpoint.accept or "application/json",
        }
        if on_behalf_of:
            headers["On-Behalf-Of"] = on_behalf_of
        if options.request_id:
            headers["X-Request-Id"] = options.request_id
        if endpoint.idempotent:
            # One key per call, reused by every retry.
            headers["Idempotency-Key"] = options.idempotency_key or self.new_key()

        payload: Optional[bytes] = None
        if endpoint.body is not None:
            payload = encode_body(endpoint.body)
            headers["Content-Type"] = "application/json"

        url = self.base_url + endpoint.path
        if endpoint.query is not None and endpoint.query.items:
            url += "?" + endpoint.query.encode()

        max_retries = self.max_retries if endpoint.method == "GET" or endpoint.idempotent else 0
        attempt = 0
        while True:
            error: QBitFlowError
            try:
                resp = self._round_trip(endpoint.method, url, payload, headers)
            except NetworkError as exc:
                error = exc
            else:
                if 200 <= resp.status < 300:
                    return resp
                error = error_from_response(resp, self.now())

            if attempt >= max_retries or not should_retry(error, endpoint.idempotent):
                raise error
            delay = retry_delay(error, attempt)
            if delay is None:
                raise error
            self.sleep(delay)
            attempt += 1

    def _round_trip(
        self, method: str, url: str, payload: Optional[bytes], headers: Dict[str, str]
    ) -> Response:
        """One HTTP attempt, bounded by the per-attempt timeout; redirects are not followed."""
        try:
            res = self.http.request(
                method,
                url,
                content=payload,
                headers=headers,
                timeout=self.timeout,
                follow_redirects=False,
            )
        except httpx.TimeoutException as exc:
            raise NetworkError(f"request timed out after {self.timeout:g}s") from exc
        except httpx.HTTPError as exc:
            raise NetworkError("request failed") from exc
        return Response(status=res.status_code, headers=res.headers, body=res.content)


def split_options(options: Optional[RequestOptions]) -> RequestOptions:
    """``options`` or the defaults; a value of another type is a ValidationError."""
    if options is None:
        return RequestOptions()
    if not isinstance(options, RequestOptions):
        raise field_error("options", "must be a qbitflow.RequestOptions")
    return options
