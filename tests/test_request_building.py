"""
Offline tests for URL construction, argument guards and request bodies.

No API key and no server needed: ``_send`` (the transport) is stubbed so the endpoint, method
and body each handler builds can be asserted directly.

Run with:
    pytest tests/test_request_building.py -v
"""

import httpx
import pytest

from qbitflow import QBitFlow
from qbitflow.dto.transaction.status import TransactionType
from qbitflow.exceptions import ValidationError
from qbitflow.utils.duration import Duration


@pytest.fixture
def client():
    client = QBitFlow(api_key="sk_dummy_offline_tests", base_url="http://api.test")
    yield client
    client.close()


@pytest.fixture
def captured(monkeypatch):
    """Capture the endpoint each request handler builds, without issuing a request."""
    calls = []

    def fake_send(self, endpoint, method, data, params, *, retriable):
        calls.append(
            {
                "endpoint": endpoint,
                "method": method,
                "data": data,
                "params": params,
                "retriable": retriable,
                "headers": dict(self.headers),
            }
        )
        return httpx.Response(200, json={})

    monkeypatch.setattr("qbitflow.requests.base_request.BaseRequest._send", fake_send)
    return calls


def attempt(fn):
    """Run a call whose stubbed ({}) response may not fit its return type; the request matters."""
    try:
        fn()
    except Exception:
        pass


# ── Path escaping ────────────────────────────────────────────────────────────


def test_reference_with_slashes_stays_one_segment(client, captured):
    """
    A reference comes straight from the caller's own order system. Interpolated raw, the
    slashes make it address a different route entirely.
    """
    attempt(lambda: client.products.get_by_reference("ORD/2026/17"))

    assert captured[0]["endpoint"] == "/product/reference/ORD%2F2026%2F17"


@pytest.mark.parametrize(
    ("call", "expected"),
    [
        (lambda c: c.customers.get("a/b"), "/customer/uuid/a%2Fb"),
        (lambda c: c.customers.get_by_reference("a/b"), "/customer/reference/a%2Fb"),
        (lambda c: c.customers.get_by_email("a/b@x.com"), "/customer/email/a%2Fb%40x.com"),
        (lambda c: c.customers.delete("a/b"), "/customer/uuid/a%2Fb"),
        (lambda c: c.one_time_payments.get("a/b"), "/transaction/payment/a%2Fb"),
        (
            lambda c: c.one_time_payments.get_by_reference("a/b"),
            "/transaction/payment/reference/a%2Fb",
        ),
        (
            lambda c: c.one_time_payments.get_customer_for_transaction("a/b"),
            "/transaction/customer/a%2Fb",
        ),
        (lambda c: c.one_time_payments.get_session("a/b"), "/transaction/session-checkout/a%2Fb"),
        (lambda c: c.subscriptions.get("a/b"), "/transaction/subscription/a%2Fb"),
        (
            lambda c: c.subscriptions.get_by_reference("a/b"),
            "/transaction/subscription/reference/subscription/a%2Fb",
        ),
        (
            lambda c: c.subscriptions.get_payment_history("a/b"),
            "/transaction/subscription/history/a%2Fb",
        ),
        (
            lambda c: c.subscriptions.force_cancel("a/b"),
            "/transaction/subscription/processing/force-cancel/a%2Fb",
        ),
        (
            lambda c: c.refunds.get_by_transaction("a/b"),
            "/transaction/refunds/by-transaction/a%2Fb",
        ),
        (lambda c: c.users.get_by_email("a/b@x.com"), "/user/email/a%2Fb%40x.com"),
    ],
)
def test_escaping_covers_every_user_supplied_segment(client, captured, call, expected):
    attempt(lambda: call(client))

    assert captured[0]["endpoint"] == expected


def test_prefixed_identifiers_survive_escaping(client, captured):
    """
    The API's own identifiers carry a ``pay@`` prefix. Escaping ``@`` to ``%40`` is fine —
    the server decodes path params — but the identifier must still round-trip intact.
    """
    attempt(lambda: client.one_time_payments.get("pay@550e8400-e29b-41d4-a716-446655440000"))

    endpoint = captured[0]["endpoint"]
    assert endpoint == "/transaction/payment/pay%40550e8400-e29b-41d4-a716-446655440000"


# ── Argument guards: one wording, every method ───────────────────────────────


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.customers.get(""),
        lambda c: c.customers.get("   "),
        lambda c: c.customers.get_by_reference(""),
        lambda c: c.customers.update(
            "", __import__("qbitflow.dto.customer", fromlist=["x"]).UpdateCustomerDto()
        ),
        lambda c: c.customers.delete(""),
        lambda c: c.products.get_by_reference(""),
        lambda c: c.one_time_payments.get(""),
        lambda c: c.one_time_payments.get_by_reference(""),
        lambda c: c.one_time_payments.get_session(""),
        lambda c: c.one_time_payments.get_customer_for_transaction(""),
        lambda c: c.subscriptions.get(""),
        lambda c: c.subscriptions.get_by_reference(""),
        lambda c: c.subscriptions.get_session(""),
        lambda c: c.subscriptions.get_payment_history(""),
        lambda c: c.subscriptions.force_cancel(""),
        lambda c: c.subscriptions.execute_test_billing_cycle(""),
        lambda c: c.refunds.get_by_transaction(""),
        lambda c: c.transaction_status.get("", TransactionType.ONE_TIME_PAYMENT),
    ],
)
def test_empty_identifiers_are_rejected_before_any_request(client, captured, call):
    with pytest.raises(ValidationError, match="cannot be empty"):
        call(client)

    assert captured == []


@pytest.mark.parametrize("bad", [0, -1, True])
@pytest.mark.parametrize(
    "call",
    [
        lambda c, v: c.products.get(v),
        lambda c, v: c.products.update(
            v, __import__("qbitflow.dto.product", fromlist=["x"]).UpdateProductDto()
        ),
        lambda c, v: c.products.delete(v),
        lambda c, v: c.users.get_by_id(v),
        lambda c, v: c.users.update(
            v, __import__("qbitflow.dto.user", fromlist=["x"]).UpdateUserDto()
        ),
        lambda c, v: c.users.delete(v),
        lambda c, v: c.api_keys.get_for_user(v),
        lambda c, v: c.claims.get_request_by_user(v),
        lambda c, v: c.claims.create_request(v),
        lambda c, v: c.claims.trigger_test_claim_funds(v),
    ],
)
def test_non_positive_numeric_ids_are_rejected_before_any_request(client, captured, call, bad):
    with pytest.raises(ValidationError, match="positive integer"):
        call(client, bad)

    assert captured == []


@pytest.mark.parametrize(
    "email", ["", "no-at-sign", "a@b", "a b@c.com", "@x.com", "a@.com", "a@@b.com"]
)
@pytest.mark.parametrize(
    "call", [lambda c, e: c.customers.get_by_email(e), lambda c, e: c.users.get_by_email(e)]
)
def test_email_lookups_use_the_email_rule(client, captured, call, email):
    with pytest.raises(ValidationError, match="valid email"):
        call(client, email)

    assert captured == []


def test_transaction_type_must_be_the_enum(client, captured):
    with pytest.raises(ValidationError, match="TransactionType"):
        client.transaction_status.get("pay@1", "not-a-type")  # type: ignore[arg-type]

    attempt(lambda: client.transaction_status.get("pay@1", "payment"))  # exact value is accepted
    assert captured[0]["params"] == {"txUUID": "pay@1", "txType": "payment"}


# ── Retry flag on action routes ──────────────────────────────────────────────


def test_action_gets_are_marked_non_retriable(client, captured):
    attempt(lambda: client.subscriptions.force_cancel("sub@1"))
    attempt(lambda: client.subscriptions.execute_test_billing_cycle("sub@1"))
    attempt(lambda: client.claims.trigger_test_claim_funds(3))
    attempt(lambda: client.subscriptions.get("sub@1"))

    assert [c["retriable"] for c in captured] == [False, False, False, None]


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


def test_dead_types_are_gone():
    import qbitflow.dto as dto
    import qbitflow.dto.transaction as tx

    assert not hasattr(dto, "ClaimRequest")
    assert not hasattr(tx, "StatusLinkResponse")
    assert not hasattr(tx.status, "StatusResponse")
    assert not hasattr(tx, "StatusResponseError")
    assert not hasattr(tx.status, "StatusResponseError")


def test_there_is_no_websocket_helper(client):
    """`/transaction/status/ws` is internal to the checkout page; merchants use webhooks."""
    assert not hasattr(client.transaction_status, "get_websocket_url")
    assert not any("websocket" in name.lower() for name in dir(client.transaction_status))


def test_subscription_session_accepts_an_inline_ghost_product(client, captured):
    """
    Subscriptions take the same product forms as a one-time payment. This used to raise
    "Either product_id or product_reference must be provided", blocking a form the API
    accepts (verified: a subscription session with only an inline product returns 201).
    """
    attempt(
        lambda: client.subscriptions.create_session(
            product_name="Pro plan",
            description="Monthly Pro subscription",
            price=29.0,
            frequency=Duration(value=1, unit="months"),
        )
    )

    body = captured[0]["data"]
    assert body["productName"] == "Pro plan"
    assert body["price"] == 29.0
    assert body["frequency"] == {"value": 1, "unit": "months"}
    assert "productId" not in body, "unset optionals are omitted, not sent as null"
    assert captured[0]["endpoint"] == "/transaction/session-checkout/new/subscription"
    assert captured[0]["method"] == "POST"


def test_subscription_session_still_requires_some_product(client, captured):
    with pytest.raises(ValidationError, match="product_id, product_reference"):
        client.subscriptions.create_session(frequency=Duration(value=1, unit="months"))

    assert captured == []


def test_subscription_session_requires_a_frequency(client, captured):
    with pytest.raises(ValidationError) as exc_info:
        client.subscriptions.create_session(product_id=1)

    assert any(f.field == "frequency" for f in exc_info.value.fields)
    assert captured == []


def test_session_argument_errors_are_the_sdk_validation_type_with_fields(client, captured):
    """A pydantic failure on the kwargs is reported as the SDK's ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        client.one_time_payments.create_session(
            product_id=0, product_name="<b>", success_url="javascript:alert(1)"
        )

    fields = {f.field for f in exc_info.value.fields}
    assert {"product_id", "product_name", "success_url"} <= fields
    assert exc_info.value.status_code is None
    assert captured == []


def test_payment_session_body_omits_unset_and_empty_optionals(client, captured):
    attempt(
        lambda: client.one_time_payments.create_session(
            product_id=339, success_url="", customer_uuid="", reference=""
        )
    )

    assert captured[0]["data"] == {"productId": 339}


def test_get_session_omits_close_to_expire_error_by_default(client, captured):
    """
    The API defaults this to true. Sending false on every call suppressed the "session
    close to expiry" error that JS and PHP surface, so the same call behaved differently
    depending on the SDK.
    """
    attempt(lambda: client.one_time_payments.get_session("pay@1"))

    # An empty param dict is normalised to None before the request, so either shape means
    # "not sent" — what matters is that the key is absent and the API default applies.
    assert not (captured[0]["params"] or {})


def test_get_session_sends_close_to_expire_error_when_set(client, captured):
    attempt(lambda: client.one_time_payments.get_session("pay@1", close_to_expire_error=True))

    assert captured[0]["params"] == {"closeToExpireError": "true"}


def test_accounting_export_validates_dates_order_and_format_locally(client, captured):
    with pytest.raises(ValidationError, match="YYYY-MM-DD"):
        client.accounting.export("01/01/2026", "2026-02-01", "json")
    with pytest.raises(ValidationError, match="YYYY-MM-DD"):
        client.accounting.export("２０２６-01-01", "2026-02-01", "json")
    with pytest.raises(ValidationError, match="not be after"):
        client.accounting.export("2026-03-01", "2026-02-01", "json")
    with pytest.raises(ValidationError, match="format"):
        client.accounting.export("2026-01-01", "2026-02-01", "xml")  # type: ignore[arg-type]
    with pytest.raises(ValidationError, match="calendar"):
        client.accounting.export("2026-02-30", "2026-03-01", "json")
    with pytest.raises(ValidationError, match="empty"):
        client.accounting.export("", "2026-03-01", "json")

    assert captured == []


def test_accounting_export_leaves_the_window_length_to_the_server(client, captured):
    """The live server accepts spans of up to 95 days; the docs' 3-month rule is not enforced."""
    client.accounting.export("2026-01-31", "2026-05-05", "csv")
    attempt(lambda: client.accounting.export("2026-06-01", "2026-06-01", "json"))

    assert captured[0]["params"] == {"from": "2026-01-31", "to": "2026-05-05", "format": "csv"}
    assert captured[1]["params"]["from"] == captured[1]["params"]["to"]


# ── Session creation rules (live-verified against the API) ───────────────────


@pytest.mark.parametrize("price", [0, 0.0, -1, float("nan"), float("inf"), True, "9.99"])
def test_inline_session_price_must_be_finite_and_positive(client, captured, price):
    with pytest.raises(ValidationError, match="price"):
        client.one_time_payments.create_session(
            product_name="Coffee", description="A cup", price=price
        )

    assert captured == []


def test_inline_session_with_a_positive_price_is_sent(client, captured):
    attempt(
        lambda: client.one_time_payments.create_session(
            product_name="Coffee", description="A cup", price=2.5
        )
    )

    assert captured[0]["data"] == {"productName": "Coffee", "description": "A cup", "price": 2.5}


@pytest.mark.parametrize(
    "bad",
    [
        "not-a-uuid",
        "pay@01997c89-d0e9-7c9a-9886-fe7709919695",
        "01997c89d0e97c9a9886fe7709919695",
        " 01997c89-d0e9-7c9a-9886-fe7709919695",
    ],
)
def test_customer_uuid_must_be_a_bare_uuid(client, captured, bad):
    with pytest.raises(ValidationError, match="customer_uuid"):
        client.one_time_payments.create_session(product_id=1, customer_uuid=bad)

    assert captured == []


def test_a_bare_customer_uuid_in_any_case_is_sent(client, captured):
    uuid = "01997C89-D0E9-7C9A-9886-FE7709919695"
    attempt(lambda: client.one_time_payments.create_session(product_id=1, customer_uuid=uuid))

    assert captured[0]["data"] == {"productId": 1, "customerUUID": uuid}


@pytest.mark.parametrize("url", ["HTTPS://shop.example/ok", "http://checkout-web/done"])
def test_redirect_url_scheme_is_case_insensitive(client, captured, url):
    attempt(lambda: client.one_time_payments.create_session(product_id=1, success_url=url))

    assert captured[0]["data"]["successUrl"] == url


@pytest.mark.parametrize("url", ["https://:443/x", "/relative", "javascript:alert(1)", "ftp://x/y"])
def test_redirect_url_needs_an_http_scheme_and_a_host(client, captured, url):
    with pytest.raises(ValidationError, match="cancel_url"):
        client.one_time_payments.create_session(product_id=1, cancel_url=url)

    assert captured == []


def test_subscription_trial_and_min_periods_accept_zero(client, captured):
    attempt(
        lambda: client.subscriptions.create_session(
            product_id=1,
            frequency=Duration(value=1, unit="months"),
            trial_period=Duration(value=0, unit="days"),
            min_periods=0,
        )
    )

    body = captured[0]["data"]
    assert body["trialPeriod"] == {"value": 0, "unit": "days"}
    assert "minPeriods" not in body, "min_periods=0 means no minimum and is omitted"


def test_subscription_min_periods_is_sent_when_set(client, captured):
    attempt(
        lambda: client.subscriptions.create_session(
            product_id=1, frequency=Duration(value=1, unit="weeks"), min_periods=3
        )
    )

    assert captured[0]["data"]["minPeriods"] == 3


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"frequency": Duration(value=0, unit="months")}, "at least 1"),
        ({"frequency": {"value": 4294967296, "unit": "days"}}, "between 0 and 4294967295"),
        ({"frequency": {"value": 1, "unit": "fortnights"}}, "unit"),
        ({"frequency": {"value": 1.5, "unit": "days"}}, "integer"),
        ({"frequency": Duration(value=1, unit="days"), "min_periods": -1}, "min_periods"),
        (
            {"frequency": Duration(value=1, unit="days"), "min_periods": 4294967296},
            "min_periods",
        ),
        ({"frequency": Duration(value=1, unit="days"), "min_periods": True}, "min_periods"),
    ],
)
def test_subscription_duration_and_periods_are_checked(client, captured, kwargs, match):
    with pytest.raises(ValidationError, match=match):
        client.subscriptions.create_session(product_id=1, **kwargs)

    assert captured == []


@pytest.mark.parametrize("value", [-1, 4294967296, True, "3"])
def test_duration_itself_raises_the_sdk_validation_error(value):
    with pytest.raises(ValidationError, match="Duration value"):
        Duration(value=value, unit="days")


def test_session_getters_check_the_session_kind(client, monkeypatch):
    responses = {
        "pay@1": {"uuid": "pay@1", "txType": "payment"},
        "sub@1": {"uuid": "sub@1", "txType": "createSubscription", "frequency": 60},
    }

    def fake_send(self, endpoint, method, data, params, *, retriable):
        return httpx.Response(200, json=responses[endpoint.rsplit("/", 1)[-1].replace("%40", "@")])

    monkeypatch.setattr("qbitflow.requests.base_request.BaseRequest._send", fake_send)

    assert client.one_time_payments.get_session("pay@1").uuid == "pay@1"
    assert client.subscriptions.get_session("sub@1").frequency == 60
    with pytest.raises(ValidationError, match="subscriptions.get_session"):
        client.one_time_payments.get_session("sub@1")
    with pytest.raises(ValidationError, match="one_time_payments.get_session"):
        client.subscriptions.get_session("pay@1")


# ── Cursor parameters ───────────────────────────────────────────────────────


@pytest.mark.parametrize("limit", [0, -3, True, 2.0, "10"])
def test_cursor_limit_must_be_a_positive_integer(client, captured, limit):
    with pytest.raises(ValidationError, match="limit"):
        client.customers.get_all(limit=limit)

    assert captured == []


def test_cursor_params_omit_an_empty_cursor(client, captured):
    client.customers.get_all(limit=5, cursor="")
    client.refunds.get_all_inactive(cursor="abc")

    assert captured[0]["params"] == {"limit": 5}
    assert captured[1]["params"] == {"cursor": "abc"}


# ── Client-level On-Behalf-Of reaches the wire ──────────────────────────────


def test_client_level_on_behalf_of_header_is_sent_by_every_service(client, captured):
    scoped = client.on_behalf_of(31)

    attempt(lambda: scoped.products.get_all())
    scoped.customers.get_all()
    attempt(lambda: scoped.one_time_payments.get_session("pay@1"))
    attempt(lambda: scoped.claims.get_funds())
    scoped.webhooks.verify(b"{}", "sha256=x", "1")

    assert [c["headers"].get("On-Behalf-Of") for c in captured] == ["31"] * 5

    attempt(lambda: client.products.get_all())
    assert "On-Behalf-Of" not in captured[-1]["headers"]
