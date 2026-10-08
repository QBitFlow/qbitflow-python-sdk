"""The integration helpers (spec helpers.md H1-H8): the webhook router and its framework adapters,
sign, wait_for_completion, has_access, the amount conversions, the range exports, from_env and
the redirect placeholders. No framework is a dev dependency: the adapters are exercised with
minimal stand-in modules and requests (the interface each adapter uses)."""

from __future__ import annotations

import asyncio
import io
import json
import sys
import time
import types
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator, Dict, List, Tuple
from urllib.parse import parse_qs

import httpx
import pytest

import qbitflow
from qbitflow import (
    PLACEHOLDER_TRANSACTION_TYPE,
    PLACEHOLDER_UUID,
    CheckoutSessionStatusValue,
    Currency,
    EventType,
    NotFoundError,
    PaymentCompleted,
    PaymentCompletedEvent,
    QBitFlow,
    Subscription,
    UnknownEvent,
    ValidationError,
    WebhookResult,
    WebhookRouter,
    WebhookSignatureError,
    format_amount,
    parse_amount,
    webhooks,
)

from .conftest import FIXTURES, TEST_API_KEY, make_client, reply

SECRET = "whsec_router_secret"
PAYMENT = (FIXTURES / "events" / "payment.completed.json").read_text()


def with_type(body: str, event_type: str, **changes: Any) -> str:
    data = json.loads(body)
    data["type"] = event_type
    data.update(changes)
    return json.dumps(data)


def signed(body: str, secret: str = SECRET, **kw: Any) -> Tuple[bytes, str]:
    raw = body.encode()
    return raw, webhooks.sign(raw, secret, **kw)


class Calls:
    """Records the handlers' calls, in order."""

    def __init__(self) -> None:
        self.log: List[Tuple[str, Any]] = []

    def router(self) -> WebhookRouter:
        router = WebhookRouter(SECRET)

        @router.on("payment.completed")
        def on_payment(data: PaymentCompleted, event: PaymentCompletedEvent) -> None:
            self.log.append(("payment", (data, event)))

        @router.on_unknown
        def on_unknown(event: UnknownEvent) -> None:
            self.log.append(("unknown", event))

        @router.on_any
        def first(event: Any) -> None:
            self.log.append(("any1", event))

        @router.on_any
        def second(event: Any) -> None:
            self.log.append(("any2", event))

        return router

    @property
    def names(self) -> List[str]:
        return [name for name, _ in self.log]


# ── H1: the router ───────────────────────────────────────────────────────────


def test_router_valid_delivery_runs_typed_handler_then_on_any() -> None:
    calls = Calls()
    result = calls.router().handle(*signed(PAYMENT))
    assert result.status == 200 and result.error is None
    assert isinstance(result.event, PaymentCompletedEvent)
    assert calls.names == ["payment", "any1", "any2"]
    data, event = calls.log[0][1]
    assert isinstance(data, PaymentCompleted) and data.reference == "order-1042"
    assert event is result.event and calls.log[1][1] is event


def test_router_str_body_and_enum_registration() -> None:
    seen: List[str] = []
    router = WebhookRouter(SECRET)
    router.on(EventType.PAYMENT_COMPLETED)(lambda data, event: seen.append(data.uuid))
    assert router.add("payment.completed", lambda d, e: seen.append("added")) is router
    raw, header = signed(PAYMENT)
    assert router.handle(raw.decode(), header).status == 200
    assert len(seen) == 2 and seen[1] == "added"


def test_router_bad_signature_is_400_and_no_handler_runs() -> None:
    calls = Calls()
    raw, _ = signed(PAYMENT)
    _, other = signed(PAYMENT, secret="whsec_other")
    for header in (other, None, "", "garbage"):
        result = calls.router().handle(raw, header)
        assert result.status == 400 and result.event is None
        assert isinstance(result.error, WebhookSignatureError)
    assert calls.log == []


def test_router_stale_signature_is_400() -> None:
    calls = Calls()
    result = calls.router().handle(*signed(PAYMENT, timestamp=int(time.time()) - 301))
    assert result.status == 400 and isinstance(result.error, WebhookSignatureError)
    assert calls.log == []
    # The tolerance is the router's.
    router = WebhookRouter(SECRET, tolerance=1000)
    assert router.handle(*signed(PAYMENT, timestamp=int(time.time()) - 900)).status == 200


@pytest.mark.parametrize(
    "body",
    ["not json", "[1]", with_type(PAYMENT, "payment.completed", version="v1"), "{}"],
    ids=["not-json", "array", "v1", "no-version"],
)
def test_router_unparsable_body_is_400(body: str) -> None:
    calls = Calls()
    result = calls.router().handle(*signed(body))
    assert result.status == 400 and isinstance(result.error, ValidationError)
    assert calls.log == []


def test_router_data_not_fitting_its_type_is_400() -> None:
    calls = Calls()
    data = json.loads(PAYMENT)["data"]
    data["amount"] = "ten"  # a number on the wire
    result = calls.router().handle(*signed(with_type(PAYMENT, "payment.completed", data=data)))
    assert result.status == 400 and isinstance(result.error, ValidationError)
    assert result.event is None and calls.log == []


def test_router_on_error_gets_every_error() -> None:
    errors: List[Tuple[Any, BaseException]] = []
    router = WebhookRouter(SECRET, on_error=lambda event, exc: errors.append((event, exc)))
    raw, _ = signed(PAYMENT)
    assert router.handle(raw, "t=1,v1=00").status == 400
    assert router.handle(*signed("not json")).status == 400
    assert router.handle(*signed(PAYMENT)).status == 200  # no error: not called
    assert [type(exc) for _, exc in errors] == [WebhookSignatureError, ValidationError]
    assert all(event is None for event, _ in errors)


def test_router_unknown_type_is_200_with_on_unknown_and_on_any() -> None:
    calls = Calls()
    result = calls.router().handle(*signed(with_type(PAYMENT, "brand.new")))
    assert result.status == 200 and isinstance(result.event, UnknownEvent)
    assert calls.names == ["unknown", "any1", "any2"]


def test_router_type_without_handler_is_200() -> None:
    calls = Calls()
    body = (FIXTURES / "events" / "member.removed.json").read_text()
    assert calls.router().handle(*signed(body)).status == 200
    assert calls.names == ["any1", "any2"]
    result = WebhookRouter(SECRET).handle(*signed(body))
    assert result == WebhookResult(200, result.event, None)


def test_router_handler_error_is_500_and_stops_the_rest() -> None:
    log: List[str] = []
    errors: List[Tuple[Any, BaseException]] = []
    router = WebhookRouter(SECRET, on_error=lambda event, exc: errors.append((event, exc)))
    boom = RuntimeError("db down")

    def fail(_data: Any, _event: Any) -> None:
        log.append("fail")
        raise boom

    router.add("payment.completed", fail)
    router.add("payment.completed", lambda d, e: log.append("second"))
    router.on_any(lambda e: log.append("any"))
    result = router.handle(*signed(PAYMENT))
    assert result.status == 500 and result.error is boom
    assert isinstance(result.event, PaymentCompletedEvent)
    assert log == ["fail"]
    assert errors == [(result.event, boom)]

    # An on_any handler failing stops the later on_any handlers.
    log.clear()
    router = WebhookRouter(SECRET)
    router.on_any(lambda e: log.append("a"))
    router.on_any(lambda e: 1 / 0)
    router.on_any(lambda e: log.append("c"))
    result = router.handle(*signed(PAYMENT))
    assert result.status == 500 and isinstance(result.error, ZeroDivisionError)
    assert log == ["a"]


def test_router_registration_checks() -> None:
    with pytest.raises(ValidationError):
        WebhookRouter("")
    with pytest.raises(ValidationError):
        WebhookRouter(SECRET, tolerance="5")  # type: ignore[arg-type]
    router = WebhookRouter(SECRET)
    with pytest.raises(ValidationError, match="type"):
        router.on("payment.complete")  # a typo
    with pytest.raises(ValidationError):
        router.add("payment.completed", "not callable")  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        router.on_any(None)  # type: ignore[type-var]
    with pytest.raises(ValidationError):
        router.on_unknown(3)  # type: ignore[type-var]
    with pytest.raises(ValidationError):
        WebhookRouter(SECRET, on_error="log")  # type: ignore[arg-type]
    assert SECRET not in repr(router)


def test_client_router() -> None:
    client = QBitFlow(TEST_API_KEY)
    router = client.webhooks.router(SECRET, tolerance=60)
    assert isinstance(router, WebhookRouter)
    assert router.handle(*signed(PAYMENT)).status == 200


# ── H1: the adapters ─────────────────────────────────────────────────────────


def fake_module(monkeypatch: pytest.MonkeyPatch, name: str, **attrs: Any) -> types.ModuleType:
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    monkeypatch.setitem(sys.modules, name, module)
    return module


class FakeResponse:
    """Stands for Flask's, Django's and Starlette's response classes."""

    def __init__(self, content: bytes = b"", status: int = 200, **kw: Any) -> None:
        self.content = kw.pop("response", content)
        self.status = kw.pop("status_code", status)
        self.headers: Dict[str, str] = dict(kw.pop("headers", None) or {})
        self.kw = kw

    def __setitem__(self, name: str, value: str) -> None:
        self.headers[name] = value

    def json(self) -> Any:
        return json.loads(self.content)


class BrokenBody(bytes):
    """A body whose reading fails (a client gone mid-request)."""


class BrokenStream(io.BytesIO):
    def read(self, size: Any = -1) -> bytes:
        raise OSError("client disconnected")


def body_stream(body: bytes) -> io.BytesIO:
    return BrokenStream() if isinstance(body, BrokenBody) else io.BytesIO(body)


class FlaskRequest:
    def __init__(self, method: str, headers: Dict[str, str], body: bytes, length: Any) -> None:
        self.method = method
        self.headers = headers
        self.content_length = length
        self.stream = body_stream(body)


class DjangoRequest:
    def __init__(self, method: str, headers: Dict[str, str], body: bytes, length: Any) -> None:
        self.method = method
        self.headers = headers
        self.META = {} if length is None else {"CONTENT_LENGTH": str(length)}
        self.read = body_stream(body).read


class StarletteRequest:
    def __init__(self, method: str, headers: Dict[str, str], body: bytes, length: Any) -> None:
        self.method = method
        self.headers = dict(headers)
        if length is not None:
            self.headers["content-length"] = str(length)
        self._body = body

    async def stream(self) -> AsyncIterator[bytes]:
        if isinstance(self._body, BrokenBody):
            raise OSError("client disconnected")
        for i in range(0, len(self._body), 65536):
            yield self._body[i : i + 65536]


async def run_in_threadpool(fn: Any, *args: Any) -> Any:
    return fn(*args)


def flask_call(monkeypatch: pytest.MonkeyPatch, router: WebhookRouter) -> Any:
    flask = fake_module(monkeypatch, "flask", Response=FakeResponse, request=None)
    view = router.flask_view()
    assert view.methods == ["POST"]  # type: ignore[attr-defined]

    def call(method: str, headers: Dict[str, str], body: bytes, length: Any) -> FakeResponse:
        setattr(flask, "request", FlaskRequest(method, headers, body, length))
        response: FakeResponse = view()
        assert response.kw["content_type"] == "application/json"
        return response

    return call


def django_call(monkeypatch: pytest.MonkeyPatch, router: WebhookRouter) -> Any:
    fake_module(monkeypatch, "django")
    fake_module(monkeypatch, "django.http", HttpResponse=FakeResponse)
    view = router.django_view()
    assert view.csrf_exempt is True  # type: ignore[attr-defined]

    def call(method: str, headers: Dict[str, str], body: bytes, length: Any) -> FakeResponse:
        response: FakeResponse = view(DjangoRequest(method, headers, body, length))
        assert response.kw["content_type"] == "application/json"
        return response

    return call


def starlette_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_module(monkeypatch, "starlette")
    fake_module(monkeypatch, "starlette.responses", Response=FakeResponse)
    fake_module(monkeypatch, "starlette.requests", Request=StarletteRequest)
    fake_module(monkeypatch, "starlette.concurrency", run_in_threadpool=run_in_threadpool)


def asgi_call(monkeypatch: pytest.MonkeyPatch, router: WebhookRouter) -> Any:
    starlette_modules(monkeypatch)

    def call(method: str, headers: Dict[str, str], body: bytes, length: Any) -> FakeResponse:
        request = StarletteRequest(method, headers, body, length)
        response: FakeResponse = asyncio.run(router.handle_asgi(request))
        assert response.kw["media_type"] == "application/json"
        return response

    return call


def fastapi_call(monkeypatch: pytest.MonkeyPatch, router: WebhookRouter) -> Any:
    starlette_modules(monkeypatch)
    endpoint = router.fastapi_endpoint()
    import inspect

    signature = inspect.signature(endpoint)
    assert signature.parameters["request"].annotation is StarletteRequest
    assert signature.return_annotation is FakeResponse

    def call(method: str, headers: Dict[str, str], body: bytes, length: Any) -> FakeResponse:
        response: FakeResponse = asyncio.run(
            endpoint(StarletteRequest(method, headers, body, length))
        )
        return response

    return call


ADAPTERS = {
    "flask": flask_call,
    "django": django_call,
    "asgi": asgi_call,
    "fastapi": fastapi_call,
}


@pytest.fixture(params=sorted(ADAPTERS))
def adapter(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> Any:
    calls = Calls()
    call = ADAPTERS[request.param](monkeypatch, calls.router())
    call.calls = calls
    return call


def test_adapter_valid_delivery(adapter: Any) -> None:
    raw, header = signed(PAYMENT)
    # Any case of the header name.
    for name in ("QBitFlow-Signature", "qbitflow-signature", "QBITFLOW-SIGNATURE"):
        response = adapter("POST", {name: header}, raw, len(raw))
        assert response.status == 200 and response.json() == {"received": True}
    assert adapter.calls.names.count("payment") == 3
    # Without a declared length (chunked) the body is read too.
    assert adapter("post", {"QBitFlow-Signature": header}, raw, None).status == 200


def test_adapter_answers(adapter: Any) -> None:
    raw, header = signed(PAYMENT)
    response = adapter("GET", {"QBitFlow-Signature": header}, raw, len(raw))
    assert response.status == 405 and response.headers["Allow"] == "POST"
    assert response.json() == {"error": "method not allowed"}

    response = adapter("POST", {}, raw, len(raw))
    assert response.status == 400 and response.json() == {"error": "invalid signature"}

    bad, bad_header = signed("not json")
    response = adapter("POST", {"QBitFlow-Signature": bad_header}, bad, len(bad))
    assert response.status == 400 and response.json() == {"error": "invalid event"}
    assert adapter.calls.log == []


def test_adapter_body_limit(adapter: Any) -> None:
    big = b"{" + b" " * webhooks.MAX_BODY_BYTES + b"}"
    header = webhooks.sign(big, SECRET)
    # Declared too large: refused before reading.
    response = adapter("POST", {"QBitFlow-Signature": header}, big, len(big))
    assert response.status == 413 and response.json() == {"error": "body too large"}
    # Undeclared, read past 1 MiB.
    response = adapter("POST", {"QBitFlow-Signature": header}, big, None)
    assert response.status == 413
    # Exactly 1 MiB is read (then refused as not an event, not as too large).
    exact = b"{" + b" " * (webhooks.MAX_BODY_BYTES - 2) + b"}"
    exact_header = webhooks.sign(exact, SECRET)
    response = adapter("POST", {"QBitFlow-Signature": exact_header}, exact, len(exact))
    assert response.status == 400 and response.json() == {"error": "invalid event"}
    assert adapter.calls.log == []


def test_adapter_unreadable_body_is_400(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in sorted(ADAPTERS):
        errors: List[Tuple[Any, BaseException]] = []
        router = WebhookRouter(SECRET, on_error=lambda event, exc: errors.append((event, exc)))
        raw, header = signed(PAYMENT)
        response = ADAPTERS[name](monkeypatch, router)(
            "POST", {"QBitFlow-Signature": header}, BrokenBody(raw), len(raw)
        )
        assert response.status == 400 and response.json() == {"error": "cannot read the body"}
        assert len(errors) == 1 and errors[0][0] is None and isinstance(errors[0][1], OSError)
        # 405 and 413 are not reported.
        call = ADAPTERS[name](monkeypatch, router)
        assert call("GET", {}, raw, len(raw)).status == 405
        assert call("POST", {}, raw, webhooks.MAX_BODY_BYTES + 1).status == 413
        assert len(errors) == 1


def test_adapter_handler_error_is_500_without_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    router = WebhookRouter(SECRET)

    @router.on("payment.completed")
    def fail(_data: Any, _event: Any) -> None:
        raise RuntimeError("secret detail")

    for name in sorted(ADAPTERS):
        raw, header = signed(PAYMENT)
        response = ADAPTERS[name](monkeypatch, router)(
            "POST", {"QBitFlow-Signature": header}, raw, len(raw)
        )
        assert response.status == 500 and response.json() == {"error": "internal error"}
        assert b"secret" not in response.content


@pytest.mark.parametrize(
    "module, make",
    [
        ("flask", lambda r: r.flask_view()),
        ("django.http", lambda r: r.django_view()),
        ("starlette.requests", lambda r: r.fastapi_endpoint()),
        ("starlette.responses", lambda r: asyncio.run(r.handle_asgi(object()))),
    ],
)
def test_adapter_without_its_framework(
    monkeypatch: pytest.MonkeyPatch, module: str, make: Any
) -> None:
    monkeypatch.setitem(sys.modules, module, None)  # makes the import fail
    with pytest.raises(ImportError, match="pip install"):
        make(WebhookRouter(SECRET))


# ── H2: sign ─────────────────────────────────────────────────────────────────

DOCS_BODY = (
    '{"createdAt":"2026-10-01T12:00:00Z","data":{},"id":"evt_3f1c'
    '2d4e-5a6b-5c7d-8e9f-0a1b2c3d4e5f","test":false,"type":"webho'
    'ok.test","version":"v2"}'
)


def test_sign_vector_and_round_trip() -> None:
    expected = "t=1790856000,v1=4a158046f55556e922bdec376a917c3ac338ba575b495f825427541a60bd2f4d"
    assert webhooks.sign(DOCS_BODY, "whsec_new_secret", 1790856000) == expected
    assert webhooks.sign(DOCS_BODY.encode(), "whsec_new_secret", 1790856000.9) == expected
    at = datetime.fromtimestamp(1790856000, timezone.utc)
    assert webhooks.sign(DOCS_BODY, "whsec_new_secret", at) == expected
    assert webhooks.sign(DOCS_BODY, "whsec_new_secret", at.replace(tzinfo=None)) == expected

    header = webhooks.sign(DOCS_BODY, SECRET)
    webhooks.verify(DOCS_BODY, header, SECRET)
    assert webhooks.construct_event(DOCS_BODY, header, SECRET).type == "webhook.test"
    with pytest.raises(WebhookSignatureError):
        webhooks.verify(DOCS_BODY, header, "whsec_other")


def test_sign_checks() -> None:
    with pytest.raises(ValidationError):
        webhooks.sign(DOCS_BODY, "")
    with pytest.raises(ValidationError):
        webhooks.sign(DOCS_BODY, SECRET, -1)
    with pytest.raises(ValidationError):
        webhooks.sign(DOCS_BODY, SECRET, "1790856000")  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        webhooks.sign(DOCS_BODY, SECRET, True)


# ── H3: wait_for_completion ──────────────────────────────────────────────────

STATUS = "pay@019eca82-5680-7b00-8000-0000000000a1"


def status_body(value: str) -> str:
    return json.dumps({"uuid": STATUS, "status": value})


def waiting_client(*statuses: Any) -> Tuple[QBitFlow, Any, List[float]]:
    """A client answering the statuses in order (then the last again), on a fake clock."""

    def handler(_req: httpx.Request, n: int) -> httpx.Response:
        item = statuses[min(n, len(statuses) - 1)]
        return item if isinstance(item, httpx.Response) else reply(200, status_body(item))

    client, server, sleeps = make_client(handler, max_retries=0)
    clock = [1000.0]

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock[0] += seconds

    client._transport.sleep = sleep
    client._transport.monotonic = lambda: clock[0]
    return client, server, sleeps


def test_wait_completes_after_polls() -> None:
    client, server, sleeps = waiting_client(
        "created", "waitingConfirmation", "waitingConfirmation", "completed"
    )
    status = client.checkout_sessions.wait_for_completion(STATUS)
    assert status.status == CheckoutSessionStatusValue.COMPLETED
    assert len(server.requests) == 4 and sleeps == [3.0, 3.0, 3.0]
    assert server.requests[0].path.startswith("/transaction/session-checkout/pay")
    assert server.requests[0].path.endswith("/status")


def test_wait_expired() -> None:
    client, server, sleeps = waiting_client("created", "expired")
    status = client.checkout_sessions.wait_for_completion(STATUS, interval=5)
    assert status.status == CheckoutSessionStatusValue.EXPIRED
    assert len(server.requests) == 2 and sleeps == [5.0]


def test_wait_timeout_returns_last_status() -> None:
    client, server, sleeps = waiting_client("created", "waitingConfirmation")
    status = client.checkout_sessions.wait_for_completion(STATUS, timeout=10, interval=4)
    assert status.status == CheckoutSessionStatusValue.WAITING_CONFIRMATION
    # Polls at 0, 4, 8 and at the deadline (10), never sleeping past it.
    assert sleeps == [4.0, 4.0, 2.0] and len(server.requests) == 4

    # 0 or less means the default: 600 seconds.
    for timeout in (0, -5):
        client, server, sleeps = waiting_client("created")
        status = client.checkout_sessions.wait_for_completion(STATUS, timeout=timeout)
        assert status.status == CheckoutSessionStatusValue.CREATED
        assert sum(sleeps) == 600 and len(server.requests) == 201


def test_wait_interval_floor() -> None:
    client, _, sleeps = waiting_client("created", "created", "completed")
    client.checkout_sessions.wait_for_completion(STATUS, interval=0.01)
    assert sleeps == [1.0, 1.0]
    client, _, sleeps = waiting_client("created", "completed")
    client.checkout_sessions.wait_for_completion(STATUS, interval=0)
    assert sleeps == [1.0]
    client, _, sleeps = waiting_client("created", "completed")
    client.checkout_sessions.wait_for_completion(STATUS, interval=-3)
    assert sleeps == [1.0]


def test_wait_errors_propagate() -> None:
    not_found = reply(404, {"error": "no session", "code": "not_found"})
    client, server, _ = waiting_client("created", not_found)
    with pytest.raises(NotFoundError):
        client.checkout_sessions.wait_for_completion(STATUS)
    assert len(server.requests) == 2
    for kwargs in ({"timeout": "5"}, {"interval": True}, {"timeout": float("nan")}):
        with pytest.raises(ValidationError):
            client.checkout_sessions.wait_for_completion(STATUS, **kwargs)
    with pytest.raises(ValidationError):
        client.checkout_sessions.wait_for_completion("not-a-session")


# ── H4: has_access ───────────────────────────────────────────────────────────


def test_has_access() -> None:
    end = datetime(2026, 10, 31, 12, tzinfo=timezone.utc)
    sub = Subscription.model_validate(
        {"currentPeriodEnd": "2026-10-31T12:00:00Z", "status": "cancelled"}
    )
    assert sub.has_access(end - timedelta(microseconds=1))
    assert not sub.has_access(end)  # equal: no access
    assert not sub.has_access(end + timedelta(seconds=1))
    assert sub.has_access(datetime(2026, 10, 31, 11, 59))  # naive: UTC
    assert sub.has_access(datetime(2026, 10, 31, 13, tzinfo=timezone(timedelta(hours=2))))
    assert not Subscription().has_access(end)  # no period end
    assert not Subscription().has_access()
    future = Subscription(currentPeriodEnd=datetime.now(timezone.utc) + timedelta(days=1))
    assert future.has_access()
    with pytest.raises(ValidationError):
        sub.has_access("2026-10-01")  # type: ignore[arg-type]
    event = qbitflow.webhooks.parse_event(
        (FIXTURES / "events" / "subscription.created.json").read_text()
    )
    assert event.data.has_access(end - timedelta(days=1))  # type: ignore[union-attr]


# ── H5: amounts ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "min_units, decimals, expected",
    [
        ("1500000", 6, "1.5"),
        ("1000000", 6, "1"),
        ("1", 6, "0.000001"),
        ("0", 6, "0"),
        ("-10004200", 6, "-10.0042"),
        ("123", 0, "123"),
        ("000120", 2, "1.2"),
        ("-0", 6, "0"),
        ("-000", 0, "0"),
        ("12345678901234567890123456789", 18, "12345678901.234567890123456789"),
        ("1", 77, "0." + "0" * 76 + "1"),
    ],
)
def test_format_amount(min_units: str, decimals: int, expected: str) -> None:
    assert format_amount(min_units, decimals) == expected


@pytest.mark.parametrize(
    "min_units, decimals",
    [
        ("", 6),
        ("1.5", 6),
        ("+1", 6),
        ("1e6", 6),
        (" 1", 6),
        ("1\n", 6),
        ("١٢", 2),  # non-ASCII digits
        (1500000, 6),
        ("1", -1),
        ("1", 78),
        ("1", True),
        ("1", 6.0),
    ],
)
def test_format_amount_invalid(min_units: Any, decimals: Any) -> None:
    with pytest.raises(ValidationError):
        format_amount(min_units, decimals)


@pytest.mark.parametrize(
    "amount, decimals, expected",
    [
        ("1.5", 6, "1500000"),
        ("0.000001", 6, "1"),
        ("10", 2, "1000"),
        ("-0.5", 2, "-50"),
        ("-0", 2, "0"),
        ("-0.00", 2, "0"),
        ("007.10", 2, "710"),
        ("0", 0, "0"),
        ("1.000000", 6, "1000000"),
        ("12345678901.234567890123456789", 18, "12345678901234567890123456789"),
    ],
)
def test_parse_amount(amount: str, decimals: int, expected: str) -> None:
    assert parse_amount(amount, decimals) == expected
    assert parse_amount(format_amount(expected, decimals), decimals) == expected


@pytest.mark.parametrize(
    "amount, decimals",
    [
        ("1.0000001", 6),
        ("1.50", 1),  # trailing zeros count as decimal places
        ("1.5", 0),
        ("1e3", 2),
        ("1,000", 2),
        ("1.", 2),
        (".5", 2),
        ("+1", 2),
        ("", 2),
        (" 1", 2),
        (1.5, 6),
        ("1", -1),
        ("1", 78),
    ],
)
def test_parse_amount_invalid(amount: Any, decimals: Any) -> None:
    with pytest.raises(ValidationError):
        parse_amount(amount, decimals)


def test_currency_format_amount() -> None:
    usdc = Currency(decimals=6, symbol="USDC")
    assert usdc.format_amount("1500000") == "1.5"
    assert Currency(decimals=18).format_amount("1") == "0." + "0" * 17 + "1"
    with pytest.raises(ValidationError):
        usdc.format_amount("1.5")


# ── H6: range exports ────────────────────────────────────────────────────────


def windows_of(server: Any) -> List[Tuple[str, str]]:
    out = []
    for request in server.requests:
        query = parse_qs(request.query)
        out.append((query["from"][0], query["to"][0]))
    return out


def test_export_json_range_yearly_windows() -> None:
    def handler(req: httpx.Request, n: int) -> httpx.Response:
        return reply(200, [{"paymentUuid": f"pay@{n}", "type": "payment"}])

    client, server, _ = make_client(handler)
    events = client.accounting.export_json_range("2026-01-01", "2026-12-31")
    assert windows_of(server) == [
        ("2026-01-01", "2026-04-06"),
        ("2026-04-07", "2026-07-11"),
        ("2026-07-12", "2026-10-15"),
        ("2026-10-16", "2026-12-31"),
    ]
    assert [e.payment_uuid for e in events] == ["pay@0", "pay@1", "pay@2", "pay@3"]
    assert all("format=json" in r.query for r in server.requests)


def test_export_range_95_and_96_days() -> None:
    from datetime import date

    client, server, _ = make_client(lambda req, n: reply(200, []))
    start = date(2026, 1, 1)
    assert client.accounting.export_json_range(start, start + timedelta(days=95)) == []
    assert windows_of(server) == [("2026-01-01", "2026-04-06")]

    client, server, _ = make_client(lambda req, n: reply(200, []))
    client.accounting.export_json_range(start, start + timedelta(days=96))
    assert windows_of(server) == [("2026-01-01", "2026-04-06"), ("2026-04-07", "2026-04-07")]

    client, server, _ = make_client(lambda req, n: reply(200, []))
    client.accounting.export_json_range("2026-03-03", "2026-03-03")
    assert windows_of(server) == [("2026-03-03", "2026-03-03")]


def test_export_csv_range_dedupes_headers() -> None:
    parts = [
        "date,amount\r\n2026-01-02,1\r\n",
        "date,amount\r\n",  # a window without rows adds nothing
        "date,amount\r\n2026-07-20,3\r\n2026-08-01,4\r\n",
        "date,amount\r\n2026-11-01,5",  # no final line ending: kept as sent
    ]

    def handler(req: httpx.Request, n: int) -> httpx.Response:
        return httpx.Response(200, content=parts[n], headers={"Content-Type": "text/csv"})

    client, server, _ = make_client(handler)
    text = client.accounting.export_csv_range("2026-01-01", "2026-12-31")
    assert text == ("date,amount\r\n2026-01-02,1\r\n2026-07-20,3\r\n2026-08-01,4\r\n2026-11-01,5")
    assert len(server.requests) == 4 and all("format=csv" in r.query for r in server.requests)

    # A first window without a final line ending gets one before the next rows.
    parts[:] = ["h\nr1", "h\nr2\n"]
    client, _, _ = make_client(handler)
    assert client.accounting.export_csv_range("2026-01-01", "2026-05-01") == "h\nr1\nr2\n"


def test_export_range_validation_and_errors() -> None:
    client, server, _ = make_client(lambda req, n: reply(200, []))
    for args in (("2026-12-31", "2026-01-01"), ("2026-1-1", "2026-02-01"), ("", "2026-01-01")):
        with pytest.raises(ValidationError):
            client.accounting.export_json_range(*args)
        with pytest.raises(ValidationError):
            client.accounting.export_csv_range(*args)
    assert server.requests == []

    def handler(req: httpx.Request, n: int) -> httpx.Response:
        if n == 1:
            return reply(404, {"error": "gone", "code": "not_found"})
        return reply(200, [])

    client, server, _ = make_client(handler, max_retries=0)
    with pytest.raises(NotFoundError):
        client.accounting.export_json_range("2026-01-01", "2026-12-31")
    assert len(server.requests) == 2  # stops at the failing window


# ── H7: from_env ─────────────────────────────────────────────────────────────


def test_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    member = "019eca82-5680-7b00-8000-0000000000b1"
    monkeypatch.setenv("QBITFLOW_API_KEY", " sk_env_key ")
    monkeypatch.delenv("QBITFLOW_BASE_URL", raising=False)
    monkeypatch.delenv("QBITFLOW_ON_BEHALF_OF", raising=False)
    client = QBitFlow.from_env()
    assert client._transport.api_key == "sk_env_key"
    assert client._transport.base_url == qbitflow.DEFAULT_BASE_URL
    assert client._on_behalf_of == ""

    monkeypatch.setenv("QBITFLOW_BASE_URL", "https://api.example.test/v2/")
    monkeypatch.setenv("QBITFLOW_ON_BEHALF_OF", member)
    client = QBitFlow.from_env(timeout=5)
    assert client._transport.base_url == "https://api.example.test/v2"
    assert client._on_behalf_of == member and client._transport.timeout == 5

    # Explicit options win over the environment.
    client = QBitFlow.from_env(
        api_key="sk_explicit", base_url="https://other.test", on_behalf_of=""
    )
    assert client._transport.api_key == "sk_explicit"
    assert client._transport.base_url == "https://other.test" and client._on_behalf_of == ""
    assert QBitFlow.from_env(base_url=None)._transport.base_url == qbitflow.DEFAULT_BASE_URL

    monkeypatch.setenv("QBITFLOW_BASE_URL", "")  # empty: unset
    assert QBitFlow.from_env()._transport.base_url == qbitflow.DEFAULT_BASE_URL

    monkeypatch.setenv("QBITFLOW_BASE_URL", "ftp://nope")
    with pytest.raises(ValidationError, match="baseUrl"):
        QBitFlow.from_env()


def test_from_env_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QBITFLOW_API_KEY", raising=False)
    with pytest.raises(ValidationError) as info:
        QBitFlow.from_env()
    assert "QBITFLOW_API_KEY" in str(info.value)
    assert info.value.field_errors[0].field == "QBITFLOW_API_KEY"
    monkeypatch.setenv("QBITFLOW_API_KEY", "  ")
    with pytest.raises(ValidationError, match="QBITFLOW_API_KEY"):
        QBitFlow.from_env()
    assert QBitFlow.from_env(api_key="sk_given")._transport.api_key == "sk_given"


# ── H8: placeholders ─────────────────────────────────────────────────────────


def test_placeholders_sent_literally() -> None:
    assert PLACEHOLDER_UUID == "{{UUID}}"
    assert PLACEHOLDER_TRANSACTION_TYPE == "{{TRANSACTION_TYPE}}"

    session = {"uuid": "pay@x", "link": "https://pay.test/x"}
    client, server, _ = make_client(lambda req, n: reply(201, session))
    client.checkout_sessions.create_payment(
        product_name="Plan",
        price=5,
        success_url=f"https://shop.test/ok?id={PLACEHOLDER_UUID}&t={PLACEHOLDER_TRANSACTION_TYPE}",
    )
    sent = server.requests[0].json()
    assert sent["successUrl"] == "https://shop.test/ok?id={{UUID}}&t={{TRANSACTION_TYPE}}"


def test_exports() -> None:
    for name in (
        "WebhookRouter",
        "WebhookResult",
        "format_amount",
        "parse_amount",
        "PLACEHOLDER_UUID",
        "PLACEHOLDER_TRANSACTION_TYPE",
    ):
        assert name in qbitflow.__all__ and hasattr(qbitflow, name)
    assert {"sign", "WebhookRouter", "WebhookResult"} <= set(webhooks.__all__)
