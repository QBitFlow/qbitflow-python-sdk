"""
Webhooks, usable without a client (a webhook receiver may not hold an API key).

:class:`WebhookRouter` is the usual way in: it verifies a delivery, parses it, runs the handlers
registered for its type and gives the HTTP answer QBitFlow expects; adapters plug it into Flask,
Django or FastAPI/Starlette::

    from qbitflow import Event, PaymentCompleted, webhooks

    router = webhooks.WebhookRouter(os.environ["QBITFLOW_WEBHOOK_SECRET"])

    @router.on("payment.completed")
    def fulfil(data: PaymentCompleted, event: Event) -> None:
        orders.mark_paid(data.reference, event_id=event.id)  # idempotent: dedupe on event.id

    result = router.handle(raw_body, request.headers.get("QBitFlow-Signature"))

The lower level: :func:`verify` checks the ``QBitFlow-Signature`` header
(``t=<unix seconds>,v1=<hex>``, two ``v1`` during a secret rotation) over the **raw body**: never
re-serialize it. :func:`construct_event` verifies, then parses; :func:`parse_event` only parses
(for a body already verified, e.g. by ``client.webhooks.verify_remote``). :func:`sign` builds a
header as QBitFlow does, to test your endpoint.
"""

from __future__ import annotations

import hashlib
import hmac
import importlib
import inspect
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from types import ModuleType
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar, Union

import pydantic

from ._transport import adapter
from .errors import (
    ValidationError,
    WebhookSignatureError,
    WebhookSignatureReason,
    field_error,
    signature_error,
)
from .models.enums import EventType, WebhookPayloadVersion
from .models.events import Event, UnknownEvent

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
    "sign",
    "WebhookRouter",
    "WebhookResult",
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


def sign(
    raw_body: RawBody,
    secret: str,
    timestamp: Union[int, float, datetime, None] = None,
) -> str:
    """A ``QBitFlow-Signature`` header for ``raw_body``, exactly as QBitFlow sends it
    (``t=<unix seconds>,v1=<hex HMAC-SHA256>``): to unit-test your webhook endpoint
    (``verify(body, sign(body, secret), secret)`` passes).

    Args:
        raw_body: The body to sign (bytes, or a str signed as UTF-8).
        secret: The endpoint's ``whsec_…`` secret.
        timestamp: Unix seconds (a float is truncated) or a datetime (naive is taken as UTC);
            default now.

    Raises:
        ValidationError: an empty secret, or a negative or non-numeric timestamp.
    """
    if not isinstance(secret, str) or secret == "":
        raise field_error("secret", "is required (the endpoint's whsec_… secret)")
    body = _body_bytes(raw_body)
    if timestamp is None:
        seconds = int(time.time())
    elif isinstance(timestamp, datetime):
        aware = timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=timezone.utc)
        seconds = int(aware.timestamp())
    elif isinstance(timestamp, (int, float)) and not isinstance(timestamp, bool):
        seconds = int(timestamp)
    else:
        raise field_error("timestamp", "must be unix seconds or a datetime")
    if seconds < 0:
        raise field_error("timestamp", "must not be negative")
    t = str(seconds)
    signature = hmac.new(
        secret.encode("utf-8"), t.encode("ascii") + b"." + body, hashlib.sha256
    ).hexdigest()
    return f"t={t},v1={signature}"


# ── Router ───────────────────────────────────────────────────────────────────

#: A type's handler: ``(data, event)``, ``data`` typed by the event type.
TypeHandler = Callable[[Any, Any], Any]
#: An ``on_any`` / ``on_unknown`` handler: ``(event)``.
EventHandler = Callable[[Any], Any]
#: Called with ``(event, exception)`` when a handler raises.
ErrorHandler = Callable[[Any, BaseException], Any]

_F = TypeVar("_F", bound=Callable[..., Any])
_KNOWN_TYPES = frozenset(t.value for t in EventType)
_JSON = "application/json"
#: An adapter's answer: the status, the JSON body, extra headers.
_Answer = Tuple[int, bytes, Dict[str, str]]


@dataclass(frozen=True)
class WebhookResult:
    """What :meth:`WebhookRouter.handle` did with a delivery.

    Attributes:
        status: The HTTP status to answer: 200 (handled, or ignored: QBitFlow must not retry
            it), 400 (bad signature or not a v2 event: no handler ran) or 500 (a handler
            raised: QBitFlow retries the delivery).
        event: The parsed event (``None`` on a 400).
        error: Why it is not a 200: a :class:`~qbitflow.WebhookSignatureError`, a
            :class:`~qbitflow.ValidationError` or the handler's exception.
    """

    status: int
    event: Optional[Event] = None
    error: Optional[BaseException] = None


def _require(module: str, adapter: str, package: str) -> ModuleType:
    """Import a framework only when its adapter is used (none is a dependency of the SDK)."""
    try:
        return importlib.import_module(module)
    except ImportError as exc:
        raise ImportError(
            f"WebhookRouter.{adapter}() needs {package}: pip install {package.lower()}"
        ) from exc


def _event_type(value: Any) -> str:
    """A known event type's name; a type this SDK does not know (a typo) is refused."""
    name = value.value if isinstance(value, EventType) else value
    if not isinstance(name, str) or name not in _KNOWN_TYPES:
        raise field_error("type", "must be an event type (" + ", ".join(sorted(_KNOWN_TYPES)) + ")")
    return name


def _find_header(headers: Any, name: str) -> Optional[str]:
    """A header's value, its name matched case-insensitively (any mapping with ``items()``)."""
    wanted = name.lower()
    for key, value in headers.items():
        if isinstance(key, str) and key.lower() == wanted:
            return str(value)
    return None


def _declared_length(value: Any) -> Optional[int]:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str) and _DIGITS.fullmatch(value.strip()):
        return int(value)
    return None


def _json_answer(status: int, payload: Dict[str, Any], **headers: str) -> _Answer:
    return status, json.dumps(payload, separators=(",", ":")).encode("utf-8"), dict(headers)


_NOT_POST = _json_answer(405, {"error": "method not allowed"}, Allow="POST")
_TOO_LARGE = _json_answer(413, {"error": "body too large"})


class WebhookRouter:
    """Verify, parse and dispatch webhook deliveries, and answer them.

    Register a handler per event type, then pass each delivery to :meth:`handle` (or plug an
    adapter into your framework: :meth:`flask_view`, :meth:`django_view`,
    :meth:`fastapi_endpoint` / :meth:`handle_asgi`)::

        router = WebhookRouter(os.environ["QBITFLOW_WEBHOOK_SECRET"])

        @router.on("payment.completed")
        def fulfil(data: PaymentCompleted, event: Event) -> None: ...

        @router.on_any
        def audit(event: Event) -> None: ...

    For each delivery: the handlers of its type run (in registration order) with the typed
    ``data`` and the event, then every :meth:`on_any` handler; a type this SDK does not know
    runs the :meth:`on_unknown` handlers instead. A type without a handler is still answered
    200 (QBitFlow must not retry it). A handler that raises stops the rest and makes the
    answer 500, so QBitFlow retries the delivery: **handlers must be idempotent** (deduplicate
    on ``event.id``). Handlers are plain (synchronous) functions.

    Args:
        secret: The endpoint's ``whsec_…`` secret.
        tolerance: Seconds the signature's timestamp may be from now (default 300).
        on_error: Called with ``(event, exception)`` for every delivery answered 400 or 500
            (``event`` is ``None`` when it could not be parsed), to log it: the adapters
            answer without the details. Not called for a 405 or a 413.

    Raises:
        ValidationError: an empty secret.
    """

    def __init__(
        self,
        secret: str,
        *,
        tolerance: float = DEFAULT_TOLERANCE,
        on_error: Optional[ErrorHandler] = None,
    ) -> None:
        if not isinstance(secret, str) or secret == "":
            raise field_error("secret", "is required (the endpoint's whsec_… secret)")
        if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)):
            raise field_error("tolerance", "must be a number of seconds")
        if on_error is not None and not callable(on_error):
            raise field_error("onError", "must be callable")
        self._secret = secret
        self._tolerance = tolerance
        self._on_error = on_error
        self._handlers: Dict[str, List[TypeHandler]] = {}
        self._unknown: List[EventHandler] = []
        self._any: List[EventHandler] = []

    def __repr__(self) -> str:
        return f"WebhookRouter(types={sorted(self._handlers)!r})"  # never the secret

    # ── Registration ──

    def add(self, type: Union[EventType, str], handler: TypeHandler) -> "WebhookRouter":
        """Register ``handler(data, event)`` for an event type; returns the router (chaining).

        Raises:
            ValidationError: a type this SDK does not know (a typo would never be called), or a
                handler that is not callable.
        """
        name = _event_type(type)
        if not callable(handler):
            raise field_error("handler", "must be callable")
        self._handlers.setdefault(name, []).append(handler)
        return self

    def on(self, type: Union[EventType, str]) -> Callable[[_F], _F]:
        """A decorator registering ``fn(data, event)`` for an event type
        (``@router.on("payment.completed")`` or ``@router.on(EventType.PAYMENT_COMPLETED)``)."""
        name = _event_type(type)

        def decorator(fn: _F) -> _F:
            self.add(name, fn)
            return fn

        return decorator

    def on_unknown(self, fn: _F) -> _F:
        """A decorator registering ``fn(event)`` for the types this SDK does not know (an
        :class:`~qbitflow.UnknownEvent`, raw ``data``)."""
        if not callable(fn):
            raise field_error("handler", "must be callable")
        self._unknown.append(fn)
        return fn

    def on_any(self, fn: _F) -> _F:
        """A decorator registering ``fn(event)`` for every event, after its type's handlers."""
        if not callable(fn):
            raise field_error("handler", "must be callable")
        self._any.append(fn)
        return fn

    # ── Handling ──

    def handle(self, raw_body: RawBody, signature_header: Optional[str]) -> WebhookResult:
        """Verify, parse and dispatch one delivery; never raises for a bad delivery.

        Args:
            raw_body: The body exactly as received (bytes, or the str it decodes to).
            signature_header: The ``QBitFlow-Signature`` header (``None`` when missing).

        Returns:
            The status to answer (200, 400 or 500), the event and the error, if any.
        """
        try:
            verify(raw_body, signature_header, self._secret, tolerance=self._tolerance)
            event = parse_event(raw_body)
        except (WebhookSignatureError, ValidationError) as exc:
            return self._failed(WebhookResult(400, None, exc))
        try:
            if isinstance(event, UnknownEvent):
                for on_unknown in self._unknown:
                    on_unknown(event)
            else:
                for handler in self._handlers.get(event.type, ()):
                    handler(event.data, event)
            for on_any in self._any:
                on_any(event)
        except Exception as exc:
            return self._failed(WebhookResult(500, event, exc))
        return WebhookResult(200, event, None)

    def _failed(self, result: WebhookResult) -> WebhookResult:
        """Report a result carrying an error to ``on_error`` (400 and 500, never 405/413)."""
        if self._on_error is not None and result.error is not None:
            self._on_error(result.event, result.error)
        return result

    def _answer(self, headers: Any, body: bytes) -> _Answer:
        result = self.handle(body, _find_header(headers, SIGNATURE_HEADER))
        if result.status == 200:
            return _json_answer(200, {"received": True})
        if result.status == 400:
            bad_signature = isinstance(result.error, WebhookSignatureError)
            return _json_answer(
                400, {"error": "invalid signature" if bad_signature else "invalid event"}
            )
        return _json_answer(500, {"error": "internal error"})

    def _unreadable(self, exc: Exception) -> _Answer:
        """A body that could not be read (a client gone mid-request, a broken stream)."""
        self._failed(WebhookResult(400, None, exc))
        return _json_answer(400, {"error": "cannot read the body"})

    def _serve(
        self, method: str, headers: Any, declared_length: Any, read: Callable[[int], bytes]
    ) -> _Answer:
        """The blocking adapters' flow: POST only, at most 1 MiB read, then :meth:`handle`."""
        if str(method).upper() != "POST":
            return _NOT_POST
        length = _declared_length(declared_length)
        if length is not None and length > MAX_BODY_BYTES:
            return _TOO_LARGE
        try:
            body = read(MAX_BODY_BYTES + 1) or b""
        except Exception as exc:
            return self._unreadable(exc)
        if len(body) > MAX_BODY_BYTES:
            return _TOO_LARGE
        return self._answer(headers, bytes(body))

    # ── Framework adapters (each framework is imported only when its adapter is used) ──

    def flask_view(self) -> Callable[[], Any]:
        """A Flask view (POST only)::

            app.add_url_rule("/webhooks/qbitflow", view_func=router.flask_view())

        It reads the raw body itself: don't read ``request.data``/``request.json`` before it
        (e.g. in a ``before_request`` hook).
        """
        flask = _require("flask", "flask_view", "Flask")

        def qbitflow_webhook() -> Any:
            request = flask.request
            status, body, headers = self._serve(
                request.method, request.headers, request.content_length, request.stream.read
            )
            return flask.Response(body, status=status, headers=headers, content_type=_JSON)

        qbitflow_webhook.methods = ["POST"]  # type: ignore[attr-defined]
        return qbitflow_webhook

    def django_view(self) -> Callable[[Any], Any]:
        """A Django view, CSRF-exempt (QBitFlow signs its deliveries instead)::

        urlpatterns = [path("webhooks/qbitflow", router.django_view())]
        """
        http = _require("django.http", "django_view", "Django")

        def qbitflow_webhook(request: Any) -> Any:
            status, body, headers = self._serve(
                request.method, request.headers, request.META.get("CONTENT_LENGTH"), request.read
            )
            response = http.HttpResponse(body, status=status, content_type=_JSON)
            for name, value in headers.items():
                response[name] = value
            return response

        qbitflow_webhook.csrf_exempt = True  # type: ignore[attr-defined]
        return qbitflow_webhook

    async def handle_asgi(self, request: Any) -> Any:
        """Answer a Starlette/FastAPI ``Request``: returns a Starlette ``Response``. The
        handlers run in Starlette's thread pool (they are synchronous)::

            @app.post("/webhooks/qbitflow")
            async def qbitflow_webhook(request: Request) -> Response:
                return await router.handle_asgi(request)
        """
        responses = _require("starlette.responses", "handle_asgi", "Starlette")
        answer: Optional[_Answer] = None
        if str(request.method).upper() != "POST":
            answer = _NOT_POST
        else:
            length = _declared_length(_find_header(request.headers, "content-length"))
            if length is not None and length > MAX_BODY_BYTES:
                answer = _TOO_LARGE
        if answer is None:
            body = bytearray()
            try:
                async for chunk in request.stream():
                    body += chunk
                    if len(body) > MAX_BODY_BYTES:
                        answer = _TOO_LARGE
                        break
            except Exception as exc:
                answer = self._unreadable(exc)
            if answer is None:
                concurrency = _require("starlette.concurrency", "handle_asgi", "Starlette")
                answer = await concurrency.run_in_threadpool(
                    self._answer, request.headers, bytes(body)
                )
        status, content, headers = answer
        return responses.Response(
            content=content, status_code=status, headers=headers, media_type=_JSON
        )

    def fastapi_endpoint(self) -> Callable[[Any], Any]:
        """A FastAPI (or Starlette) endpoint taking the ``Request``::

        app.add_api_route("/webhooks/qbitflow", router.fastapi_endpoint(), methods=["POST"])
        # Starlette: Route("/webhooks/qbitflow", router.fastapi_endpoint(), methods=["POST"])
        """
        requests = _require("starlette.requests", "fastapi_endpoint", "Starlette")
        responses = _require("starlette.responses", "fastapi_endpoint", "Starlette")

        async def qbitflow_webhook(request: Any) -> Any:
            return await self.handle_asgi(request)

        # FastAPI injects the request from the annotation: give it the real classes.
        qbitflow_webhook.__signature__ = inspect.Signature(  # type: ignore[attr-defined]
            [
                inspect.Parameter(
                    "request", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=requests.Request
                )
            ],
            return_annotation=responses.Response,
        )
        return qbitflow_webhook
