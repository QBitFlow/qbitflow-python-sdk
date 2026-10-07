"""
End-to-end tests of the request layer against an in-process ``httpx.MockTransport``.

Unlike ``test_error_parsing.py`` (which calls ``_handle_http_status`` directly) these drive
real requests through ``_make_request`` / ``_make_raw_request``, so the retry loop, the
re-raise path and the status mapping are exercised exactly as a caller sees them. This is
the layer where 2.5.0's headline fix lives: a 400 must reach the caller as
``ValidationError`` with its status code and fields — not re-wrapped into an anonymous
``APIError``.

No API key and no server needed.

Run with:
    pytest tests/test_transport.py -v
"""

import json
from typing import Any, Callable, Dict, List, Optional

import httpx
import pytest

from qbitflow import QBitFlow
from qbitflow.exceptions import (
    APIError,
    AuthenticationError,
    ConflictError,
    ForbiddenException,
    InvalidRequestError,
    NetworkError,
    NotFoundException,
    QBitFlowError,
    RateLimitError,
    ServerError,
    ValidationError,
)
from qbitflow.requests import base_request

BASE_URL = "http://api.test"

VALIDATION_BODY = {
    "errors": [
        {"field": "ProductName", "message": "ProductName is too short"},
        {"field": "Price", "message": "Price is too short"},
    ]
}


class Recorder:
    """Scripted transport: answers from a queue and records every request it saw."""

    def __init__(self, responses: List[Any]):
        self.responses = list(responses)
        self.requests: List[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        nxt = self.responses.pop(0) if self.responses else httpx.Response(200, json={})
        if isinstance(nxt, Exception):
            raise nxt
        if callable(nxt):
            return nxt(request)
        return nxt


def make_client(
    recorder: Recorder, *, max_retries: Optional[int] = None, timeout: Optional[float] = None
) -> QBitFlow:
    client = QBitFlow(
        "sk_dummy_offline_tests", base_url=BASE_URL, max_retries=max_retries, timeout=timeout
    )
    # Swap the shared pool for one wired to the scripted transport.
    client._http = httpx.Client(transport=httpx.MockTransport(recorder.handler))
    for name in (
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
    ):
        handler = getattr(client, name)
        handler._client = client._http
        if hasattr(handler, "_session"):
            handler._session._client = client._http
    return client


@pytest.fixture
def no_sleep(monkeypatch):
    """Record backoff waits instead of sleeping."""
    waits: List[float] = []
    monkeypatch.setattr(base_request, "_sleep", waits.append)
    return waits


def error(status: int, body: Optional[Dict[str, Any]] = None, **headers: str) -> httpx.Response:
    return httpx.Response(
        status, json=body if body is not None else {"error": "x"}, headers=headers
    )


# ── Status → type, end to end ───────────────────────────────────────────────


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (400, ValidationError),
        (422, ValidationError),
        (401, AuthenticationError),
        (403, ForbiddenException),
        (404, NotFoundException),
        (409, ConflictError),
        (429, RateLimitError),
        (405, InvalidRequestError),
        (418, InvalidRequestError),
        (500, ServerError),
        (503, ServerError),
        (301, ServerError),
        (302, ServerError),
    ],
)
def test_status_maps_to_its_own_type_through_make_request(status, expected, no_sleep):
    rec = Recorder([error(status, VALIDATION_BODY)] * 10)
    client = make_client(rec, max_retries=0)

    with pytest.raises(expected) as exc_info:
        client.products.get_all()

    err = exc_info.value
    assert type(err) is expected, "must be the exact type, not a re-wrapped APIError"
    assert err.status_code == status
    assert [f.field for f in err.fields] == ["ProductName", "Price"]
    assert "ProductName is too short" in err.message and "Price is too short" in err.message


def test_a_400_is_never_rewrapped_into_an_anonymous_api_error(no_sleep):
    """The 2.1.0 → 2.5.0 regression: ValidationError fell through to ``except Exception``."""
    rec = Recorder([error(400, {"error": "bad request"})])
    client = make_client(rec)

    with pytest.raises(QBitFlowError) as exc_info:
        client.products.get_all()

    assert isinstance(exc_info.value, ValidationError)
    assert not type(exc_info.value) is APIError
    assert exc_info.value.status_code == 400
    assert "Unexpected error" not in exc_info.value.message


def test_rate_limit_exposes_retry_after_and_is_not_retried(no_sleep):
    rec = Recorder([error(429, {"error": "slow down"}, **{"Retry-After": "7"})] * 5)
    client = make_client(rec)

    with pytest.raises(RateLimitError) as exc_info:
        client.products.get_all()

    assert exc_info.value.retry_after == 7
    assert exc_info.value.response == {"retry_after": 7}
    assert len(rec.requests) == 1, "429 must never be retried"
    assert no_sleep == []


def test_rate_limit_without_header_has_none_retry_after(no_sleep):
    client = make_client(Recorder([error(429, {"error": "slow down"})]))

    with pytest.raises(RateLimitError) as exc_info:
        client.products.get_all()

    assert exc_info.value.retry_after is None
    assert exc_info.value.response is None


def test_redirect_is_a_server_error_mentioning_base_url(no_sleep):
    rec = Recorder([httpx.Response(302, headers={"Location": "https://elsewhere.test/v1"})] * 3)
    client = make_client(rec)

    with pytest.raises(ServerError) as exc_info:
        client.products.get_all()

    assert exc_info.value.status_code == 302
    assert "base_url" in exc_info.value.message
    assert "https://elsewhere.test/v1" in exc_info.value.message
    assert len(rec.requests) == 1, "3xx must never be retried, nor followed"
    assert str(rec.requests[0].url) == f"{BASE_URL}/product/"


def test_redirects_are_not_followed_by_the_real_client():
    """The shared pool itself must not follow redirects (a Location with a real target)."""
    client = QBitFlow("sk_dummy_offline_tests", base_url=BASE_URL)
    try:
        assert client._http.follow_redirects is False
    finally:
        client.close()


@pytest.mark.parametrize("body", [b"", b"   ", b"\n"])
def test_empty_2xx_body_is_a_server_error(body, no_sleep):
    client = make_client(Recorder([httpx.Response(200, content=body)]))

    with pytest.raises(ServerError) as exc_info:
        client.products.get(1)

    assert exc_info.value.status_code == 200
    assert "empty body" in exc_info.value.message


def test_204_is_not_an_error(no_sleep):
    client = make_client(Recorder([httpx.Response(204), httpx.Response(204)]))

    assert client.products.delete(1).message == ""
    assert client.products.get_all() == []


def test_null_json_for_an_object_is_a_server_error(no_sleep):
    client = make_client(Recorder([httpx.Response(200, content=b"null")]))

    with pytest.raises(ServerError) as exc_info:
        client.products.get(1)

    assert exc_info.value.status_code == 200


def test_non_json_2xx_is_a_server_error(no_sleep):
    rec = Recorder([httpx.Response(200, text="<html>proxy error page</html>")])
    client = make_client(rec)

    with pytest.raises(ServerError) as exc_info:
        client.products.get_all()

    assert exc_info.value.status_code == 200
    assert exc_info.value.response == {"raw": "<html>proxy error page</html>"}


def test_response_shape_mismatch_is_a_server_error_with_the_status(no_sleep):
    """A field of the wrong JSON type is a response-shape failure, never a bare pydantic error."""
    rec = Recorder([httpx.Response(200, json={"id": "not-a-number", "name": 7})])
    client = make_client(rec)

    with pytest.raises(ServerError) as exc_info:
        client.products.get(1)

    assert "Product" in exc_info.value.message
    assert exc_info.value.status_code == 200
    assert exc_info.value.response == {"raw": {"id": "not-a-number", "name": 7}}
    assert exc_info.value.__cause__ is not None


@pytest.mark.parametrize(
    ("call", "body"),
    [
        (lambda c: c.products.get_all(), {"not": "a list"}),
        (lambda c: c.customers.get_all(), {"items": {"not": "a list"}}),
        (lambda c: c.customers.get_all(), {"items": [{"uuid": 5}]}),
        (lambda c: c.subscriptions.get("sub@1"), {"currency": "USDC"}),
        (lambda c: c.one_time_payments.get("pay@1"), {"metadata": []}),
        (lambda c: c.one_time_payments.get_session("pay@1"), {"txType": "payment", "price": "9"}),
        (lambda c: c.refunds.get_all(), [{"status": 3}]),
    ],
)
def test_wrong_json_types_are_server_errors_carrying_the_status(call, body, no_sleep):
    client = make_client(Recorder([httpx.Response(201, json=body)]))

    with pytest.raises(ServerError) as exc_info:
        call(client)

    assert exc_info.value.status_code == 201


def test_unknown_keys_are_ignored(no_sleep):
    client = make_client(Recorder([httpx.Response(200, json={"id": 3, "brandNew": {"x": 1}})]))

    assert client.products.get(3).id == 3


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.products.get_all(),
        lambda c: c.users.get_all(),
        lambda c: c.api_keys.get_all(),
        lambda c: c.refunds.get_all(),
        lambda c: c.claims.get_funds(),
        lambda c: c.currencies.get_all_available(),
        lambda c: c.subscriptions.get_payment_history("sub@1"),
        lambda c: c.accounting.export("2026-01-01", "2026-01-31", "json"),
    ],
)
def test_null_top_level_lists_are_empty_lists(call, no_sleep):
    """A Go nil slice is serialised as `null`; that is an empty list, not an error."""
    client = make_client(Recorder([httpx.Response(200, content=b"null")]))

    assert call(client) == []


@pytest.mark.parametrize("body", [{"items": None, "nextCursor": None}, {}])
def test_null_or_absent_cursor_items_are_an_empty_page(body, no_sleep):
    client = make_client(Recorder([httpx.Response(200, json=body)] * 4))

    for page in (
        client.customers.get_all(),
        client.one_time_payments.get_all(),
        client.one_time_payments.get_all_combined(),
        client.refunds.get_all_inactive(),
    ):
        assert page.items == [] and page.next_cursor is None and not page.has_more()


def test_server_error_is_an_api_error_for_backwards_compatible_handlers(no_sleep):
    client = make_client(Recorder([error(500)]), max_retries=0)

    with pytest.raises(APIError):
        client.products.get_all()


# ── Message precedence ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (
            httpx.Response(
                400, json={"error": "First", "errors": [{"field": "a", "message": "b"}]}
            ),
            "First",
        ),
        (
            httpx.Response(400, json=VALIDATION_BODY),
            "ProductName: ProductName is too short; Price: Price is too short",
        ),
        (httpx.Response(400, json={"message": "Synthesised"}), "Synthesised"),
        (httpx.Response(400, text="plain body"), "plain body"),
        (httpx.Response(400, text=""), "Bad Request"),
        (httpx.Response(400, json={}), "Bad Request"),
    ],
)
def test_message_precedence(response, expected, no_sleep):
    client = make_client(Recorder([response]))

    with pytest.raises(ValidationError) as exc_info:
        client.products.get_all()

    assert exc_info.value.message == expected


# ── Retry policy ─────────────────────────────────────────────────────────────


def test_get_retries_5xx_with_exponential_backoff_then_succeeds(no_sleep):
    rec = Recorder([error(500), error(502), httpx.Response(200, json=[])])
    client = make_client(rec)  # default max_retries = 3

    assert client.products.get_all() == []
    assert len(rec.requests) == 3
    assert no_sleep == [1.0, 2.0]


def test_get_gives_up_after_max_retries(no_sleep):
    rec = Recorder([error(503)] * 10)
    client = make_client(rec, max_retries=3)

    with pytest.raises(ServerError) as exc_info:
        client.products.get_all()

    assert exc_info.value.status_code == 503
    assert len(rec.requests) == 4  # 1 + 3 retries
    assert no_sleep == [1.0, 2.0, 4.0]


def test_max_retries_zero_disables_retries(no_sleep):
    """``max_retries=0`` used to be coalesced to the default 3 by ``or``."""
    rec = Recorder([error(500)] * 5)
    client = make_client(rec, max_retries=0)

    with pytest.raises(ServerError):
        client.products.get_all()

    assert len(rec.requests) == 1
    assert client.products.max_retries == 0


def test_timeout_zero_is_honoured():
    client = QBitFlow("sk_dummy_offline_tests", base_url=BASE_URL, timeout=0)
    assert client.products.timeout == 0
    client.close()


@pytest.mark.parametrize("bad", [-1, -3])
def test_negative_max_retries_is_rejected(bad):
    with pytest.raises(ValidationError):
        QBitFlow("sk_dummy_offline_tests", base_url=BASE_URL, max_retries=bad)


def test_get_retries_network_errors(no_sleep):
    rec = Recorder(
        [
            httpx.ConnectError("refused"),
            httpx.ReadTimeout("slow"),
            httpx.Response(200, json=[]),
        ]
    )
    client = make_client(rec)

    assert client.products.get_all() == []
    assert len(rec.requests) == 3
    assert no_sleep == [1.0, 2.0]


@pytest.mark.parametrize(
    "failure",
    [
        httpx.RemoteProtocolError("Server disconnected without sending a response."),
        httpx.LocalProtocolError("bad state"),
        httpx.ProxyError("proxy down"),
        httpx.ReadError("reset"),
        httpx.WriteError("broken pipe"),
        httpx.PoolTimeout("pool exhausted"),
    ],
)
def test_get_retries_every_transport_failure(failure, no_sleep):
    """A dropped keep-alive connection ("server disconnected") is the most common one."""
    rec = Recorder([failure, httpx.Response(200, json=[])])
    client = make_client(rec)

    assert client.products.get_all() == []
    assert len(rec.requests) == 2
    assert no_sleep == [1.0]


def test_transport_failure_after_budget_is_a_network_error(no_sleep):
    rec = Recorder([httpx.RemoteProtocolError("disconnected")] * 5)
    client = make_client(rec, max_retries=2)

    with pytest.raises(NetworkError):
        client.products.get_all()

    assert len(rec.requests) == 3


def test_unsupported_protocol_is_not_retried(no_sleep):
    rec = Recorder([httpx.UnsupportedProtocol("no scheme")] * 5)
    client = make_client(rec)

    with pytest.raises(NetworkError, match="base_url"):
        client.products.get_all()

    assert len(rec.requests) == 1
    assert no_sleep == []


def test_a_base_url_without_scheme_fails_fast():
    client = QBitFlow("sk_dummy_offline_tests", base_url="api.qbitflow.app/v1", max_retries=3)
    try:
        with pytest.raises(NetworkError, match="base_url"):
            client.products.get_all()
    finally:
        client.close()


def test_network_error_after_budget_is_a_network_error(no_sleep):
    rec = Recorder([httpx.ConnectError("refused")] * 10)
    client = make_client(rec, max_retries=2)

    with pytest.raises(NetworkError):
        client.products.get_all()

    assert len(rec.requests) == 3


def test_timeout_after_budget_mentions_the_timeout(no_sleep):
    rec = Recorder([httpx.ReadTimeout("slow")] * 10)
    client = make_client(rec, max_retries=1, timeout=7)

    with pytest.raises(NetworkError) as exc_info:
        client.products.get_all()

    assert "timeout" in exc_info.value.message.lower()
    assert "7" in exc_info.value.message


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.customers.create(
            __import__("qbitflow.dto.customer", fromlist=["CreateCustomerDto"]).CreateCustomerDto(
                name="John", last_name="Doe", email="j@example.com"
            )
        ),
        lambda c: c.one_time_payments.create_session(product_id=1),
        lambda c: c.products.update(
            1,
            __import__("qbitflow.dto.product", fromlist=["UpdateProductDto"]).UpdateProductDto(
                price=2
            ),
        ),
        lambda c: c.products.delete(1),
    ],
)
def test_post_put_delete_are_never_retried(call, no_sleep):
    """A timed-out session creation must never be silently sent twice."""
    rec = Recorder([error(500)] * 5)
    client = make_client(rec)  # retries enabled

    with pytest.raises(ServerError):
        call(client)

    assert len(rec.requests) == 1
    assert rec.requests[0].method in ("POST", "PUT", "DELETE")
    assert no_sleep == []


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.subscriptions.force_cancel("sub@1"),
        lambda c: c.subscriptions.execute_test_billing_cycle("sub@1"),
        lambda c: c.claims.trigger_test_claim_funds(1),
    ],
)
def test_action_gets_are_never_retried(call, no_sleep):
    """force-cancel / execute-billing / test-trigger are GETs that perform an action."""
    rec = Recorder([httpx.ConnectError("refused")] * 5)
    client = make_client(rec)

    with pytest.raises(NetworkError):
        call(client)

    assert len(rec.requests) == 1
    assert no_sleep == []


def test_4xx_is_never_retried(no_sleep):
    rec = Recorder([error(404)] * 5)
    client = make_client(rec)

    with pytest.raises(NotFoundException):
        client.products.get(1)

    assert len(rec.requests) == 1


# ── Request shape ────────────────────────────────────────────────────────────


def test_headers_carry_api_key_and_user_agent(no_sleep):
    rec = Recorder([httpx.Response(200, json=[])])
    client = make_client(rec)
    client.products.get_all()

    sent = rec.requests[0].headers
    assert sent["X-API-Key"] == "sk_dummy_offline_tests"
    assert sent["User-Agent"] == f"qbitflow-python/{__import__('qbitflow').__version__}"
    assert sent["Accept"] == "application/json"


def test_base_url_is_used_and_trailing_slash_stripped(no_sleep):
    rec = Recorder([httpx.Response(200, json=[])])
    client = QBitFlow("sk_dummy_offline_tests", base_url="http://api.test/v9///")
    client._http = httpx.Client(transport=httpx.MockTransport(rec.handler))
    client.products._client = client._http

    client.products.get_all()

    assert str(rec.requests[0].url) == "http://api.test/v9/product/"
    assert client.base_url == "http://api.test/v9"


def test_base_url_reaches_nested_session_handler_and_scoped_copies():
    client = QBitFlow("sk_dummy_offline_tests", base_url="http://api.test/v9/")

    assert client.one_time_payments._session.base_url == "http://api.test/v9"
    assert client.subscriptions._session.base_url == "http://api.test/v9"
    assert client.products.on_behalf_of(3).base_url == "http://api.test/v9"
    assert client.one_time_payments.on_behalf_of(3)._session.base_url == "http://api.test/v9"
    client.close()


def test_without_base_url_the_module_setting_is_followed(monkeypatch):
    from qbitflow import config

    monkeypatch.setattr(config, "BASE_URL", "http://module.test/v1/")
    client = QBitFlow("sk_dummy_offline_tests")
    try:
        assert client.base_url == "http://module.test/v1"
        assert client.products._effective_base_url() == "http://module.test/v1"
        config.set_base_url("http://later.test/")
        assert client.products._effective_base_url() == "http://later.test"
    finally:
        client.close()


def test_blank_base_url_is_rejected():
    with pytest.raises(ValidationError):
        QBitFlow("sk_dummy_offline_tests", base_url="   ")


def test_handlers_share_one_http_client_and_close_closes_it():
    client = QBitFlow("sk_dummy_offline_tests", base_url=BASE_URL)
    pool = client._http
    assert client.products._client is pool
    assert client.one_time_payments._session._client is pool
    assert client.products.on_behalf_of(4)._client is pool

    with client:
        pass
    assert pool.is_closed


def test_scoped_copy_close_does_not_close_the_shared_pool():
    client = QBitFlow("sk_dummy_offline_tests", base_url=BASE_URL)
    client.products.on_behalf_of(4).close()
    assert not client._http.is_closed
    client.close()


def test_on_behalf_of_negative_is_rejected():
    client = QBitFlow("sk_dummy_offline_tests", base_url=BASE_URL)
    with pytest.raises(ValidationError):
        client.products.on_behalf_of(-1)
    client.close()


def test_create_bodies_omit_unset_optionals(no_sleep):
    from qbitflow.dto.customer import CreateCustomerDto

    rec = Recorder(
        [
            httpx.Response(
                200,
                json={
                    "uuid": "u",
                    "name": "John",
                    "lastName": "Doe",
                    "email": "j@example.com",
                    "createdAt": "2026-01-01T00:00:00Z",
                },
            )
        ]
    )
    client = make_client(rec)
    client.customers.create(
        CreateCustomerDto(name="John", last_name="Doe", email="j@example.com", phone_number="")
    )

    body = json.loads(rec.requests[0].content)
    assert body == {"name": "John", "lastName": "Doe", "email": "j@example.com"}
    assert rec.requests[0].headers["Content-Type"] == "application/json"


def test_request_bodies_are_revalidated_before_sending(no_sleep):
    """A value assigned after construction is still checked (and never sent)."""
    from qbitflow.dto.product import UpdateProductDto

    rec = Recorder([])
    client = make_client(rec)
    dto = UpdateProductDto(price=5)
    dto.price = 0

    with pytest.raises(ValidationError, match="price"):
        client.products.update(1, dto)

    assert rec.requests == []


def test_request_methods_accept_a_plain_mapping(no_sleep):
    rec = Recorder([httpx.Response(200, json={"id": 1})])
    client = make_client(rec)

    client.products.update(1, {"price": 12.5})

    assert json.loads(rec.requests[0].content) == {"price": 12.5}

    with pytest.raises(ValidationError):
        client.products.update(1, {"price": -1})
    with pytest.raises(ValidationError, match="UpdateProductDto"):
        client.products.update(1, 12)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_numbers_in_a_body_raise_the_sdk_validation_error(bad, no_sleep):
    rec = Recorder([])
    client = make_client(rec)

    with pytest.raises(ValidationError, match="cannot be encoded"):
        client.webhooks.verify({"value": bad}, "sha256=s", "1")

    assert rec.requests == []


def test_a_string_that_is_not_valid_utf8_raises_the_sdk_validation_error(no_sleep):
    from qbitflow.dto.customer import UpdateCustomerDto

    rec = Recorder([])
    client = make_client(rec)

    with pytest.raises(ValidationError, match="cannot be encoded"):
        client.customers.update("c-1", UpdateCustomerDto(address="lone \ud800 surrogate"))

    assert rec.requests == []


# ── webhooks.verify end to end ───────────────────────────────────────────────


def test_webhook_verify_returns_false_only_for_a_real_400(no_sleep):
    rec = Recorder([error(400, {"error": "signature mismatch"})])
    client = make_client(rec)

    assert client.webhooks.verify(b'{"a":1}', "sha256=bad", "1700000000") is False
    assert rec.requests[0].method == "POST"
    assert json.loads(rec.requests[0].content) == {
        "payload": {"a": 1},
        "receivedSignature": "sha256=bad",
        "receivedTimestamp": "1700000000",
    }


def test_webhook_verify_returns_true_on_200(no_sleep):
    client = make_client(Recorder([httpx.Response(200, json={"message": "webhook verified!"})]))
    assert client.webhooks.verify('{"a":1}', "sha256=good", "1700000000") is True


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (error(401), AuthenticationError),
        (error(403), ForbiddenException),
        (error(422), ValidationError),
        (error(500), ServerError),
        (httpx.ConnectError("down"), NetworkError),
    ],
)
def test_webhook_verify_propagates_everything_else(response, expected, no_sleep):
    """An outage must never look like a forged signature."""
    client = make_client(Recorder([response] * 5))

    with pytest.raises(expected):
        client.webhooks.verify(b'{"a":1}', "sha256=good", "1700000000")


@pytest.mark.parametrize("payload", [b"not json", "{", b'{"a":NaN}', '{"a":Infinity}', None])
def test_webhook_verify_rejects_an_invalid_payload_locally(payload, no_sleep):
    rec = Recorder([])
    client = make_client(rec)

    with pytest.raises(ValidationError):
        client.webhooks.verify(payload, "sha256=good", "1700000000")

    assert rec.requests == []


@pytest.mark.parametrize(
    ("payload", "sent"),
    [
        ({"a": {}, "b": []}, {"a": {}, "b": []}),
        ('{"a":{},"b":[]}', {"a": {}, "b": []}),
        ([1, {"x": None}], [1, {"x": None}]),
        ('{"s":"\\ud800"}', {"s": "\ufffd"}),
    ],
)
def test_webhook_verify_accepts_raw_or_decoded_payloads(payload, sent, no_sleep):
    rec = Recorder([httpx.Response(200, json={"message": "webhook verified!"})])
    client = make_client(rec)

    assert client.webhooks.verify(payload, "sha256=good", "1700000000") is True
    assert json.loads(rec.requests[0].content)["payload"] == sent


# ── execute-billing shape ────────────────────────────────────────────────────


def test_execute_test_billing_cycle_returns_the_json_message(no_sleep):
    rec = Recorder([httpx.Response(200, json={"message": "Billing executed successfully"})])
    client = make_client(rec)

    result = client.subscriptions.execute_test_billing_cycle("sub@1")

    assert result.message == "Billing executed successfully"
    assert str(rec.requests[0].url).endswith("/processing/execute-billing/sub%401")


def test_execute_test_billing_not_due_is_a_conflict(no_sleep):
    rec = Recorder([error(409, {"error": "Subscription is not due for billing yet"})])
    client = make_client(rec)

    with pytest.raises(ConflictError) as exc_info:
        client.subscriptions.execute_test_billing_cycle("sub@1")

    assert exc_info.value.status_code == 409
    assert "not due" in exc_info.value.message


# ── Raw (CSV) path shares the same behaviour ─────────────────────────────────


def test_csv_export_returns_text_and_maps_errors(no_sleep):
    rec = Recorder([httpx.Response(200, text="paymentId,type\npay@1,payment\n")])
    client = make_client(rec)
    assert client.accounting.export("2026-01-01", "2026-03-31", "csv").startswith("paymentId")

    client = make_client(Recorder([error(403)]))
    with pytest.raises(ForbiddenException):
        client.accounting.export("2026-01-01", "2026-03-31", "csv")


def test_csv_export_parses_a_json_error_body(no_sleep):
    body = {"error": "'to' date cannot be more than 3 months after 'from' date"}
    client = make_client(Recorder([httpx.Response(400, json=body)]))

    with pytest.raises(ValidationError) as exc_info:
        client.accounting.export("2026-01-01", "2026-12-31", "csv")

    assert exc_info.value.status_code == 400
    assert exc_info.value.message == body["error"]


def test_export_window_is_left_to_the_server(no_sleep):
    """A span longer than three months is sent; the server decides (it accepts 95 days)."""
    rec = Recorder([httpx.Response(200, json=[])])
    client = make_client(rec)

    assert client.accounting.export("2026-01-01", "2026-04-05", "json") == []
    assert rec.requests[0].url.params["to"] == "2026-04-05"


def test_json_export_hydrates_events(no_sleep):
    event = {
        "paymentId": "pay@1",
        "paymentReference": "",
        "type": "payment",
        "txTimeUtc": "2026-01-01T00:00:00Z",
        "receiptUrl": "",
        "relatedPaymentId": "",
        "relatedPaymentReference": "",
        "productId": 1,
        "productReference": "",
        "productName": "P",
        "productDescription": "D",
        "customerUUID": "",
        "customerReference": "",
        "chain": "ETH",
        "blockNumberOrSlot": "1",
        "txHash": "0x",
        "fromAddress": "a",
        "toAddress": "b",
        "tokenSymbol": "USDC",
        "currencyDecimals": 6,
        "tokenContractOrMint": "",
        "explorerUrl": "",
        "grossAmount": "1",
        "grossAmountUsd": 1.0,
        "platformFeePercent": 1.0,
        "platformFeeUsd": 0.01,
        "platformFee": "0.01",
        "organizationFeePercent": 0,
        "organizationFeeUsd": 0,
        "organizationFee": "0",
        "networkFeesUsd": 0,
        "networkFees": "0",
        "netAmountUsd": 0.99,
        "netAmount": "0.99",
    }
    client = make_client(Recorder([httpx.Response(200, json=[event])]))

    events = client.accounting.export("2026-01-01", "2026-03-31", "json")

    assert len(events) == 1 and events[0].payment_id == "pay@1"


Sender = Callable[[QBitFlow], Any]
