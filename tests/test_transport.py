"""Path and query encoding, body encoding, the decoding policy, status handling (Go
transport_test.go)."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs

import httpx
import pytest
from pydantic import Field

from qbitflow import (
    BadRequestError,
    Product,
    RequestOptions,
    ServerError,
    SubscriptionStatus,
    ValidationError,
    is_retryable,
)
from qbitflow._transport import Endpoint, Query, Response, decode, format_time, pathf
from qbitflow.models import Model
from qbitflow.models._base import ZERO_TIME, Bool, Float, Int, Str, Time, UInt
from qbitflow.models._fields import SubscriptionStatusT

from .conftest import MEMBER_UUID, make_client, reply, static


@pytest.mark.parametrize(
    "got, want",
    [
        (pathf("/product/reference/{}", "a/b c"), "/product/reference/a%2Fb%20c"),
        (pathf("/transaction/payment/{}", "pay@019c-1"), "/transaction/payment/pay@019c-1"),
        (pathf("/customer/email/{}", "a+b@example.com"), "/customer/email/a+b@example.com"),
        (pathf("/product/reference/{}", ".."), "/product/reference/%2E%2E"),
        (pathf("/product/reference/{}", "."), "/product/reference/%2E"),
        (pathf("/product/reference/{}", "v1..2"), "/product/reference/v1..2"),
        (pathf("/x/{}/y/{}", "?q=1#f", "%41"), "/x/%3Fq=1%23f/y/%2541"),
        (
            pathf("/transaction/subscription/reference/{}/{}", "subscription", "ord:1"),
            "/transaction/subscription/reference/subscription/ord:1",
        ),
    ],
)
def test_path_escaping(got: str, want: str) -> None:
    assert got == want


def test_escaped_path_reaches_the_server() -> None:
    client, server, _ = make_client(static(200, "{}"))
    client.products.get_by_reference("a/b")
    assert server.requests[0].path == "/product/reference/a%2Fb"


def test_query_encoding() -> None:
    after = datetime(2026, 10, 4, 12, tzinfo=timezone(timedelta(hours=2)))
    before = datetime(2026, 10, 5, 0, 0, 0, 500, tzinfo=timezone.utc)
    assert format_time(after) == "2026-10-04T12:00:00+02:00"
    assert format_time(before) == "2026-10-05T00:00:00.0005Z"
    client, server, _ = make_client(static(200, '{"items":[],"nextCursor":null}'))
    client.payments.list(
        limit=25,
        cursor="019c-cursor",
        customer_uuid=MEMBER_UUID,
        created_after=after,
        created_before=before,
        include_members=True,
        refunded=False,
    )
    want = (
        "createdAfter=2026-10-04T12%3A00%3A00%2B02%3A00&createdBefore=2026-10-05T00%3A00%3A00.0005Z"
        "&cursor=019c-cursor&customerUuid=" + MEMBER_UUID + "&includeMembers=true&limit=25"
        "&refunded=false"
    )
    raw = server.requests[0].query
    assert raw == want
    assert parse_qs(raw)["createdAfter"] == ["2026-10-04T12:00:00+02:00"]
    # Unset filters are omitted.
    client.payments.list()
    assert server.requests[1].query == ""


def test_naive_datetime_refused() -> None:
    client, server, _ = make_client(static(200))
    with pytest.raises(ValidationError) as info:
        client.payments.list(created_after=datetime(2026, 1, 1))
    assert info.value.field_errors[0].field == "createdAfter"
    assert server.requests == []


@pytest.mark.parametrize(
    "query, want",
    [
        (
            Query().flag("includeHidden", True).boolean("subscription", True),
            "includeHidden=true&subscription=true",
        ),
        (Query().flag("includeHidden", False).boolean("subscription", None), ""),
        (
            Query().page(5, None).string("email", "a+b@x.io").boolean("verified", False),
            "email=a%2Bb%40x.io&limit=5&verified=false",
        ),
        (
            Query().string("source", "subscriptionHistory").string("subscriptionUuid", "sub@x"),
            "source=subscriptionHistory&subscriptionUuid=sub%40x",
        ),
        (Query().page(-1, ""), "limit=-1"),
        (Query().string("x", ""), ""),
    ],
)
def test_query_helpers(query: Query, want: str) -> None:
    assert query.encode() == want


@pytest.mark.parametrize(
    "body, field",
    [
        ({"name": "Pro", "price": math.nan}, None),
        ({"price": math.inf}, None),
        ({"name": "Ad\udcffa", "email": "a@b.co"}, "name"),
        ({"address": "bad \udcfe"}, "address"),
        ({"frequency": {"value": 1, "unit": "mon\udcffths"}}, "frequency.unit"),
        ({"bad\udcffkey": 1}, "body"),
        ({"url": "https://x.io", "events": ["payment.completed", "x\udcff"]}, "events[1]"),
    ],
)
def test_body_encoding_failures(body: Dict[str, Any], field: Optional[str]) -> None:
    client, server, _ = make_client(static(200))
    with pytest.raises(ValidationError) as info:
        client._send(Endpoint("POST", "/x", body=body), None)
    if field is not None:
        assert [f.field for f in info.value.field_errors] == [field]
    assert server.requests == []


def test_body_utf8_sent_untouched() -> None:
    client, server, _ = make_client(static(200))
    client._send(Endpoint("POST", "/x", body={"name": "O’Brien ☃ �"}), None)
    assert server.requests[0].body == '{"name":"O’Brien ☃ �"}'.encode("utf-8")


def test_service_body_with_lone_surrogate() -> None:
    client, server, _ = make_client(static(200))
    with pytest.raises(ValidationError) as info:
        client.customers.create(name="Ada", email="a@b.co", address="bad \udcfe")
    assert [f.field for f in info.value.field_errors] == ["address"]
    assert server.requests == []


class Target(Model):
    s: Str = ""
    n: Int = 0
    u: UInt = 0
    f: Float = 0.0
    b: Bool = False
    t: Time = ZERO_TIME
    p: Optional[Time] = None
    lst: List[Int] = Field(default_factory=list, alias="l")
    m: Dict[str, Str] = Field(default_factory=dict)
    enum: SubscriptionStatusT = ""
    dec: Str = ""


def _decode(body: str, status: int = 200, headers: Optional[Dict[str, str]] = None) -> Target:
    return decode(Target, Response(status, httpx.Headers(headers or {}), body.encode()))


@pytest.mark.parametrize(
    "name, body, check",
    [
        (
            "absent fields are zero",
            "{}",
            lambda v: v.s == ""
            and v.n == 0
            and not v.b
            and v.t == ZERO_TIME
            and v.p is None
            and v.lst == [],
        ),
        (
            "null fields are zero",
            '{"s":null,"n":null,"f":null,"b":null,"t":null,"p":null,"l":null,"m":null}',
            lambda v: v.s == "" and v.n == 0 and v.t == ZERO_TIME and v.p is None and v.lst == [],
        ),
        ("unknown keys ignored", '{"zzz":{"a":[1]},"s":"x"}', lambda v: v.s == "x"),
        (
            "unknown enum kept",
            '{"enum":"hibernating"}',
            lambda v: v.enum == "hibernating" and not isinstance(v.enum, SubscriptionStatus),
        ),
        ("known enum", '{"enum":"active"}', lambda v: v.enum is SubscriptionStatus.ACTIVE),
        ("int into float", '{"f":3}', lambda v: v.f == 3.0 and isinstance(v.f, float)),
        (
            "integral float into int",
            '{"n":2.0,"u":1e3,"f":1.5}',
            lambda v: v.n == 2 and v.u == 1000 and v.f == 1.5,
        ),
        (
            "decimal strings stay strings",
            '{"dec":"-10004200.000001"}',
            lambda v: v.dec == "-10004200.000001",
        ),
        (
            "local offsets and microseconds",
            '{"t":"2026-09-13T21:23:26.620071+02:00"}',
            lambda v: v.t == datetime(2026, 9, 13, 19, 23, 26, 620071, tzinfo=timezone.utc),
        ),
        (
            "nanoseconds truncated",
            '{"t":"2026-09-13T21:23:26.123456789Z"}',
            lambda v: v.t.microsecond == 123456,
        ),
    ],
)
def test_decoding_policy(name: str, body: str, check: Any) -> None:
    assert check(_decode(body)), name


@pytest.mark.parametrize(
    "body",
    [
        "",
        "  \n",
        "<html>ok</html>",
        '{"n":"5"}',
        '{"s":5}',
        '{"s":true}',
        '{"b":"true"}',
        '{"b":1}',
        '{"l":{}}',
        '{"t":5}',
        '{"t":"yesterday"}',
        '{"t":"2026-09-13T21:23:26"}',
        '{"n":2.5}',
        '{"u":-1}',
        '{"n":true}',
        '{"f":"1.5"}',
        '{"enum":5}',
        "[1]",
        '{"s":"x"',
        "null",
    ],
)
def test_decoding_failures_are_server_errors(body: str) -> None:
    with pytest.raises(ServerError) as info:
        _decode(body, 201, {"X-Request-Id": "rid"})
    assert info.value.status == 201 and info.value.request_id == "rid"
    assert not is_retryable(info.value)


def test_null_list_is_empty() -> None:
    assert decode(List[Product], Response(200, httpx.Headers(), b"null")) == []


def test_status_text_and_void() -> None:
    def handler(request: httpx.Request, _n: int) -> httpx.Response:
        path = request.url.path
        if path == "/accounting/export":
            if request.url.params.get("from") == "2026-01-01":
                return reply(400, '{"error":"too long","code":"bad_request"}')
            return httpx.Response(
                200, text="paymentUuid,type\npay@1,payment\n", headers={"Content-Type": "text/csv"}
            )
        if path.startswith("/product/") and request.method == "DELETE":
            return {
                "/product/019eca82-5680-7b00-8000-0000000000c1": reply(
                    200, '{"message":"deleted"}'
                ),
                "/product/019eca82-5680-7b00-8000-0000000000c2": httpx.Response(204),
            }.get(path, httpx.Response(200))
        if path.startswith("/product/uuid/"):
            return httpx.Response(204) if path.endswith("c2") else httpx.Response(200)
        return reply(404, "{}")

    client, server, _ = make_client(handler)
    text = client.accounting.export_csv("2026-09-01", "2026-09-30")
    assert text == "paymentUuid,type\npay@1,payment\n"
    assert server.requests[0].headers["Accept"] == "text/csv, application/json"
    with pytest.raises(BadRequestError):
        client.accounting.export_csv("2026-01-01", "2026-09-30")
    for suffix in ("c1", "c2", "c3"):
        assert client.products.delete(f"019eca82-5680-7b00-8000-0000000000{suffix}") is None
    for suffix in ("c1", "c2"):  # an empty 200, a 204: where JSON is expected
        with pytest.raises(ServerError):
            client.products.get(f"019eca82-5680-7b00-8000-0000000000{suffix}")


def test_request_options_dataclass() -> None:
    opts = RequestOptions(on_behalf_of="", idempotency_key="k", request_id="r")
    assert opts.on_behalf_of == "" and opts.idempotency_key == "k" and opts.request_id == "r"
