"""
Offline behavioural tests for the client and its request handlers.

These need no API key and no running server — they assert on how the SDK builds its
request state, not on API responses. The PHP SDK has an equivalent suite
(``tests/Unit/ClientBehaviourTest.php``); this file mirrors the parts of it that can be
expressed without a mock HTTP transport.

Run with:
    pytest tests/test_client_behaviour.py -v
"""

import pytest

from qbitflow import QBitFlow
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
    "claim",
    "webhooks",
]


@pytest.fixture
def client():
    """A client with a dummy key — no request is ever issued by these tests."""
    return QBitFlow(api_key="sk_dummy_offline_tests")


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
def test_on_behalf_of_preserves_the_service_type(client, service_name):
    """The scoped copy has to keep the resource methods of the service it came from."""
    original = getattr(client, service_name)

    assert isinstance(original.on_behalf_of(123), type(original))


@pytest.mark.parametrize(
    ("service_name", "expected_type"),
    [
        ("one_time_payments", PaymentRequests),
        ("subscriptions", SubscriptionRequests),
    ],
)
def test_on_behalf_of_reaches_the_nested_session_handler(client, service_name, expected_type):
    """
    Payments and subscriptions delegate session creation to their own SessionRequests.
    The scoped header has to survive that hop, or `create_session` would silently run at
    organization level while every other call on the same scoped service is impersonated.
    """
    scoped = getattr(client, service_name).on_behalf_of(456)

    assert isinstance(scoped, expected_type)
    assert scoped._session.headers.get("On-Behalf-Of") == "456"


def test_on_behalf_of_zero_acts_at_organization_level(client):
    """`0` means "no impersonation" and omits the header — the documented contract."""
    scoped = client.products.on_behalf_of(0)

    assert "On-Behalf-Of" not in scoped.headers


def test_client_requires_an_api_key():
    with pytest.raises(ValueError):
        QBitFlow(api_key="")
