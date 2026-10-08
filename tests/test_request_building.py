"""
Offline tests for URL construction and the webhook-verification contract.

No API key and no server needed: the transport layer is stubbed so the endpoint the SDK
built can be asserted directly, and error paths can be driven deterministically.

Run with:
    pytest tests/test_request_building.py -v
"""

import pytest

from qbitflow import QBitFlow
from qbitflow.exceptions import (
    APIError,
    AuthenticationError,
    ForbiddenException,
    NetworkError,
    ValidationError,
)


@pytest.fixture
def client():
    return QBitFlow(api_key="sk_dummy_offline_tests")


@pytest.fixture
def captured(monkeypatch):
    """Capture the endpoint each request handler builds, without issuing a request."""
    calls = []

    def fake_make_request(self, endpoint, method="GET", data=None, params=None, **kwargs):
        calls.append({"endpoint": endpoint, "method": method, "data": data, "params": params})
        return {}

    monkeypatch.setattr(
        "qbitflow.requests.base_request.BaseRequest._make_request", fake_make_request
    )
    return calls


# ── Path escaping ────────────────────────────────────────────────────────────


def test_reference_with_slashes_stays_one_segment(client, captured):
    """
    A reference comes straight from the caller's own order system. Interpolated raw, the
    slashes make it address a different route entirely.
    """
    try:
        client.products.get_by_reference("ORD/2026/17")
    except Exception:
        pass  # the stub returns {}, so model construction may fail — the URL is the point

    assert captured[0]["endpoint"] == "/product/reference/ORD%2F2026%2F17"


@pytest.mark.parametrize(
    ("call", "expected"),
    [
        (lambda c: c.customers.get("a/b"), "/customer/uuid/a%2Fb"),
        (lambda c: c.customers.get_by_reference("a/b"), "/customer/reference/a%2Fb"),
        (lambda c: c.customers.get_by_email("a/b@x.com"), "/customer/email/a%2Fb%40x.com"),
        (lambda c: c.one_time_payments.get("a/b"), "/transaction/payment/a%2Fb"),
        (
            lambda c: c.one_time_payments.get_by_reference("a/b"),
            "/transaction/payment/reference/a%2Fb",
        ),
        (lambda c: c.subscriptions.get("a/b"), "/transaction/subscription/a%2Fb"),
        (
            lambda c: c.refunds.get_by_transaction("a/b"),
            "/transaction/refunds/by-transaction/a%2Fb",
        ),
        (lambda c: c.users.get_by_email("a/b@x.com"), "/user/email/a%2Fb%40x.com"),
    ],
)
def test_escaping_covers_every_user_supplied_segment(client, captured, call, expected):
    try:
        call(client)
    except Exception:
        pass

    assert captured[0]["endpoint"] == expected


def test_prefixed_identifiers_survive_escaping(client, captured):
    """
    The API's own identifiers carry a ``pay@`` prefix. Escaping ``@`` to ``%40`` is fine —
    the server decodes path params — but the identifier must still round-trip intact.
    """
    try:
        client.one_time_payments.get("pay@550e8400-e29b-41d4-a716-446655440000")
    except Exception:
        pass

    endpoint = captured[0]["endpoint"]
    assert endpoint == "/transaction/payment/pay%40550e8400-e29b-41d4-a716-446655440000"


def test_websocket_url_escapes_query_values(client):
    from qbitflow.dto.transaction.status import TransactionType

    url = client.transaction_status.get_websocket_url("a&b", TransactionType.ONE_TIME_PAYMENT)

    # Raw, the '&' would split into an extra query parameter and truncate txUUID.
    assert "txUUID=a%26b" in url
    assert url.startswith("ws://") or url.startswith("wss://")


# ── Webhook verification contract ────────────────────────────────────────────


def raise_on_request(monkeypatch, exc):
    """Make every request raise, to drive the verification error paths."""

    def fake_make_request(self, *args, **kwargs):
        raise exc

    monkeypatch.setattr(
        "qbitflow.requests.base_request.BaseRequest._make_request", fake_make_request
    )


def test_verify_reports_a_rejected_signature_as_false(client, monkeypatch):
    raise_on_request(monkeypatch, ValidationError("invalid signature", status_code=400))

    assert client.webhooks.verify(b'{"a":1}', "sha256=bad", "123") is False


def test_verify_accepts_a_valid_signature(client, captured):
    assert client.webhooks.verify(b'{"a":1}', "sha256=good", "123") is True


@pytest.mark.parametrize(
    "exc",
    [
        # A 403 now raises its own type, so a permissions failure can never be
        # reported as a forged signature.
        ForbiddenException("forbidden", status_code=403),
        AuthenticationError("invalid token", status_code=401),
        NetworkError("connection refused"),
        APIError("boom", status_code=500),
    ],
)
def test_verify_propagates_non_rejection_failures(client, monkeypatch, exc):
    """
    Reporting these as "not verified" would make an outage indistinguishable from a
    forged signature, and a handler that drops unverified events would silently discard
    real payments for the duration.
    """
    raise_on_request(monkeypatch, exc)

    with pytest.raises(type(exc)):
        client.webhooks.verify(b'{"a":1}', "sha256=good", "123")


def test_verify_does_not_flatten_the_error_type(client, monkeypatch):
    """The blanket re-wrap used to turn every failure into APIError, losing the cause."""
    raise_on_request(monkeypatch, NetworkError("connection refused"))

    with pytest.raises(NetworkError):
        client.webhooks.verify(b'{"a":1}', "sha256=good", "123")


# ── Adjudicated corrections ──────────────────────────────────────────────────


def test_link_response_has_no_phantom_expiry_field():
    """
    The API's LinkResponse is exactly {link, uuid} — confirmed against a real 201. An
    `expires_at` field was declared here and could only ever be None, so it promised
    information the API never sends.
    """
    from qbitflow.dto.transaction.session import LinkResponse

    response = LinkResponse(uuid="pay@1", link="https://pay")

    assert not hasattr(response, "expires_at")
    assert set(LinkResponse.model_fields) == {"uuid", "link"}


def test_subscription_session_accepts_an_inline_ghost_product(client, captured):
    """
    Subscriptions take the same product forms as a one-time payment. This used to raise
    "Either product_id or product_reference must be provided", blocking a form the API
    accepts (verified: a subscription session with only an inline product returns 201).
    """
    from qbitflow.utils.duration import Duration

    try:
        client.subscriptions.create_session(
            product_name="Pro plan",
            description="Monthly Pro subscription",
            price=29.0,
            frequency=Duration(value=1, unit="months"),
        )
    except Exception:
        pass

    body = captured[0]["data"]
    assert body["productName"] == "Pro plan"
    assert body["price"] == 29.0
    assert captured[0]["endpoint"] == "/transaction/session-checkout/new/subscription"


def test_subscription_session_still_requires_some_product(client, captured):
    from qbitflow.utils.duration import Duration

    with pytest.raises(Exception):
        client.subscriptions.create_session(frequency=Duration(value=1, unit="months"))


def test_get_session_omits_close_to_expire_error_by_default(client, captured):
    """
    The API defaults this to true. Sending false on every call suppressed the "session
    close to expiry" error that JS and PHP surface, so the same call behaved differently
    depending on the SDK.
    """
    try:
        client.one_time_payments.get_session("pay@1")
    except Exception:
        pass

    # An empty param dict is normalised to None before the request, so either shape means
    # "not sent" — what matters is that the key is absent and the API default applies.
    assert not (captured[0]["params"] or {})


def test_get_session_sends_close_to_expire_error_when_set(client, captured):
    try:
        client.one_time_payments.get_session("pay@1", close_to_expire_error=True)
    except Exception:
        pass

    assert captured[0]["params"] == {"closeToExpireError": "true"}
