"""Live checks against a QBitFlow API (Go integration_test.go). They never run by default:

    QBITFLOW_API_KEY=sk_… QBITFLOW_BASE_URL=https://… pytest tests/test_integration.py -v

* No key: skipped. A key without ``QBITFLOW_BASE_URL``: failed (never aim the checks at production
  by accident).
* The read-only group only reads.
* The write group also needs ``QBITFLOW_LIVE_WRITES=1`` and a test-mode key (per ``me()``), or
  ``QBITFLOW_ALLOW_LIVE_MODE_WRITES=1``. It creates a product, a customer, a checkout session and
  a webhook endpoint, and deletes (or expires) each of them.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from typing import Callable, Iterator, List

import pytest

from qbitflow import (
    PLACEHOLDER_UUID,
    CheckoutSessionStatusValue,
    ConflictError,
    EventType,
    Me,
    NotFoundError,
    QBitFlow,
    Role,
    webhooks,
)

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def client() -> Iterator[QBitFlow]:
    key = os.environ.get("QBITFLOW_API_KEY", "")
    base = os.environ.get("QBITFLOW_BASE_URL", "")
    if not key:
        pytest.skip("QBITFLOW_API_KEY not set: live checks skipped")
    if not base:
        pytest.fail(
            (
                "QBITFLOW_API_KEY is set but QBITFLOW_BASE_URL is not: set th"
                "e API's base URL explicitly"
            )
        )
    with QBitFlow(key, base_url=base) as c:
        yield c


@pytest.fixture(scope="module")
def me(client: QBitFlow) -> Me:
    me = client.me()
    assert me.space is not None and me.space.uuid, me
    return me


def is_organization_key(me: Me) -> bool:
    return me.role == Role.ADMIN and not me.on_behalf_of


# ── Read-only ────────────────────────────────────────────────────────────────


def test_live_products(client: QBitFlow, me: Me) -> None:
    client.products.list(include_hidden=True)


def test_live_customers(client: QBitFlow, me: Me) -> None:
    page = client.customers.list(limit=2)
    assert len(page.items) <= 2
    for n, customer in enumerate(client.customers.iterate(limit=2), start=1):
        assert customer.uuid
        if n == 3:  # the first page and one more row at most
            break


def test_live_payments(client: QBitFlow, me: Me) -> None:
    client.payments.list(limit=5)
    since = datetime.now(timezone.utc) - timedelta(days=30)
    client.payments.list_combined(limit=5, created_after=since)
    client.failures.list(limit=5)


def test_live_subscriptions(client: QBitFlow, me: Me) -> None:
    client.subscriptions.list(limit=5)


def test_live_refunds(client: QBitFlow, me: Me) -> None:
    client.refunds.list()
    client.refunds.list_inactive(limit=5)


def test_live_members(client: QBitFlow, me: Me) -> None:
    if not is_organization_key(me):
        pytest.skip("organization key only")
    client.members.list(limit=5)
    client.members.list_held_funds()
    client.invitations.list(limit=5)


def test_live_wallets(client: QBitFlow, me: Me) -> None:
    client.wallets.list(with_balances=True)
    client.wallets.list_supported_currencies()


def test_live_currencies(client: QBitFlow, me: Me) -> None:
    assert me.space is not None
    currencies = client.currencies.list_available(test=me.space.test)
    client.currencies.list_main()
    if currencies:
        assert client.currencies.get(currencies[0].id).id == currencies[0].id


def test_live_accounting(client: QBitFlow, me: Me) -> None:
    to = datetime.now(timezone.utc).date()
    start = to - timedelta(days=30)
    client.accounting.export_json(start, to)
    csv = client.accounting.export_csv(start.isoformat(), to.isoformat())
    assert csv, "a header line is expected"


def test_live_webhooks(client: QBitFlow, me: Me) -> None:
    client.webhooks.endpoints.list()
    page = client.webhooks.events.list(limit=5)
    if page.items:
        client.webhooks.events.get(page.items[0].id)


def test_live_unknown_session(client: QBitFlow, me: Me) -> None:
    with pytest.raises(NotFoundError):
        client.checkout_sessions.get_status("pay@019eca82-5680-7b00-8000-00000000dead")


# ── Writes ───────────────────────────────────────────────────────────────────


@pytest.fixture
def writer(client: QBitFlow, me: Me) -> Iterator[QBitFlow]:
    if os.environ.get("QBITFLOW_LIVE_WRITES") != "1":
        pytest.skip("QBITFLOW_LIVE_WRITES=1 not set: write checks skipped")
    assert me.space is not None
    if not me.space.test and os.environ.get("QBITFLOW_ALLOW_LIVE_MODE_WRITES") != "1":
        pytest.skip(
            "write checks run on a test-mode key only (or QBITFLOW_ALLOW_LIVE_MODE_WRITES=1)"
        )
    cleanups: List[Callable[[], None]] = []
    client._cleanups = cleanups
    yield client
    for undo in reversed(cleanups):
        try:
            undo()
        except NotFoundError:
            pass  # already gone


def cleanup(client: QBitFlow, undo: Callable[[], None]) -> None:
    client._cleanups.append(undo)


def suffix() -> str:
    return str(time.time_ns())


def test_live_writes_product(writer: QBitFlow) -> None:
    ref = "sdk-python-test-" + suffix()
    product = writer.products.create(name="SDK Python test", price=1, reference=ref)
    cleanup(writer, lambda: writer.products.delete(product.uuid))
    assert writer.products.get(product.uuid).reference == ref
    assert writer.products.get_by_reference(ref).uuid == product.uuid
    updated = writer.products.update(
        product.uuid, price=2.0, description="Updated by the Python SDK"
    )
    assert updated.price == 2 and updated.description
    writer.products.delete(product.uuid)
    with pytest.raises(NotFoundError):
        writer.products.get(product.uuid)


def test_live_writes_customer(writer: QBitFlow) -> None:
    s = suffix()
    customer = writer.customers.create(
        name="Ada",
        last_name="Test",
        email=f"sdk-python-test-{s}@example.com",
        phone_number="+33 6 12 34 56 78",
        reference="sdk-python-" + s,
    )
    cleanup(writer, lambda: writer.customers.delete(customer.uuid))
    assert customer.phone_number
    updated = writer.customers.update(customer.uuid, phone_number="")
    assert not updated.phone_number and updated.email == customer.email
    writer.customers.delete(customer.uuid)


def test_live_writes_checkout(writer: QBitFlow) -> None:
    try:
        session = writer.checkout_sessions.create_payment(
            product_name="SDK Python test",
            price=1,
            reference="sdk-python-order-" + suffix(),
            success_url=f"https://example.com/ok?id={PLACEHOLDER_UUID}",
            cancel_url="https://example.com/cancel",
        )
    except ConflictError as exc:
        if exc.code == "merchant_not_ready":
            pytest.skip("the space accepts no currency (merchant_not_ready)")
        raise

    def expire() -> None:
        try:
            writer.checkout_sessions.expire(session.uuid)
        except ConflictError:
            pass  # already final

    cleanup(writer, expire)
    assert session.link and session.expires_at is not None
    assert (
        writer.checkout_sessions.get_status(session.uuid).status
        == CheckoutSessionStatusValue.CREATED
    )
    # Nobody pays it: the timeout elapses and the last (non-final) status comes back.
    waited = writer.checkout_sessions.wait_for_completion(session.uuid, timeout=1, interval=1)
    assert waited.status == CheckoutSessionStatusValue.CREATED
    assert (
        writer.checkout_sessions.expire(session.uuid).status == CheckoutSessionStatusValue.EXPIRED
    )
    # Final now: the first poll returns it, no wait.
    waited = writer.checkout_sessions.wait_for_completion(session.uuid, timeout=5)
    assert waited.status == CheckoutSessionStatusValue.EXPIRED


def test_live_writes_webhook_endpoint(writer: QBitFlow) -> None:
    created = writer.webhooks.endpoints.create(
        url="https://example.com/qbitflow-sdk-test",
        events=[EventType.PAYMENT_COMPLETED],
        description="Python SDK test " + suffix(),
    )
    cleanup(writer, lambda: writer.webhooks.endpoints.delete(created.uuid))
    assert created.secret
    assert writer.webhooks.endpoints.get(created.uuid).url == created.url
    # The router accepts a delivery signed with the endpoint's real secret (local check).
    seen: List[str] = []
    router = writer.webhooks.router(created.secret)
    router.on_any(lambda event: seen.append(event.id))
    body = (
        b'{"id":"evt_sdk_smoke","version":"v2","type":"webhook.test",'
        b'"createdAt":"2026-10-01T12:00:00Z","test":true,"data":{}}'
    )
    assert router.handle(body, webhooks.sign(body, created.secret)).status == 200
    assert seen == ["evt_sdk_smoke"]
    updated = writer.webhooks.endpoints.update(created.uuid, description="", enabled=False)
    assert updated.description == "" and updated.disabled_at is not None
    writer.webhooks.endpoints.delete(created.uuid)
