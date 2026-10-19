"""Live checks against a QBitFlow API (Go integration_test.go). They never run by default:

    QBITFLOW_API_KEY=sk_… QBITFLOW_BASE_URL=https://… pytest tests/test_integration.py -v

* No key: skipped. A key without ``QBITFLOW_BASE_URL``: failed (never aim the checks at production
  by accident).
* The read-only group only reads.
* The write group also needs ``QBITFLOW_LIVE_WRITES=1`` and a test-mode key (per ``me()``), or
  ``QBITFLOW_ALLOW_LIVE_MODE_WRITES=1``. It creates a product, a customer, three checkout sessions
  (a payment's and a subscription's with fees) and a webhook endpoint, and deletes (or expires)
  each of them; it sets and deletes a metadata key on the latest subscription, if there is one.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from typing import Callable, Iterator, List

import pytest

from qbitflow import (
    PLACEHOLDER_UUID,
    CheckoutFees,
    CheckoutSessionStatusValue,
    ConflictError,
    Duration,
    DurationUnit,
    EventType,
    FeeItem,
    Me,
    NotFoundError,
    PermissionDeniedError,
    QBitFlow,
    RefundStatus,
    Role,
    TransactionKind,
    WebhookPayloadVersion,
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
    return me.role == Role.ADMIN and not me.on_behalf_of_user_uuid


# ── Read-only ────────────────────────────────────────────────────────────────


def test_live_products(client: QBitFlow, me: Me) -> None:
    page = client.products.list(include_hidden=True, limit=2)
    assert len(page.items) <= 2 and page.has_more == (page.next_cursor is not None)
    if page.items and page.items[0].reference:
        assert client.products.get_by_reference(page.items[0].reference).uuid == page.items[0].uuid
    with pytest.raises(NotFoundError):
        client.products.get_by_reference("sdk-python-no-such-reference")


def test_live_customers(client: QBitFlow, me: Me) -> None:
    page = client.customers.list(limit=2)
    assert len(page.items) <= 2
    for n, customer in enumerate(client.customers.iterate(limit=2), start=1):
        assert customer.uuid
        if n == 3:  # the first page and one more row at most
            break


def test_live_payments(client: QBitFlow, me: Me) -> None:
    payments = client.payments.list(limit=5)
    if payments.items:
        p = client.payments.get(payments.items[0].uuid)
        assert p.uuid == payments.items[0].uuid and p.currency.code and p.amount_usd
    since = datetime.now(timezone.utc) - timedelta(days=30)
    for tx in client.transactions.list(limit=5, created_after=since).items:
        assert tx.type in (TransactionKind.PAYMENT, TransactionKind.BILL)
    client.transactions.list(limit=5, type=TransactionKind.BILL)
    client.failures.list(limit=5)


def test_live_subscriptions(client: QBitFlow, me: Me) -> None:
    subs = client.subscriptions.list(limit=5)
    if subs.items:
        sub = subs.items[0]
        client.subscriptions.get(sub.uuid)
        bills = client.subscriptions.list_bills(sub.uuid, limit=2)
        if bills.items:
            assert client.subscriptions.get_bill(bills.items[0].uuid).subscription_uuid == sub.uuid


def test_live_refunds(client: QBitFlow, me: Me) -> None:
    pending = client.refunds.list(status=[RefundStatus.PENDING])
    assert all(r.status == RefundStatus.PENDING for r in pending.items)
    answered = client.refunds.list(limit=5, status=[RefundStatus.APPROVED, RefundStatus.REJECTED])
    if answered.items:
        assert client.refunds.get(answered.items[0].uuid).uuid == answered.items[0].uuid


def test_live_members(client: QBitFlow, me: Me) -> None:
    if not is_organization_key(me):
        pytest.skip("organization key only")
    client.members.list(limit=5)
    client.members.list_held_funds()
    client.invitations.list(limit=5)
    held = client.members.get_own_held_funds()
    assert held.ledgers == []  # the organization's own space holds nothing


def test_live_wallets(client: QBitFlow, me: Me) -> None:
    client.wallets.list(with_balances=True)
    client.wallets.list_accepted_currencies()


def test_live_currencies(client: QBitFlow, me: Me) -> None:
    assert me.space is not None
    currencies = client.currencies.list(test=me.space.test)
    for native in client.currencies.list(test=me.space.test, main=True):
        assert native.address is None and native.main_currency_id is None
    if currencies:
        assert client.currencies.get(currencies[0].id).id == currencies[0].id


def test_live_accounting(client: QBitFlow, me: Me) -> None:
    to = datetime.now(timezone.utc).date()
    start = to - timedelta(days=30)
    client.accounting.export_json(start, to)
    csv = client.accounting.export_csv(start.isoformat(), to.isoformat())
    assert csv, "a header line is expected"


def test_live_webhooks(client: QBitFlow, me: Me) -> None:
    client.webhooks.endpoints.list(limit=5)
    page = client.webhooks.events.list(limit=5)
    if page.items:
        client.webhooks.events.get(page.items[0].id)


def test_live_unknown_session(client: QBitFlow, me: Me) -> None:
    with pytest.raises(NotFoundError):
        client.checkout_sessions.get("pay@019eca82-5680-7b00-8000-00000000dead")


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
    product = writer.products.create(
        name="SDK Python test",
        price_usd="1",
        reference=ref,
        metadata={"sdk": "python", "run": suffix()},
    )
    cleanup(writer, lambda: writer.products.delete(product.uuid))
    got = writer.products.get(product.uuid)
    assert got.reference == ref and got.price_usd == "1" and got.metadata["sdk"] == "python"
    assert writer.products.get_by_reference(ref).uuid == product.uuid
    updated = writer.products.update(
        product.uuid,
        price_usd="2.50",
        description="Updated by the Python SDK",
        metadata={"run": "", "tier": "gold"},
    )
    assert updated.price_usd == "2.5" and updated.description
    # Metadata merged: a key set to "" is deleted, others kept.
    assert updated.metadata.get("sdk") == "python" and updated.metadata.get("tier") == "gold"
    assert "run" not in updated.metadata
    assert writer.products.delete(product.uuid) is None
    with pytest.raises(NotFoundError):
        writer.products.get(product.uuid)


def test_live_writes_customer(writer: QBitFlow) -> None:
    s = suffix()
    customer = writer.customers.create(
        first_name="Ada",
        last_name="Test",
        email=f"sdk-python-test-{s}@example.com",
        phone_number="+33 6 12 34 56 78",
        reference="sdk-python-" + s,
        metadata={"crm": "42"},
    )
    cleanup(writer, lambda: writer.customers.delete(customer.uuid))
    assert customer.phone_number and customer.first_name == "Ada" and customer.verified
    assert customer.metadata["crm"] == "42"
    assert writer.customers.get_by_reference("sdk-python-" + s).uuid == customer.uuid
    by_email = writer.customers.list(email=customer.email)
    assert [c.uuid for c in by_email.items] == [customer.uuid]
    updated = writer.customers.update(
        customer.uuid, last_name="", phone_number="", metadata={"crm": ""}
    )
    assert not updated.phone_number and not updated.last_name
    assert updated.email == customer.email and updated.metadata == {}
    writer.customers.delete(customer.uuid)


def test_live_writes_checkout(writer: QBitFlow) -> None:
    try:
        session = writer.checkout_sessions.create_payment(
            product_name="SDK Python test",
            price_usd="1",
            reference="sdk-python-order-" + suffix(),
            success_url=f"https://example.com/ok?id={PLACEHOLDER_UUID}",
            cancel_url="https://example.com/cancel",
            metadata={"orderId": "sdk-python"},
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
    assert session.link and session.expires_at.year > 1
    status = writer.checkout_sessions.get(session.uuid)
    assert status.status == CheckoutSessionStatusValue.CREATED and status.expires_at is not None
    # Nobody pays it: the timeout elapses and the last (non-final) status comes back.
    waited = writer.checkout_sessions.wait_for_completion(session.uuid, timeout=1, interval=1)
    assert waited.status == CheckoutSessionStatusValue.CREATED
    assert (
        writer.checkout_sessions.expire(session.uuid).status == CheckoutSessionStatusValue.EXPIRED
    )
    # Final now: the first poll returns it, no wait.
    waited = writer.checkout_sessions.wait_for_completion(session.uuid, timeout=5)
    assert waited.status == CheckoutSessionStatusValue.EXPIRED
    # The payment does not exist (the session expired unpaid): its reference finds nothing.
    with pytest.raises(NotFoundError):
        writer.payments.get_by_reference("sdk-python-order-none-" + suffix())


def test_live_writes_checkout_fees(writer: QBitFlow) -> None:
    # The snippets' feesCheckout: $3.99 + $0.75 shipping + the processing fee, under the
    # test-mode $5 cap, then a subscription checkout with the same fees.
    success_url = f"https://shop.example.com/orders/success?uuid={PLACEHOLDER_UUID}"
    cancel_url = "https://shop.example.com/orders/cancel"
    fees = CheckoutFees(
        processing_fee=True,
        items=[FeeItem(label="Shipping", description="Standard, 3 to 5 days", amount_usd="0.75")],
    )
    try:
        session = writer.checkout_sessions.create_payment(
            product_name="T-shirt",
            description="Blue, size M",
            price_usd="3.99",
            reference="order-1044-" + suffix(),
            success_url=success_url,
            cancel_url=cancel_url,
            fees=fees,
        )
    except ConflictError as exc:
        if exc.code == "merchant_not_ready":
            pytest.skip("the space accepts no currency (merchant_not_ready)")
        raise

    def expire(uuid: str) -> Callable[[], None]:
        def run() -> None:
            try:
                writer.checkout_sessions.expire(uuid)
            except ConflictError:
                pass  # already final

        return run

    cleanup(writer, expire(session.uuid))
    assert session.uuid.startswith("pay@") and session.link
    assert writer.checkout_sessions.get(session.uuid).status == CheckoutSessionStatusValue.CREATED

    # A subscription checkout takes the same fees, charged with every bill.
    try:
        sub = writer.checkout_sessions.create_subscription(
            product_name="Pro",
            description="Monthly plan",
            price_usd="3.99",
            reference="sub-1044-" + suffix(),
            frequency=Duration(value=1, unit=DurationUnit.MONTHS),
            success_url=success_url,
            cancel_url=cancel_url,
            fees=fees,
        )
    except PermissionDeniedError as exc:
        if exc.code == "policy_disabled":
            pytest.skip("subscriptions are off for this member (members.subscriptions)")
        raise
    cleanup(writer, expire(sub.uuid))
    assert sub.uuid.startswith("sub@") and sub.link


def test_live_writes_webhook_endpoint(writer: QBitFlow) -> None:
    created = writer.webhooks.endpoints.create(
        url="https://example.com/qbitflow-sdk-test",
        events=[EventType.PAYMENT_COMPLETED],
        description="Python SDK test " + suffix(),
    )
    cleanup(writer, lambda: writer.webhooks.endpoints.delete(created.uuid))
    assert created.secret
    got = writer.webhooks.endpoints.get(created.uuid)
    assert got.url == created.url and got.payload_version == WebhookPayloadVersion.V2
    assert created.uuid in {e.uuid for e in writer.webhooks.endpoints.iterate(limit=1)}
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
    assert not updated.description and updated.disabled_at is not None
    assert writer.webhooks.endpoints.delete(created.uuid) is None


def test_live_writes_subscription_metadata(writer: QBitFlow) -> None:
    """Sets then deletes a metadata key on the space's latest subscription, if it has one (a
    PATCH that leaves the subscription as it was)."""
    subs = writer.subscriptions.list(limit=1)
    if not subs.items:
        pytest.skip("no subscription to update")
    sub = subs.items[0]
    key = "sdkPythonTest"
    if key in sub.metadata:
        pytest.skip(f"the subscription already has a {key} key")
    try:
        updated = writer.subscriptions.update(sub.uuid, metadata={key: suffix()})
    except PermissionDeniedError as exc:
        if exc.code == "policy_disabled":
            pytest.skip("subscriptions are off for this member (members.subscriptions)")
        raise
    cleanup(writer, lambda: writer.subscriptions.update(sub.uuid, metadata={key: ""}))
    assert updated.metadata.get(key) and len(updated.metadata) == len(sub.metadata) + 1
