"""Webhook event parsing: the 15 docs fixtures and the edge cases (Go events_test.go)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Type

import httpx
import pytest

from qbitflow import (
    BillingFailureReason,
    Chain,
    CheckoutExpiredEvent,
    Duration,
    DurationUnit,
    EventDetail,
    EventType,
    FeeLineType,
    HeldFundsReleasedEvent,
    LedgerEntryType,
    MemberJoinedEvent,
    MemberRemovedEvent,
    PaymentCompletedEvent,
    PaymentSessionData,
    RefundCompletedEvent,
    RefundDeniedEvent,
    RefundRequestedEvent,
    RefundStatus,
    SubscriptionActionRequiredChangedEvent,
    SubscriptionBilledEvent,
    SubscriptionBillingFailedEvent,
    SubscriptionCreatedEvent,
    SubscriptionSessionData,
    SubscriptionStatus,
    SubscriptionStatusChangedEvent,
    SubscriptionUpcomingBillEvent,
    TransactionType,
    TransferType,
    UnknownEvent,
    ValidationError,
    WebhookTestEvent,
    webhooks,
)
from qbitflow._transport import Response, decode

from .conftest import FIXTURES

CLASSES = {
    "payment.completed": PaymentCompletedEvent,
    "subscription.created": SubscriptionCreatedEvent,
    "subscription.billed": SubscriptionBilledEvent,
    "subscription.statusChanged": SubscriptionStatusChangedEvent,
    "subscription.actionRequiredChanged": SubscriptionActionRequiredChangedEvent,
    "subscription.billingFailed": SubscriptionBillingFailedEvent,
    "subscription.upcomingBill": SubscriptionUpcomingBillEvent,
    "refund.requested": RefundRequestedEvent,
    "refund.completed": RefundCompletedEvent,
    "refund.denied": RefundDeniedEvent,
    "member.joined": MemberJoinedEvent,
    "member.removed": MemberRemovedEvent,
    "heldFunds.released": HeldFundsReleasedEvent,
    "checkout.expired": CheckoutExpiredEvent,
    "webhook.test": WebhookTestEvent,
}


def raw(event_type: str) -> str:
    return (FIXTURES / "events" / f"{event_type}.json").read_text()


def load(event_type: str) -> Any:
    event = webhooks.parse_event(raw(event_type))
    assert event.type == event_type and event.version == "v2" and event.id.startswith("evt_")
    assert event.created_at.tzinfo is not None
    return event


def _keys(value: Any) -> Any:
    # An empty list is an omitted one (the API's omitempty lists, e.g. a payment's fees): the
    # model writes [] for a list the example leaves out.
    if isinstance(value, dict):
        return {k: _keys(v) for k, v in value.items() if v is not None and v != []}
    if isinstance(value, list):
        return [_keys(v) for v in value]
    return None


@pytest.mark.parametrize("event_type", [t.value for t in EventType])
def test_fixtures_are_fully_modelled(event_type: str) -> None:
    event = load(event_type)
    assert type(event) is CLASSES[event_type]
    # Every key of the docs' example data is modelled (written back by the model).
    data = json.loads(raw(event_type))["data"]
    assert _keys(event.data.model_dump(mode="json", by_alias=True, exclude_none=True)) == _keys(
        data
    )


def test_payment_completed() -> None:
    p = load("payment.completed").data
    assert p.uuid == "pay@01a0f755-f200-7000-8000-000000000001" and p.amount == 10
    assert p.amount_min_units == "10000000" and p.reference == "order-1042"
    assert p.customer_reference == "crm-5521" and p.chain == Chain.BASE and p.management_page_link
    assert p.paid_min_units == "10004200" and p.paid_usd == 10.0042
    assert p.currency is not None and p.currency.symbol == "USDC"
    assert p.currency.main_currency is not None and p.currency.main_currency.main_currency is None
    assert p.currency.main_currency_id == 3
    m = p.metadata
    assert m.fee_percent == 1.5 and m.tx_amounts.min_units.merchant == "9850000"
    assert m.tx_amounts.min_units.network_fee == "4200" and m.tx_amounts.usd.merchant == 9.85
    assert m.tx_amounts.usd.organization is None and m.tx_amounts.usd.network_fee is not None
    assert (
        m.tx_metadata.block_data.timestamp == 1790855998
        and m.tx_metadata.network_fees.units_consumed == 95000
    )
    assert m.organization_fee is None
    assert p.customer is None and p.refund is None and p.refundable is None  # API reads only
    assert p.price == 10 and p.fees == []  # a payment without fees: amount = price
    assert p.confirmed_at is not None and p.checkout_opened_at is not None


def test_subscriptions() -> None:
    created = load("subscription.created").data
    assert created.uuid.startswith("sub@") and created.frequency == Duration(
        value=1, unit=DurationUnit.MONTHS
    )
    assert (
        created.price_usd
        and created.current_period_end
        and created.next_billing_date
        and created.management_page_link
    )

    billed = load("subscription.billed").data
    assert billed.uuid.startswith("sub-hist@") and billed.subscription_uuid.startswith("sub@")
    assert (
        billed.subscription_status
        and billed.subscription_reference
        and billed.period_start
        and billed.period_end
    )

    changed = load("subscription.statusChanged").data
    assert changed.previous_status and changed.status != changed.previous_status

    action = load("subscription.actionRequiredChanged").data
    assert action.action_required

    failed = load("subscription.billingFailed").data
    assert failed.reason == BillingFailureReason.INSUFFICIENT_BALANCE and failed.amount_usd == "10"
    assert failed.attempt == 1 and failed.remaining_attempts == 4
    assert failed.bill_uuid == "sub-hist@01a0f755-f200-7000-8000-000000000005"
    assert failed.failure_code == "insufficient_funds" and failed.next_attempt_at is not None
    assert failed.status == SubscriptionStatus.PAST_DUE

    upcoming = load("subscription.upcomingBill").data
    assert upcoming.amount_usd != 0 and isinstance(upcoming.amount_usd, float)
    assert upcoming.billing_date.year > 1 and upcoming.balance_sufficient is not None
    assert upcoming.allowance_sufficient is not None


@pytest.mark.parametrize(
    "event_type, status",
    [
        ("refund.requested", RefundStatus.PENDING),
        ("refund.completed", RefundStatus.APPROVED),
        ("refund.denied", RefundStatus.REJECTED),
    ],
)
def test_refunds(event_type: str, status: RefundStatus) -> None:
    r = load(event_type).data
    assert (
        r.status == status
        and r.uuid.startswith("refund@")
        and r.tx_uuid
        and r.refund_percent
        and r.initiated_by
    )
    assert (r.responded_at is None) == (status == RefundStatus.PENDING)
    assert r.approval is None and r.customer is None and r.product_name is None
    if status == RefundStatus.APPROVED:
        assert r.metadata is not None and r.tx_hash and r.explorer_url


def test_members_and_funds() -> None:
    joined = load("member.joined").data
    assert (
        joined.user_uuid
        and joined.invitation_uuid
        and joined.space_uuid
        and joined.joined_at.year > 1
    )
    assert load("member.removed").data.user_uuid

    event = load("heldFunds.released")
    assert event.user_uuid == "019eca82-5680-7b00-8000-0000000000b1"
    released = event.data
    assert (
        released.received and released.type == TransferType.HELD_FUNDS_RELEASE and released.ledgers
    )
    assert (
        released.tx_metadata.main_currency_price_usd is not None and released.currency is not None
    )
    first = released.ledgers[0]
    assert first.type == LedgerEntryType.PAYMENT and first.metadata is not None
    assert first.owed_min_units == "98500000" and first.owed_usd == 98.5
    for line in released.ledgers:
        if line.type == LedgerEntryType.REFUND:
            assert (
                line.metadata is None
                and line.refunded_tx_uuid
                and line.owed_min_units.startswith("-")
            )


def test_checkout_expired() -> None:
    event = load("checkout.expired")
    assert isinstance(event.data, PaymentSessionData) and not isinstance(
        event.data, SubscriptionSessionData
    )
    p = event.data
    assert (
        p.tx_type == TransactionType.PAYMENT
        and p.price == 10
        and len(p.available_currency_ids) == 3
    )
    assert p.organization_name == "Example Shop" and p.expires_at is not None
    assert p.fees == [] and p.amount is None  # a session without fees (the docs' example)

    with_fees = json.loads(raw("checkout.expired"))
    with_fees["data"]["price"] = 3.99
    with_fees["data"]["amount"] = 4.88
    with_fees["data"]["fees"] = [
        {
            "type": "custom",
            "label": "Shipping",
            "description": "Standard, 3 to 5 days",
            "amountUsd": "0.75",
        },
        {"type": "processingFee", "label": "Processing fee", "amountUsd": "0.14"},
    ]
    f = webhooks.parse_event(json.dumps(with_fees)).data
    assert isinstance(f, PaymentSessionData) and f.price == 3.99 and f.amount == 4.88
    assert [(x.type, x.label, x.description, x.amount_usd) for x in f.fees] == [
        (FeeLineType.CUSTOM, "Shipping", "Standard, 3 to 5 days", "0.75"),
        (FeeLineType.PROCESSING_FEE, "Processing fee", None, "0.14"),
    ]
    assert f.to_dict()["fees"] == with_fees["data"]["fees"]

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
                    "availableCurrencyIds": [8],
                    "frequency": {"value": 1, "unit": "weeks"},
                    "trialPeriod": {"value": 14, "unit": "days"},
                    "minPeriods": 3,
                },
            }
        )
    )
    assert isinstance(sub, CheckoutExpiredEvent) and isinstance(sub.data, SubscriptionSessionData)
    s = sub.data
    assert (
        s.uuid == "sub@1"
        and s.frequency == Duration(value=1, unit="weeks")
        and s.trial_period
        and s.min_periods == 3
    )

    unknown = webhooks.parse_event(
        (
            '{"id":"e","type":"checkout.expired","version":"v2","data":{"'
            'uuid":"x@1","txType":"payAsYouGo","organizationName":"Shop"}'
            "}"
        )
    )
    assert type(unknown.data) is PaymentSessionData and unknown.data.tx_type == "payAsYouGo"


def test_webhook_test() -> None:
    w = load("webhook.test").data
    assert w.endpoint_uuid and w.message


def test_isinstance_narrowing() -> None:
    event = load("payment.completed")
    assert isinstance(event, PaymentCompletedEvent) and not isinstance(
        event, SubscriptionCreatedEvent
    )


@pytest.mark.parametrize("data", ["", '"data":null,'])
def test_absent_or_null_data(data: str) -> None:
    event = webhooks.parse_event('{"id":"e",' + data + '"type":"webhook.test","version":"v2"}')
    assert isinstance(event, WebhookTestEvent) and event.data.endpoint_uuid == ""


def test_unknown_type() -> None:
    event = webhooks.parse_event(
        '{"id":"evt_9","type":"invoice.paid","version":"v2",'
        '"createdAt":"2026-10-01T14:00:00.5+02:00","test":true,'
        '"userUuid":"u-1","data":{"anything":[1,2]},"extra":1}'
    )
    assert isinstance(event, UnknownEvent)
    assert (
        event.type == "invoice.paid"
        and event.data == {"anything": [1, 2]}
        and event.user_uuid == "u-1"
    )
    assert event.test and event.created_at == datetime(
        2026, 10, 1, 12, 0, 0, 500000, tzinfo=timezone.utc
    )


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
        (
            '{"id":"evt_1","type":"subscription.upcomingBill","version":"'
            'v2","data":{"amountUsd":"10"}}'
        ),
        '{"id":"evt_1","type":"subscription.billingFailed","version":"v2","data":{"amountUsd":10}}',
        b"\xff\xfe{}",
    ],
)
def test_invalid_bodies(body: Any) -> None:
    with pytest.raises(ValidationError):
        webhooks.parse_event(body)


def test_event_detail_decoding() -> None:
    body = """{"id":"evt_1","type":"refund.denied","version":"v2",
        "createdAt":"2026-10-01T12:00:00Z","test":false,
        "data":{"uuid":"refund@1","status":"rejected"},
        "deliveries":[{"endpointUuid":"e1","url":"https://x.io/hook","delivered":false,"attempts":[
            {"uuid":"a1","eventId":"evt_1","eventType":"refund.denied","endpointUuid":"e1",
             "attempt":1,"delivered":false,
             "statusCode":500,"error":"500 Internal","durationMs":120,
             "attemptedAt":"2026-10-01T12:00:01Z"},
            {"uuid":"a2","eventId":"evt_1","eventType":"refund.denied","endpointUuid":"e1",
             "attempt":2,"delivered":false,
             "error":"timeout","durationMs":30000,"attemptedAt":"2026-10-01T12:01:01Z"}]}]}"""
    detail = decode(EventDetail, Response(200, httpx.Headers(), body.encode()))
    assert (
        isinstance(detail.event, RefundDeniedEvent)
        and detail.event.data.status == RefundStatus.REJECTED
    )
    attempts = detail.deliveries[0].attempts
    assert len(attempts) == 2 and attempts[0].status_code == 500
    assert attempts[1].status_code is None and attempts[1].duration_ms == 30000


def test_all_event_classes_listed() -> None:
    classes: list[Type[Any]] = list(CLASSES.values())
    assert len(set(classes)) == 15
