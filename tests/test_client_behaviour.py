"""
Offline behavioural tests for the client and its request handlers.

These need no API key and no running server — they assert on how the SDK builds its
request state, not on API responses. The PHP SDK has an equivalent suite
(``tests/Unit/ClientBehaviourTest.php``); this file mirrors the parts of it that can be
expressed without a mock HTTP transport (the transport-level suite is
``tests/test_transport.py``).

Run with:
    pytest tests/test_client_behaviour.py -v
"""

import warnings

import pytest

from qbitflow import QBitFlow, __version__
from qbitflow.exceptions import ValidationError
from qbitflow.requests.claim import ClaimRequests
from qbitflow.requests.transaction.payment import PaymentRequests
from qbitflow.requests.transaction.subscription import SubscriptionRequests

# Every service the client mounts. Parametrising over all of them is the point: the
# `headers` kwarg is passed by the shared `on_behalf_of` on the base class, so a service
# that overrides `__init__` without accepting it raises TypeError at call time rather
# than failing any type check. That is how payments/subscriptions regressed.
ALL_SERVICES = [
    "customers",
    "products",
    "users",
    "api_keys",
    "currencies",
    "transaction_status",
    "one_time_payments",
    "subscriptions",
    "refunds",
    "accounting",
    "claims",
    "webhooks",
]


@pytest.fixture
def client():
    """A client with a dummy key — no request is ever issued by these tests."""
    client = QBitFlow(api_key="sk_dummy_offline_tests", base_url="http://api.test/v1")
    yield client
    client.close()


@pytest.mark.parametrize("service_name", ALL_SERVICES)
def test_on_behalf_of_is_callable_on_every_service(client, service_name):
    """Regression: `on_behalf_of` must not raise on any mounted service."""
    scoped = getattr(client, service_name).on_behalf_of(123)

    assert scoped.headers.get("On-Behalf-Of") == "123"


@pytest.mark.parametrize("service_name", ALL_SERVICES)
def test_on_behalf_of_leaves_the_original_service_untouched(client, service_name):
    """Scoping returns a copy; mixing org-level and per-user calls must stay safe."""
    original = getattr(client, service_name)
    scoped = original.on_behalf_of(123)

    assert scoped is not original
    assert "On-Behalf-Of" not in original.headers


@pytest.mark.parametrize("service_name", ALL_SERVICES)
def test_on_behalf_of_preserves_the_service_type_and_settings(client, service_name):
    """The scoped copy keeps the resource methods, base URL, timeout and retry budget."""
    original = getattr(client, service_name)
    scoped = original.on_behalf_of(123)

    assert isinstance(scoped, type(original))
    assert scoped.base_url == original.base_url == "http://api.test/v1"
    assert scoped.timeout == original.timeout
    assert scoped.max_retries == original.max_retries
    assert scoped._client is original._client, "the connection pool is shared"


@pytest.mark.parametrize(
    ("service_name", "expected_type"),
    [
        ("one_time_payments", PaymentRequests),
        ("subscriptions", SubscriptionRequests),
    ],
)
def test_on_behalf_of_reaches_the_nested_session_handler(client, service_name, expected_type):
    """
    Payments and subscriptions delegate session retrieval to their own SessionRequests.
    The scoped header has to survive that hop, or `get_session` would silently run at
    organization level while every other call on the same scoped service is impersonated.
    """
    scoped = getattr(client, service_name).on_behalf_of(456)

    assert isinstance(scoped, expected_type)
    assert scoped._session.headers.get("On-Behalf-Of") == "456"
    assert scoped._session.base_url == "http://api.test/v1"


def test_on_behalf_of_zero_acts_at_organization_level(client):
    """`0` means "no impersonation" and omits the header — the documented contract."""
    scoped = client.products.on_behalf_of(0)

    assert "On-Behalf-Of" not in scoped.headers


def test_on_behalf_of_negative_raises(client):
    with pytest.raises(ValidationError):
        client.products.on_behalf_of(-7)


@pytest.mark.parametrize("bad", [True, False, 1.0, "5", None])
def test_on_behalf_of_rejects_non_integers(client, bad):
    """`True` used to be sent as `On-Behalf-Of: True`, and `"5"` raised a bare TypeError."""
    with pytest.raises(ValidationError, match="non-negative integer"):
        client.products.on_behalf_of(bad)
    with pytest.raises(ValidationError, match="non-negative integer"):
        client.on_behalf_of(bad)


@pytest.mark.parametrize("key", ["", "   ", "\t\n", None, 42])
def test_client_requires_a_non_blank_api_key(key):
    with pytest.raises(ValueError):
        QBitFlow(api_key=key)


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"timeout": -1}, "timeout"),
        ({"timeout": float("nan")}, "timeout"),
        ({"timeout": "30"}, "timeout"),
        ({"max_retries": -1}, "max_retries"),
        ({"max_retries": 1.5}, "max_retries"),
        ({"max_retries": True}, "max_retries"),
    ],
)
def test_invalid_settings_raise_the_sdk_validation_error(kwargs, match):
    with pytest.raises(ValidationError, match=match):
        QBitFlow(api_key="sk_dummy_offline_tests", **kwargs)


# ── Client-level On-Behalf-Of ───────────────────────────────────────────────


@pytest.mark.parametrize("service_name", ALL_SERVICES)
def test_client_on_behalf_of_scopes_every_service(client, service_name):
    scoped = client.on_behalf_of(77)

    service = getattr(scoped, service_name)
    assert service.headers.get("On-Behalf-Of") == "77"
    assert service._client is client._http, "the connection pool is shared"
    assert service.base_url == "http://api.test/v1"
    assert "On-Behalf-Of" not in getattr(client, service_name).headers


def test_client_on_behalf_of_reaches_nested_session_handlers(client):
    scoped = client.on_behalf_of(78)

    assert scoped.one_time_payments._session.headers["On-Behalf-Of"] == "78"
    assert scoped.subscriptions._session.headers["On-Behalf-Of"] == "78"


def test_client_on_behalf_of_zero_is_organization_level(client):
    scoped = client.on_behalf_of(0)

    for service_name in ALL_SERVICES:
        assert "On-Behalf-Of" not in getattr(scoped, service_name).headers


def test_client_on_behalf_of_keeps_the_settings():
    client = QBitFlow(
        "sk_dummy_offline_tests", base_url="http://api.test/", timeout=5, max_retries=0
    )
    try:
        scoped = client.on_behalf_of(9)
        assert scoped.base_url == "http://api.test"
        assert scoped.products.timeout == 5
        assert scoped.products.max_retries == 0
        assert scoped.api_key == client.api_key
        assert "on_behalf_of=9" in repr(scoped)
        # A service-level scope on top of a client-level one replaces it.
        assert scoped.products.on_behalf_of(0).headers.get("On-Behalf-Of") is None
        assert scoped.products.on_behalf_of(10).headers["On-Behalf-Of"] == "10"
    finally:
        client.close()


def test_closing_a_scoped_client_does_not_close_the_shared_pool(client):
    scoped = client.on_behalf_of(5)
    scoped.close()
    with scoped:
        pass

    assert not client._http.is_closed


# ── Deprecated aliases ──────────────────────────────────────────────────────


def test_claim_is_a_deprecated_alias_of_claims(client):
    with pytest.warns(DeprecationWarning, match="claims"):
        alias = client.claim

    assert alias is client.claims
    assert isinstance(alias, ClaimRequests)


def test_claims_does_not_warn(client):
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert isinstance(client.claims, ClaimRequests)


def test_get_request_is_a_deprecated_alias_of_get_request_by_user(client, monkeypatch):
    calls = []
    monkeypatch.setattr(
        ClaimRequests, "get_request_by_user", lambda self, user_id: calls.append(user_id) or "ok"
    )

    with pytest.warns(DeprecationWarning, match="get_request_by_user"):
        assert client.claims.get_request(42) == "ok"

    assert calls == [42]


def test_every_handler_sends_the_auth_and_user_agent_headers(client):
    for service_name in ALL_SERVICES:
        headers = getattr(client, service_name).headers
        assert headers["X-API-Key"] == "sk_dummy_offline_tests"
        assert headers["User-Agent"] == f"qbitflow-python/{__version__}"


def test_explicit_zero_settings_are_honoured():
    client = QBitFlow(api_key="sk_dummy_offline_tests", timeout=0, max_retries=0)
    try:
        assert client.products.timeout == 0
        assert client.products.max_retries == 0
    finally:
        client.close()


def test_defaults_when_unset():
    client = QBitFlow(api_key="sk_dummy_offline_tests")
    try:
        assert client.products.timeout == 30
        assert client.products.max_retries == 3
    finally:
        client.close()


def test_repr_hides_the_key(client):
    text = repr(client)
    assert "sk_dummy_offline_tests" not in text
    assert text.endswith("ests', base_url='http://api.test/v1')")


def test_client_is_a_context_manager():
    with QBitFlow(api_key="sk_dummy_offline_tests") as client:
        pool = client._http
        assert not pool.is_closed
    assert pool.is_closed
