"""Webhook event parsing: the 15 docs fixtures and the edge cases (Go events_test.go)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Type

import httpx
import pytest

from qbitflow import (
    ActionRequired,
    Bill,
    BillingFailureReason,
    Chain,
    CheckoutExpiredEvent,
    Duration,
    DurationUnit,
    EventDetail,
    EventType,
    FeeLineType,
    HeldFundsReleased,
    HeldFundsReleasedEvent,
    LedgerEntryType,
    Member,
    MemberJoined,
    MemberJoinedEvent,
    MemberRemovedEvent,
    PaymentCompleted,
    PaymentCompletedEvent,
    PaymentSessionData,
    Refund,
    RefundApprovedEvent,
    RefundInitiator,
    RefundRejectedEvent,
    RefundRequestedEvent,
    RefundStatus,
    Subscription,
    SubscriptionActionRequiredChanged,
    SubscriptionActionRequiredChangedEvent,
    SubscriptionBilled,
    SubscriptionBilledEvent,
    SubscriptionBillingFailed,
    SubscriptionBillingFailedEvent,
    SubscriptionCreatedEvent,
    SubscriptionSessionData,
    SubscriptionStatus,
    SubscriptionStatusChanged,
    SubscriptionStatusChangedEvent,
    SubscriptionUpcomingBill,
    SubscriptionUpcomingBillEvent,
    TransactionType,
    TransferSettlement,
    TransferType,
    UnknownEvent,
    ValidationError,
    WebhookTest,
    WebhookTestEvent,
    webhooks,
)
from qbitflow._transport import Response, decode

from .conftest import FIXTURES

CLASSES: Dict[str, Type[Any]] = {
    "payment.completed": PaymentCompletedEvent,
    "subscription.created": SubscriptionCreatedEvent,
    "subscription.billed": SubscriptionBilledEvent,
    "subscription.statusChanged": SubscriptionStatusChangedEvent,
    "subscription.actionRequiredChanged": SubscriptionActionRequiredChangedEvent,
    "subscription.billingFailed": SubscriptionBillingFailedEvent,
    "subscription.upcomingBill": SubscriptionUpcomingBillEvent,
    "refund.requested": RefundRequestedEvent,
    "refund.approved": RefundApprovedEvent,
    "refund.rejected": RefundRejectedEvent,
    "member.joined": MemberJoinedEvent,
    "member.removed": MemberRemovedEvent,
    "heldFunds.released": HeldFundsReleasedEvent,
    "checkout.expired": CheckoutExpiredEvent,
    "webhook.test": WebhookTestEvent,
}

#: The data model of each type (types.md §4).
DATA: Dict[str, Type[Any]] = {
    "payment.completed": PaymentCompleted,
    "subscription.created": Subscription,
    "subscription.billed": SubscriptionBilled,
    "subscription.statusChanged": SubscriptionStatusChanged,
    "subscription.actionRequiredChanged": SubscriptionActionRequiredChanged,
    "subscription.billingFailed": SubscriptionBillingFailed,
    "subscription.upcomingBill": SubscriptionUpcomingBill,
    "refund.requested": Refund,
    "refund.approved": Refund,
    "refund.rejected": Refund,
    "member.joined": MemberJoined,
    "member.removed": Member,
    "heldFunds.released": HeldFundsReleased,
    "checkout.expired": PaymentSessionData,
    "webhook.test": WebhookTest,
}


def raw(event_type: str) -> str:
    return (FIXTURES / "events" / f"{event_type}.json").read_text()


def load(event_type: str) -> Any:
    event = webhooks.parse_event(raw(event_type))
    assert event.type == event_type and event.version == "v2" and event.id.startswith("evt_")
    assert event.created_at.tzinfo is not None and event.created_at.year > 1
    return event


def _keys(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _keys(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_keys(v) for v in value]
    return None


def _covers(fixture: Any, dumped: Any) -> bool:
    """Every key of the fixture (at every level) is written back by the model."""
    if isinstance(fixture, dict):
        return isinstance(dumped, dict) and all(
            k in dumped and _covers(v, dumped[k]) for k, v in fixture.items()
        )
    if isinstance(fixture, list):
        return isinstance(dumped, list) and all(_covers(f, d) for f, d in zip(fixture, dumped))
    return True


def test_one_fixture_per_type() -> None:
    files = sorted(p.stem for p in (FIXTURES / "events").glob("*.json"))
    assert files == sorted(t.value for t in EventType) == sorted(CLASSES) == sorted(DATA)
    assert len(files) == 15


@pytest.mark.parametrize("event_type", [t.value for t in EventType])
def test_fixtures_are_fully_modelled(event_type: str) -> None:
    event = load(event_type)
    assert type(event) is CLASSES[event_type]
    assert type(event.data) is DATA[event_type]
    # Every key of the docs' example data is modelled (written back by the model).
    data = json.loads(raw(event_type))["data"]
    dumped = event.data.model_dump(mode="json", by_alias=True, exclude_none=True)
    assert _covers(data, dumped), (_keys(data), _keys(dumped))


def test_payment_completed() -> None:
    p = load("payment.completed").data
    assert p.uuid == "pay@01a0f755-f200-7000-8000-000000000001"
    assert (p.amount, p.amount_min_units, p.amount_usd) == ("10", "10000000", "10")
    assert p.reference == "order-1042" and p.customer_reference == "crm-5521"
    assert p.chain == Chain.BASE and p.product_name == "Pro plan (lifetime)"
    assert p.management_page_link
    assert (p.paid, p.paid_min_units, p.paid_usd) == ("10.0042", "10004200", "10.0042")
    assert p.metadata["orderId"] == "order-1042" and p.metadata["crm:customer"] == "C-5521"
    c = p.currency
    assert c.code == "BASE:USDC" and c.symbol == "USDC" and c.chain == Chain.BASE
    assert c.main_currency_id == 3 and c.address
    st = p.settlement
    assert st.fee_percent == "0.99" and st.split is not None
    assert st.split.merchant.amount_min_units == "9901000" and st.split.platform.amount == "0.099"
    assert st.split.network_fee is not None and st.split.network_fee.amount == "0.0042"
    assert st.split.organization is None and st.split.referral is None
    assert st.organization_fee is None and st.referral_fee is None
    tx = st.transaction
    assert tx is not None and tx.block_number == "52468103" and tx.gas_used == 95000
    assert (
        tx.native_price_usd == "4512.37" and tx.l1_fee is None and tx.fee.amount_usd == "0.005144"
    )
    # Webhooks never carry the API-only fields.
    assert p.customer is None and p.refund is None and p.refundable is None
    assert p.not_refundable_reason is None
    assert p.confirmed_at is not None and p.checkout_opened_at is not None
    # The docs' payment has a price and no fees: amount_usd = price_usd.
    assert p.price_usd == "10" and p.fees == [] and p.price_usd == p.amount_usd


def test_subscriptions() -> None:
    created = load("subscription.created").data
    assert isinstance(created, Subscription) and created.uuid.startswith("sub@")
    assert created.frequency == Duration(value=1, unit=DurationUnit.MONTHS)
    assert created.status == SubscriptionStatus.ACTIVE and created.price_usd == "10"
    assert created.current_period_end and created.next_billing_at and created.last_billed_at
    assert created.management_page_link and created.metadata["plan"] == "pro"
    assert created.reference == "customer-7731" and created.currency.code == "BASE:USDC"
    a = created.allowance
    assert a is not None and a.amount == "110" and a.remaining_periods == 11
    assert a.max_per_period_min_units == "30000000" and created.dunning is None
    assert created.has_access(datetime(2026, 10, 30, tzinfo=timezone.utc))
    assert not created.has_access(created.current_period_end)

    billed = load("subscription.billed").data
    assert isinstance(billed.bill, Bill) and isinstance(billed.subscription, Subscription)
    b, sub = billed.bill, billed.subscription
    assert b.uuid.startswith("sub-hist@") and b.subscription_uuid == sub.uuid
    assert b.amount == "10" and b.product_name == "Pro plan" and b.paid == "10.0042"
    assert b.period_start and b.period_end and b.settlement.split is not None
    assert b.settlement.fee_percent == "0.99"
    assert sub.status == SubscriptionStatus.ACTIVE and sub.reference == "customer-7731"
    assert sub.metadata["crm:account"] == "A-1042" and sub.next_billing_at == b.period_end
    # The draft's flattened fields are gone.
    assert not hasattr(billed, "subscription_reference") and not hasattr(billed, "uuid")

    changed = load("subscription.statusChanged").data
    assert changed.previous_status == SubscriptionStatus.PAST_DUE
    assert changed.status == SubscriptionStatus.ACTIVE and changed.management_page_link

    action = load("subscription.actionRequiredChanged").data
    assert action.action_required == ActionRequired.TOP_UP_ALLOWANCE
    assert action.previous_action_required is None
    assert action.allowance is not None and action.allowance.remaining_periods == 0

    failed = load("subscription.billingFailed").data
    assert failed.reason == BillingFailureReason.INSUFFICIENT_BALANCE and failed.amount_usd == "10"
    assert failed.attempt == 1 and failed.remaining_attempts == 4
    assert failed.bill_uuid == "sub-hist@01a0f755-f200-7000-8000-000000000005"
    assert failed.failure_code == "insufficient_funds" and failed.next_attempt_at is not None
    assert failed.status == SubscriptionStatus.PAST_DUE and failed.management_page_link

    upcoming = load("subscription.upcomingBill").data
    assert upcoming.amount_usd == "10" and isinstance(upcoming.amount_usd, str)
    assert upcoming.billing_at == datetime(2026, 10, 4, 12, tzinfo=timezone.utc)
    assert upcoming.trial_ending is False and upcoming.balance_sufficient is True
    assert upcoming.allowance_sufficient is not None


@pytest.mark.parametrize(
    "event_type, status",
    [
        ("refund.requested", RefundStatus.PENDING),
        ("refund.approved", RefundStatus.APPROVED),
        ("refund.rejected", RefundStatus.REJECTED),
    ],
)
def test_refunds(event_type: str, status: RefundStatus) -> None:
    r = load(event_type).data
    assert r.status == status and r.uuid.startswith("refund@") and r.tx_uuid.startswith("pay@")
    assert r.refund_percent and r.initiated_by == RefundInitiator.CUSTOMER and r.reason
    assert r.paid == "10.0042" and r.currency.code == "BASE:USDC"
    assert (r.responded_at is None) == (status == RefundStatus.PENDING)
    # Webhooks never carry the API-only fields.
    assert r.approval is None and r.customer is None and r.customer_uuid is None
    assert r.product_name is None


def test_refund_details() -> None:
    approved = load("refund.approved").data
    assert approved.refund_percent == "50" and approved.amount == "5.0021"
    assert approved.settlement is not None and approved.settlement.transaction is not None
    assert approved.tx_hash and approved.explorer_url and approved.merchant_message is None
    rejected = load("refund.rejected").data
    assert rejected.merchant_message and rejected.settlement is None and rejected.tx_hash is None
    requested = load("refund.requested").data
    assert requested.refund_percent == "100" and requested.amount == requested.paid


@pytest.mark.parametrize("retired", ["refund.completed", "refund.denied"])
def test_retired_refund_types_are_unknown(retired: str) -> None:
    body = json.loads(raw("refund.approved"))
    body["type"] = retired
    event = webhooks.parse_event(json.dumps(body))
    assert isinstance(event, UnknownEvent) and event.type == retired
    assert isinstance(event.data, dict) and event.data["status"] == "approved"


def test_members_and_funds() -> None:
    joined = load("member.joined").data
    assert joined.user_uuid and joined.invitation_uuid and joined.space_uuid
    assert joined.joined_at.year > 1 and joined.first_name == "Alice"
    assert joined.organization_fee_percent == "5" and joined.trusted_at is None
    assert [c.id for c in joined.accepted_currencies] == [8]
    removed = load("member.removed").data
    assert removed.user_uuid and removed.trusted_at is not None and removed.last_name == "Martin"

    event = load("heldFunds.released")
    assert event.user_uuid == "019eca82-5680-7b00-8000-0000000000b1"
    released = event.data
    assert released.received and released.type == TransferType.HELD_FUNDS_RELEASE
    assert len(released.ledgers) == 3 and released.uuid.startswith("transfer@")
    assert released.amount == "98.9068" and released.amount_usd == "98.9068"
    assert isinstance(released.settlement, TransferSettlement)
    assert released.settlement.transaction is not None
    assert released.currency.code == "BASE:USDC"
    first = released.ledgers[0]
    assert first.type == LedgerEntryType.PAYMENT and first.settlement is not None
    assert first.settlement.split is not None and first.amount_usd == "100"
    assert (first.owed, first.owed_min_units, first.owed_usd) == ("99.01", "99010000", "99.01")
    refund = released.ledgers[2]
    assert refund.type == LedgerEntryType.REFUND and refund.settlement is None
    assert refund.refunded_tx_uuid and refund.owed_min_units.startswith("-")
    # amount is the sum of the lines' owed (exact, in min units).
    total = sum(int(line.owed_min_units) for line in released.ledgers)
    assert str(total) == released.amount_min_units


def test_checkout_expired() -> None:
    event = load("checkout.expired")
    assert isinstance(event.data, PaymentSessionData)
    assert not isinstance(event.data, SubscriptionSessionData)
    p = event.data
    assert p.tx_type == TransactionType.PAYMENT and p.price_usd == "10" and p.amount_usd == "10"
    assert len(p.available_currencies) == 2 and p.available_currencies[0].address is None
    assert p.available_currencies[1].code == "BASE:USDC"
    assert p.metadata["orderId"] == "order-1043" and p.organization_name == "Example Shop"
    assert p.expires_at is not None and p.created_at is not None
    assert p.reference == "order-1043" and p.redirect_url is None
    assert p.fees == []  # the docs' session has no fees

    with_fees = json.loads(raw("checkout.expired"))
    with_fees["data"].update(
        priceUsd="3.99",
        amountUsd="4.81",
        fees=[
            {
                "type": "custom",
                "label": "Shipping",
                "description": "Standard, 3 to 5 days",
                "amountUsd": "0.75",
            },
            {"type": "processingFee", "label": "Processing fee", "amountUsd": "0.07"},
        ],
    )
    f = webhooks.parse_event(json.dumps(with_fees)).data
    assert isinstance(f, PaymentSessionData) and f.price_usd == "3.99" and f.amount_usd == "4.81"
    assert [(x.type, x.label, x.description, x.amount_usd) for x in f.fees] == [
        (FeeLineType.CUSTOM, "Shipping", "Standard, 3 to 5 days", "0.75"),
        (FeeLineType.PROCESSING_FEE, "Processing fee", None, "0.07"),
    ]
    assert f.to_dict()["fees"] == with_fees["data"]["fees"]

    currency = json.loads((FIXTURES / "models.json").read_text())["Currency"]
    sub = webhooks.parse_event(
        json.dumps(
            {
                "id": "evt_1",
                "type": "checkout.expired",
                "version": "v2",
                "data": {
                    "uuid": "sub@1",
                    "txType": "createSubscription",
                    "organizationName": "Shop",
                    "test": True,
                    "priceUsd": "9.99",
                    "amountUsd": "9.99",
                    "fees": [],
                    "availableCurrencies": [currency],
                    "metadata": {"plan": "pro"},
                    "frequency": {"value": 1, "unit": "weeks"},
                    "trialPeriod": {"value": 14, "unit": "days"},
                    "minPeriods": 3,
                    "upgradingFromTrial": False,
                },
            }
        )
    )
    assert isinstance(sub, CheckoutExpiredEvent) and isinstance(sub.data, SubscriptionSessionData)
    s = sub.data
    assert s.uuid == "sub@1" and s.frequency == Duration(value=1, unit="weeks")
    assert s.trial_period is not None and s.min_periods == 3 and s.upgrading_from_trial is False
    assert s.metadata == {"plan": "pro"} and s.available_currencies[0].code == "BASE:USDC"

    unknown = webhooks.parse_event(
        '{"id":"e","type":"checkout.expired","version":"v2",'
        '"data":{"uuid":"x@1","txType":"payAsYouGo","organizationName":"Shop"}}'
    )
    assert type(unknown.data) is PaymentSessionData and unknown.data.tx_type == "payAsYouGo"

    # The session's amounts are decimal strings: a number is refused.
    with pytest.raises(ValidationError):
        webhooks.parse_event(
            '{"id":"e","type":"checkout.expired","version":"v2",'
            '"data":{"uuid":"pay@3","txType":"payment","priceUsd":10}}'
        )


def test_webhook_test() -> None:
    w = load("webhook.test").data
    assert w.endpoint_uuid and w.message


def test_isinstance_narrowing() -> None:
    event = load("payment.completed")
    assert isinstance(event, PaymentCompletedEvent)
    assert not isinstance(event, SubscriptionCreatedEvent)


@pytest.mark.parametrize("data", ["", '"data":null,'])
def test_absent_or_null_data(data: str) -> None:
    event = webhooks.parse_event('{"id":"e",' + data + '"type":"webhook.test","version":"v2"}')
    assert isinstance(event, WebhookTestEvent) and event.data == WebhookTest()


def test_unknown_type() -> None:
    event = webhooks.parse_event(
        '{"id":"evt_9","type":"invoice.paid","version":"v2",'
        '"createdAt":"2026-10-01T14:00:00.5+02:00","test":true,'
        '"userUuid":"u-1","data":{"anything":[1,2]},"extra":1}'
    )
    assert isinstance(event, UnknownEvent)
    assert event.type == "invoice.paid" and event.data == {"anything": [1, 2]}
    assert event.user_uuid == "u-1" and event.test
    assert event.created_at == datetime(2026, 10, 1, 12, 0, 0, 500000, tzinfo=timezone.utc)


def test_v1_is_unsupported() -> None:
    with pytest.raises(ValidationError) as info:
        webhooks.parse_event('{"id":"evt_1","type":"payment.completed","version":"v1","data":{}}')
    assert [f.field for f in info.value.field_errors] == ["version"]
    assert "unsupported payload version" in str(info.value)


@pytest.mark.parametrize(
    "body",
    [
        "",
        '[{"version":"v2"}]',
        '"v2"',
        '{"version":',
        '{"id":"evt_1","type":"payment.completed","version":"v1","data":{}}',
        '{"id":"evt_1","type":"payment.completed","data":{}}',
        '{"id":"evt_1","type":"payment.completed","version":"v2","test":"yes"}',
        '{"id":"evt_1","type":"webhook.test","version":"v2","createdAt":"today"}',
        '{"id":"evt_1","type":5,"version":"v2"}',
        '{"id":"e","type":"subscription.upcomingBill","version":"v2","data":{"amountUsd":10}}',
        '{"id":"e","type":"subscription.billingFailed","version":"v2","data":{"amountUsd":10}}',
        '{"id":"e","type":"payment.completed","version":"v2","data":{"amount":10}}',
        '{"id":"e","type":"subscription.billed","version":"v2","data":{"bill":"sub-hist@1"}}',
        '{"id":"e","type":"heldFunds.released","version":"v2","data":{"ledgers":{}}}',
        '{"id":"e","type":"member.joined","version":"v2","data":{"organizationFeePercent":5}}',
        '{"id":"e","type":"webhook.test","version":"v2","data":[]}',
        b"\xff\xfe{}",
    ],
)
def test_invalid_bodies(body: Any) -> None:
    with pytest.raises(ValidationError):
        webhooks.parse_event(body)


def test_event_detail_decoding() -> None:
    body = """{"id":"evt_1","type":"refund.rejected","version":"v2",
        "createdAt":"2026-10-01T12:00:00Z","test":false,
        "data":{"uuid":"refund@1","status":"rejected"},
        "deliveries":[{"endpointUuid":"e1","url":"https://x.io/hook","delivered":false,"attempts":[
            {"uuid":"a1","eventId":"evt_1","eventType":"refund.rejected","endpointUuid":"e1",
             "attempt":1,"delivered":false,
             "statusCode":500,"error":"500 Internal","durationMs":120,
             "attemptedAt":"2026-10-01T12:00:01Z"},
            {"uuid":"a2","eventId":"evt_1","eventType":"refund.rejected","endpointUuid":"e1",
             "attempt":2,"delivered":false,"skipped":true,
             "error":"timeout","durationMs":30000,"attemptedAt":"2026-10-01T12:01:01Z"}]}]}"""
    detail = decode(EventDetail, Response(200, httpx.Headers(), body.encode()))
    assert isinstance(detail.event, RefundRejectedEvent)
    assert detail.event.data.status == RefundStatus.REJECTED
    attempts = detail.deliveries[0].attempts
    assert len(attempts) == 2 and attempts[0].status_code == 500
    assert attempts[1].status_code is None and attempts[1].duration_ms == 30000
    assert attempts[0].skipped is False and attempts[1].skipped is True


def test_all_event_classes_listed() -> None:
    assert len(set(CLASSES.values())) == 15
    assert EventType("refund.approved") is EventType.REFUND_APPROVED
    assert EventType("refund.rejected") is EventType.REFUND_REJECTED
    assert "refund.completed" not in {t.value for t in EventType}
