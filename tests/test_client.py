"""The client: construction, options, headers, on_behalf_of, me (Go client_test.go)."""

from __future__ import annotations

import re

import httpx
import pytest

import qbitflow
from qbitflow import (
    DEFAULT_BASE_URL,
    Credential,
    QBitFlow,
    RequestOptions,
    Role,
    ValidationError,
)

from .conftest import MEMBER_UUID, TEST_API_KEY, make_client, reply, static

UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}")


@pytest.mark.parametrize("key", ["", "   ", "pk_live_123", "SK_live", "key", None, 42])
def test_api_key_refused(key: object) -> None:
    with pytest.raises(ValidationError) as info:
        QBitFlow(key)
    err = info.value
    assert err.status is None
    assert [f.field for f in err.field_errors] == ["apiKey"]


@pytest.mark.parametrize(
    "key", ["sk_", "sk_123_live_abc", "sk_019eca82-5680-7b00-8000-0000000000b1_test_x", "  sk_x  "]
)
def test_api_key_accepted(key: str) -> None:
    QBitFlow(key).close()


def test_defaults() -> None:
    client = QBitFlow("sk_x")
    t = client._transport
    assert DEFAULT_BASE_URL == "https://api.qbitflow.app/v2" == t.base_url
    assert t.timeout == 30.0 and t.max_retries == 3
    assert client._on_behalf_of == ""
    for name in (
        "products",
        "customers",
        "checkout_sessions",
        "payments",
        "failures",
        "subscriptions",
        "refunds",
        "members",
        "invitations",
        "wallets",
        "accounting",
        "webhooks",
        "currencies",
    ):
        assert getattr(client, name) is not None, name
    assert client.webhooks.endpoints is not None and client.webhooks.events is not None
    assert qbitflow.__version__ == "3.0.0"


@pytest.mark.parametrize(
    "kwargs, field",
    [
        ({"base_url": "ftp://api.example.com"}, "baseUrl"),
        ({"base_url": "/v2"}, "baseUrl"),
        ({"base_url": ""}, "baseUrl"),
        ({"timeout": 0}, "timeout"),
        ({"timeout": -1}, "timeout"),
        ({"timeout": True}, "timeout"),
        ({"max_retries": -1}, "maxRetries"),
        ({"max_retries": 1.5}, "maxRetries"),
        ({"on_behalf_of": "42"}, "onBehalfOf"),
        ({"on_behalf_of": "00000000-0000-0000-0000-000000000000"}, "onBehalfOf"),
        ({"on_behalf_of": " " + MEMBER_UUID}, "onBehalfOf"),
        ({"http_client": object()}, "httpClient"),
    ],
)
def test_bad_options(kwargs: dict, field: str) -> None:
    with pytest.raises(ValidationError) as info:
        QBitFlow("sk_x", **kwargs)
    assert info.value.field_errors[0].field == field


def test_options_applied() -> None:
    http = httpx.Client()
    client = QBitFlow(
        "sk_x",
        base_url="https://sandbox.example.com/v2///",
        timeout=2,
        max_retries=0,
        http_client=http,
        on_behalf_of=MEMBER_UUID,
    )
    t = client._transport
    assert t.base_url == "https://sandbox.example.com/v2"
    assert t.timeout == 2.0 and t.max_retries == 0 and client._on_behalf_of == MEMBER_UUID
    assert t.http is http and not t.owns_http
    client.close()
    assert not http.is_closed  # the caller's client is the caller's to close
    http.close()


def test_context_manager_closes_its_own_client() -> None:
    with QBitFlow("sk_x") as client:
        http = client._transport.http
    assert http.is_closed


def test_headers() -> None:
    client, server, _ = make_client(static(200, '{"credential":"apiKey"}'))
    client.me()
    client.products.create(
        name="Pro", price_usd="1", options=RequestOptions(request_id="req-1.a:b_c")
    )
    get, post = server.requests
    for r in server.requests:
        assert r.headers["X-API-Key"] == TEST_API_KEY
        assert r.headers["User-Agent"] == "qbitflow-python/3.0.0"
        assert r.headers["Accept"] == "application/json"
        assert "On-Behalf-Of" not in r.headers
    assert get.method == "GET" and get.path == "/me"
    for h in ("Content-Type", "Idempotency-Key", "X-Request-Id"):
        assert h not in get.headers
    assert post.headers["Content-Type"] == "application/json"
    assert post.method == "POST" and post.path == "/products"
    assert post.body == b'{"name":"Pro","priceUsd":"1"}'
    assert post.headers["X-Request-Id"] == "req-1.a:b_c"
    assert UUID_RE.fullmatch(post.headers["Idempotency-Key"])


@pytest.mark.parametrize("request_id", ["has space", "slash/no", "é", "r" * 129])
def test_request_id_validation(request_id: str) -> None:
    client, server, _ = make_client(static(200))
    with pytest.raises(ValidationError) as info:
        client.me(options=RequestOptions(request_id=request_id))
    assert info.value.field_errors[0].field == "X-Request-Id"
    assert server.requests == []


def test_options_type_checked() -> None:
    client, server, _ = make_client(static(200))
    with pytest.raises(ValidationError):
        client.me(options={"request_id": "x"})
    assert server.requests == []


def test_on_behalf_of() -> None:
    other = "01a05cd7-2a00-7d00-8000-0000000000d1"
    client, server, _ = make_client(static(200))
    member = client.on_behalf_of(MEMBER_UUID)
    org_only = member.on_behalf_of("")
    assert member._transport is client._transport
    assert member.products._client is member and client.products._client is client

    calls = [
        (client, None, None),
        (member, None, MEMBER_UUID),
        (member, RequestOptions(on_behalf_of=other), other),  # the request wins
        (member, RequestOptions(on_behalf_of=""), None),  # "" forces the organization level
        (client, RequestOptions(on_behalf_of=other), other),
        (org_only, None, None),
    ]
    for c, opts, _ in calls:
        c.me(options=opts)
    for r, (_, _, want) in zip(server.requests, calls):
        assert r.headers.get("On-Behalf-Of") == want

    # The client-level option.
    client2, server2, _ = make_client(static(200), on_behalf_of=MEMBER_UUID)
    client2.me()
    assert server2.requests[0].headers["On-Behalf-Of"] == MEMBER_UUID

    # "" is the organization level: the header is omitted, never sent blank (a blank one is a
    # 403), at every level.
    client3, server3, _ = make_client(static(200), on_behalf_of="")
    client3.me()
    client3.on_behalf_of(None).me()
    client3.me(options=RequestOptions(on_behalf_of=""))
    for r in server3.requests:
        assert "On-Behalf-Of" not in r.headers


def test_on_behalf_of_invalid() -> None:
    client, server, _ = make_client(static(200))
    # A whitespace-only value is invalid, not the organization level (only "" or None is).
    for bad in ("not-a-uuid", "00000000-0000-0000-0000-000000000000", "   ", "\t"):
        with pytest.raises(ValidationError) as info:
            client.on_behalf_of(bad)  # eager: the derived client is never built
        assert info.value.field_errors[0].field == "onBehalfOf"
    for bad in ("123", " "):
        with pytest.raises(ValidationError):
            client.me(options=RequestOptions(on_behalf_of=bad))
    assert server.requests == []
    client.me()  # the original client is unaffected
    upper = client.on_behalf_of("019ECA82-5680-7B00-8000-0000000000B1")
    upper.me()
    assert server.requests[-1].headers["On-Behalf-Of"] == "019ECA82-5680-7B00-8000-0000000000B1"


def test_me() -> None:
    body = """{
        "credential": "apiKey",
        "apiKeyUuid": "019cadfd-8900-7b00-8000-0000000000f1",
        "role": "user",
        "onBehalfOfUserUuid": "019eca82-5680-7b00-8000-0000000000b1",
        "space": {
            "uuid": "019eca82-5680-7c00-8000-0000000000b2",
            "organizationUuid": "019cadfd-8900-7a00-8000-0000000000a1",
            "organizationName": "Example Shop",
            "userUuid": "019eca82-5680-7b00-8000-0000000000b1",
            "member": {"userUuid": "019eca82-5680-7b00-8000-0000000000b1", "firstName": "Ada",
                       "lastName": "Lovelace", "email": "ada@example.com"},
            "test": true,
            "role": "owner",
            "organizationFeePercent": "7.5",
            "createdAt": "2026-09-01T12:00:00Z"
        },
        "user": {"ignored": true}
    }"""
    client, _, _ = make_client(lambda _r, _n: reply(200, body))
    me = client.me()
    assert me.credential == Credential.API_KEY and me.role == Role.USER
    assert me.on_behalf_of_user_uuid == MEMBER_UUID and me.user_uuid is None
    assert me.space is not None and me.space.test and me.space.organization_name == "Example Shop"
    assert me.space.member is not None and me.space.member.first_name == "Ada"
    assert me.space.role == Role.OWNER and me.space.organization_fee_percent == "7.5"
    assert me.space.trusted_at is None and me.space.created_at.year == 2026
    assert "user" not in me.to_dict()


def test_services() -> None:
    client = QBitFlow(TEST_API_KEY)
    for name, cls in (
        ("products", qbitflow.ProductsService),
        ("customers", qbitflow.CustomersService),
        ("checkout_sessions", qbitflow.CheckoutSessionsService),
        ("payments", qbitflow.PaymentsService),
        ("transactions", qbitflow.TransactionsService),
        ("failures", qbitflow.FailuresService),
        ("subscriptions", qbitflow.SubscriptionsService),
        ("refunds", qbitflow.RefundsService),
        ("members", qbitflow.MembersService),
        ("invitations", qbitflow.InvitationsService),
        ("wallets", qbitflow.WalletsService),
        ("accounting", qbitflow.AccountingService),
        ("webhooks", qbitflow.WebhooksService),
        ("currencies", qbitflow.CurrenciesService),
    ):
        assert isinstance(getattr(client, name), cls), name
    assert isinstance(client.webhooks.endpoints, qbitflow.WebhookEndpointsService)
    assert isinstance(client.webhooks.events, qbitflow.WebhookEventsService)
    member = client.on_behalf_of(MEMBER_UUID)
    assert member.transactions._client is member
    # The draft's names are gone.
    for gone in ("get_status", "get_by_email", "get_public_history", "list_combined"):
        for service in (client.checkout_sessions, client.customers, client.subscriptions):
            assert not hasattr(service, gone)
    assert not hasattr(client.payments, "list_combined")
    assert not hasattr(client.refunds, "initiate") and not hasattr(client.refunds, "list_inactive")
    assert not hasattr(client.subscriptions, "execute_test_billing")
    assert not hasattr(client.wallets, "list_supported_currencies")
    assert not hasattr(client.currencies, "list_available")


def test_repr() -> None:
    client = QBitFlow("sk_secret_value")
    assert "sk_secret" not in repr(client)
    assert "on_behalf_of" in repr(client.on_behalf_of(MEMBER_UUID))
