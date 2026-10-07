"""The retry policy, idempotency keys, Retry-After, network errors, timeouts, redirects (Go
retry_test.go)."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from typing import Any, List, Optional, Tuple, Type

import httpx
import pytest

from qbitflow import (
    ApiError,
    AuthenticationError,
    BadRequestError,
    ConflictError,
    IdempotencyError,
    NetworkError,
    NotFoundError,
    PermissionDeniedError,
    QBitFlowError,
    RateLimitError,
    RequestOptions,
    ServerError,
    ValidationError,
    is_retryable,
)
from qbitflow._transport import Endpoint, Response, error_from_response

from .conftest import make_client, reply, sequence

OK = (200, '{"ok":true}')
E500 = (500, '{"error":"boom","code":"internal"}')
E503 = (503, '{"error":"no network","code":"network_unavailable"}')
E504 = (504, '{"error":"too slow","code":"timeout"}')
IN_USE = (409, '{"error":"in use","code":"idempotency_key_in_use"}')

CREATE = Endpoint("POST", "/product", body={"name": "Pro"}, idempotent=True)


def get(path: str = "/x") -> Endpoint:
    return Endpoint("GET", path)


CASES: List[
    Tuple[
        str,
        Endpoint,
        List[Tuple[int, str]],
        int,
        List[float],
        Optional[Type[Exception]],
        Optional[int],
    ]
] = [
    ("GET 500 exhausts retries", get(), [E500], 4, [1, 2, 4], ServerError, None),
    ("GET 503 then 200", get(), [E503, OK], 2, [1], None, None),
    ("GET 504 then 200", get(), [E504, OK], 2, [1], None, None),
    (
        "GET 502 non-JSON then 200",
        get(),
        [(502, "<html>bad gateway</html>"), OK],
        2,
        [1],
        None,
        None,
    ),
    (
        "GET 400 not retried",
        get(),
        [(400, '{"error":"bad","code":"bad_request"}')],
        1,
        [],
        BadRequestError,
        None,
    ),
    (
        "GET 401 not retried",
        get(),
        [(401, '{"error":"no","code":"unauthorized"}')],
        1,
        [],
        AuthenticationError,
        None,
    ),
    (
        "GET 403 not retried",
        get(),
        [(403, '{"error":"no","code":"forbidden"}')],
        1,
        [],
        PermissionDeniedError,
        None,
    ),
    (
        "GET 404 not retried",
        get(),
        [(404, '{"error":"no","code":"not_found"}')],
        1,
        [],
        NotFoundError,
        None,
    ),
    ("GET 409 in_use not retried (not a create)", get(), [IN_USE], 1, [], ConflictError, None),
    ("POST action 500 not retried", Endpoint("POST", "/expire"), [E500], 1, [], ServerError, None),
    ("POST action 503 not retried", Endpoint("POST", "/cancel"), [E503], 1, [], ServerError, None),
    (
        "PUT 500 not retried",
        Endpoint("PUT", "/product/x", body={}),
        [E500],
        1,
        [],
        ServerError,
        None,
    ),
    ("DELETE 503 not retried", Endpoint("DELETE", "/product/x"), [E503], 1, [], ServerError, None),
    (
        "POST action 429 not retried",
        Endpoint("POST", "/trust"),
        [(429, '{"error":"slow","code":"rate_limit_exceeded"}')],
        1,
        [],
        RateLimitError,
        None,
    ),
    ("create 500, 500, 201", CREATE, [E500, E500, (201, "{}")], 3, [1, 2], None, None),
    ("create 409 in_use then 201", CREATE, [IN_USE, (201, "{}")], 2, [1], None, None),
    (
        "create 409 unique_violation not retried",
        CREATE,
        [(409, '{"error":"dup","code":"unique_violation","details":{"field":"reference"}}')],
        1,
        [],
        ConflictError,
        None,
    ),
    (
        "create 422 key reused not retried",
        CREATE,
        [(422, '{"error":"reused","code":"idempotency_key_reused"}')],
        1,
        [],
        IdempotencyError,
        None,
    ),
    (
        "create 400 validation not retried",
        CREATE,
        [(400, '{"error":"bad","code":"validation_failed"}')],
        1,
        [],
        ValidationError,
        None,
    ),
    ("3xx not retried", get(), [(302, "")], 1, [], ServerError, None),
    ("max_retries 0 disables", get(), [E500], 1, [], ServerError, 0),
    ("max_retries 1", get(), [E500], 2, [1], ServerError, 1),
    ("max_retries 5", get(), [E503], 6, [1, 2, 4, 8, 16], ServerError, 5),
]


@pytest.mark.parametrize(
    "name, endpoint, replies, attempts, sleeps, error, max_retries",
    CASES,
    ids=[c[0] for c in CASES],
)
def test_retry_matrix(
    name: str,
    endpoint: Endpoint,
    replies: List[Tuple[int, str]],
    attempts: int,
    sleeps: List[float],
    error: Optional[Type[Exception]],
    max_retries: Optional[int],
) -> None:
    kwargs = {} if max_retries is None else {"max_retries": max_retries}
    client, server, slept = make_client(sequence(*replies), **kwargs)
    if error is None:
        client._send(endpoint, None)
    else:
        with pytest.raises(error):
            client._send(endpoint, None)
    assert len(server.requests) == attempts
    assert slept == sleeps


UUID_V4 = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}")


def test_idempotency_key_stable_across_retries() -> None:
    client, server, _ = make_client(sequence(E503, IN_USE, (201, "{}")))
    client._send(CREATE, None)
    assert len(server.requests) == 3
    key = server.requests[0].headers["Idempotency-Key"]
    assert UUID_V4.fullmatch(key)
    for r in server.requests:
        assert r.headers["Idempotency-Key"] == key and r.body == b'{"name":"Pro"}'
    client._send(CREATE, None)  # a new call gets a new key
    nxt = server.requests[3].headers["Idempotency-Key"]
    assert nxt != key and UUID_V4.fullmatch(nxt)


def test_idempotency_key_option() -> None:
    client, server, _ = make_client(sequence(E500, (201, "{}")))
    client._send(CREATE, RequestOptions(idempotency_key="order-1042:create~v1"))
    assert [r.headers["Idempotency-Key"] for r in server.requests] == ["order-1042:create~v1"] * 2
    for bad in ("has space", "tab\tkey", "é", "k" * 256):
        with pytest.raises(ValidationError) as info:
            client._send(CREATE, RequestOptions(idempotency_key=bad))
        assert info.value.field_errors[0].field == "Idempotency-Key"
    client._send(CREATE, RequestOptions(idempotency_key="k" * 255))
    # Ignored (and never sent) on other methods.
    n = len(server.requests)
    client._send(get(), RequestOptions(idempotency_key="has space"))
    assert "Idempotency-Key" not in server.requests[n].headers


NOW = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "header, body, attempts, sleeps, after",
    [
        ("5", '{"error":"slow","code":"rate_limit_exceeded"}', 2, [5], None),
        ("0", '{"error":"slow"}', 2, [1], None),
        (
            format_datetime(NOW + timedelta(seconds=3), usegmt=True),
            '{"error":"slow"}',
            2,
            [3],
            None,
        ),
        (
            "",
            '{"error":"slow","details":{"retryAfterSeconds":7,"limit":60,"periodSeconds":60}}',
            2,
            [7],
            None,
        ),
        ("120", '{"error":"slow","details":{"limit":50,"periodSeconds":3600}}', 1, [], 120),
        (format_datetime(NOW + timedelta(seconds=90), usegmt=True), '{"error":"slow"}', 1, [], 90),
        ("60", '{"error":"slow"}', 2, [60], None),
    ],
)
def test_retry_after(
    header: str, body: str, attempts: int, sleeps: List[float], after: Optional[float]
) -> None:
    def handler(_req: httpx.Request, n: int) -> httpx.Response:
        if n == 0:
            return reply(429, body, {"Retry-After": header} if header else None)
        return reply(200, "{}")

    client, server, slept = make_client(handler)
    client._transport.now = lambda: NOW
    if attempts == 1:
        with pytest.raises(RateLimitError) as info:
            client._send(get(), None)
        assert info.value.retry_after == after
    else:
        client._send(get(), None)
    assert len(server.requests) == attempts
    assert slept == sleeps


def test_rate_limit_backoff_grows() -> None:
    body = (
        '{"error":"slow","code":"rate_limit_exceeded","details":{"lim'
        'it":60,"periodSeconds":60,"retryAfterSeconds":3}}'
    )
    client, _, slept = make_client(lambda _r, _n: reply(429, body, {"Retry-After": "3"}))
    with pytest.raises(RateLimitError) as info:
        client._send(get(), None)
    assert slept == [3, 3, 4]
    err = info.value
    assert err.limit == 60 and err.period_seconds == 60 and err.retry_after == 3


def _drop(_req: httpx.Request, _n: int) -> httpx.Response:
    raise httpx.ConnectError("connection refused")


def test_network_errors_retried() -> None:
    def handler(req: httpx.Request, n: int) -> httpx.Response:
        if n < 2:
            raise httpx.RemoteProtocolError("server disconnected")
        return reply(200, '{"ok":true}')

    client, server, slept = make_client(handler)
    client._send(get(), None)
    assert len(server.requests) == 3 and len(slept) == 2

    down, down_server, _ = make_client(_drop)
    with pytest.raises(NetworkError) as info:
        down._send(get(), None)
    err = info.value
    assert err.status is None and isinstance(err.__cause__, httpx.ConnectError)
    assert "request failed: connection refused" in str(err)
    assert len(down_server.requests) == 4 and is_retryable(err)

    with pytest.raises(NetworkError):
        down._send(Endpoint("POST", "/expire"), None)
    assert len(down_server.requests) == 5  # a non-retried write is attempted once


def test_per_attempt_timeout() -> None:
    def handler(_req: httpx.Request, n: int) -> httpx.Response:
        if n == 0:
            raise httpx.ReadTimeout("timed out")
        return reply(200, '{"ok":true}')

    client, server, slept = make_client(handler, timeout=0.1)
    client._send(get(), None)
    assert len(slept) == 1 and len(server.requests) == 2

    client2, _, _ = make_client(
        lambda _r, _n: (_ for _ in ()).throw(httpx.ConnectTimeout("t")), timeout=0.1, max_retries=0
    )
    with pytest.raises(NetworkError) as info:
        client2._send(get(), None)
    assert "timed out" in str(info.value) and isinstance(
        info.value.__cause__, httpx.TimeoutException
    )


def test_timeout_passed_per_request() -> None:
    seen: List[Any] = []

    def handler(req: httpx.Request, _n: int) -> httpx.Response:
        seen.append(req.extensions.get("timeout"))
        return reply(200, "{}")

    client, _, _ = make_client(handler, timeout=7.5)
    client._send(get(), None)
    assert seen[0]["read"] == 7.5


def test_redirect_not_followed() -> None:
    def handler(req: httpx.Request, _n: int) -> httpx.Response:
        if req.url.path == "/elsewhere":
            return reply(200, '{"hijacked":true}')
        return httpx.Response(302, headers={"Location": "/elsewhere"})

    client, server, slept = make_client(handler)
    http = client._transport.http
    http.follow_redirects = True  # even a caller's client that follows redirects
    for endpoint in (get("/me"), CREATE):
        with pytest.raises(ServerError) as info:
            client._send(endpoint, None)
        assert info.value.status == 302 and not is_retryable(info.value)
    assert all(r.path != "/elsewhere" for r in server.requests)
    assert len(server.requests) == 2 and slept == []


def _mk(status: int, code: str) -> ApiError:
    return error_from_response(
        Response(status, httpx.Headers(), f'{{"error":"x","code":"{code}"}}'.encode()), NOW
    )


@pytest.mark.parametrize(
    "error, want",
    [
        (_mk(500, "internal"), True),
        (_mk(503, "network_unavailable"), True),
        (_mk(504, "timeout"), True),
        (_mk(429, "rate_limit_exceeded"), True),
        (_mk(409, "idempotency_key_in_use"), True),
        (_mk(409, "unique_violation"), False),
        (_mk(422, "idempotency_key_reused"), False),
        (_mk(400, "validation_failed"), False),
        (_mk(404, "not_found"), False),
        (_mk(302, ""), False),
        (NetworkError("down"), True),
        (ValidationError("bad"), False),
        (QBitFlowError("other"), False),
        (Exception("other"), False),
        (None, False),
    ],
)
def test_is_retryable(error: Optional[BaseException], want: bool) -> None:
    assert is_retryable(error) is want


def test_new_key_is_uuid_v4() -> None:
    client, _, _ = make_client(sequence(OK))
    keys = {client._transport.new_key() for _ in range(100)}
    assert len(keys) == 100 and all(UUID_V4.fullmatch(k) for k in keys)
