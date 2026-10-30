"""Every service method: the request it sends, the decoding of its answer, its retry policy, and
its client-side checks (Go services_test.go, services_check_test.go)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import parse_qsl

import httpx
import pytest

from qbitflow import (
    AuthenticationError,
    BadRequestError,
    BillingOutcome,
    BillingStage,
    CheckoutFees,
    CheckoutSessionStatusValue,
    ConflictError,
    Duration,
    DurationUnit,
    EventType,
    FailureCategory,
    FailureKind,
    FeeItem,
    InvitationStatus,
    NotFoundError,
    QBitFlow,
    RefundStatus,
    RequestOptions,
    ServerError,
    SubscriptionStatus,
    SubscriptionTermsParams,
    TransactionKind,
    ValidationError,
    WebhookSignatureError,
    WebhookSignatureReason,
    WebhookTestEvent,
)

from .conftest import FIXTURES, MEMBER_UUID, TEST_API_KEY, make_client, reply, static

UUID_A = "019eca82-5680-7b00-8000-0000000000c1"
UUID_B = "019eca82-5680-7b00-8000-0000000000c2"
PAY_ID = "pay@019eca82-5680-7b00-8000-0000000000d1"
SUB_ID = "sub@019eca82-5680-7b00-8000-0000000000d2"
BILL_ID = "sub-hist@019eca82-5680-7b00-8000-0000000000d3"
REFUND_ID = "refund@019eca82-5680-7b00-8000-0000000000d4"
EVENT_ID = "evt_bd1a913d-188e-5ac5-a2d6-5fd25cd67301"
CURSOR = "djF8MDFhMGY3NTUtZjIwMC03MDAw"
NEXT = "djF8bmV4dA"
REF = "crm:42@shop.v1"
REF_Q = "reference=crm%3A42%40shop.v1"

AFTER = datetime(2026, 9, 1, 12, tzinfo=timezone(timedelta(hours=2)))
BEFORE = datetime(2026, 10, 1, 0, 0, 0, 500_000, tzinfo=timezone.utc)
AFTER_Q = "2026-09-01T12%3A00%3A00%2B02%3A00"
BEFORE_Q = "2026-10-01T00%3A00%3A00.5Z"

UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}")
EVT = (FIXTURES / "events" / "webhook.test.json").read_text()

# ── Answers (the API's shapes, decimal strings for money) ────────────────────

USDC = {
    "id": 8,
    "code": "BASE:USDC",
    "symbol": "USDC",
    "name": "USD Coin",
    "chain": "BASE",
    "decimals": 6,
    "address": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",
    "mainCurrencyId": 2,
    "test": False,
}
ETH = {"id": 1, "code": "ETH", "symbol": "ETH", "name": "Ethereum", "chain": "ETH", "decimals": 18}
TIME = "2026-10-01T12:00:00Z"
FX: Dict[str, Dict[str, Any]] = {
    "Product": {
        "uuid": "p-1",
        "name": "Pro",
        "priceUsd": "9.99",
        "createdAt": TIME,
        "isActive": True,
        "reference": REF,
        "metadata": {"sku": "PRO"},
        "subscription": {"frequency": {"value": 1, "unit": "months"}},
        "test": True,
    },
    "Customer": {
        "uuid": "c-1",
        "firstName": "Ada",
        "email": "ada@example.com",
        "verified": True,
        "reference": REF,
        "metadata": {"crm": "C-1"},
        "createdAt": TIME,
        "userUuid": "m-1",
    },
    "CreatedCheckoutSession": {
        "link": "https://pay.example/checkout?uuid=pay@1",
        "uuid": "pay@1",
        "expiresAt": "2026-10-01T12:30:00Z",
    },
    "CheckoutSessionStatus": {
        "uuid": "pay@1",
        "status": "created",
        "lastAttempt": {"status": "failed", "code": "insufficient_funds", "at": TIME},
        "expiresAt": "2026-10-01T12:30:00Z",
    },
    "Payment": {
        "uuid": "pay@1",
        "createdAt": TIME,
        "from": "0xfrom",
        "to": "0xto",
        "amount": "10",
        "amountMinUnits": "10000000",
        "amountUsd": "10",
        "currency": USDC,
        "txHash": "0xhash",
        "reference": REF,
        "priceUsd": "9",
        "fees": [{"type": "custom", "label": "Tax", "amountUsd": "1"}],
        "productName": "Pro",
        "metadata": {"orderId": "order-1"},
        "settlement": {
            "feePercent": "0.99",
            "organizationFee": {"address": "0xorg", "feePercent": "5"},
        },
    },
    "Transaction": {
        "type": "bill",
        "uuid": "sub-hist@1",
        "subscriptionUuid": "sub@1",
        "amount": "9.99",
        "amountMinUnits": "9990000",
        "amountUsd": "9.99",
        "currency": USDC,
        "metadata": {},
        "settlement": {"feePercent": "0.99"},
    },
    "Failure": {
        "uuid": "f-1",
        "kind": "bill",
        "txUuid": "sub-hist@1",
        "attempt": 1,
        "code": "insufficient_allowance",
        "category": "allowanceExhausted",
        "attempted": "9.99",
        "attemptedMinUnits": "9990000",
        "attemptedUsd": "9.99",
        "currency": USDC,
    },
    "Subscription": {
        "uuid": "sub@1",
        "reference": REF,
        "status": "stopped",
        "priceUsd": "9.99",
        "currency": USDC,
        "frequency": {"value": 1, "unit": "months"},
        "metadata": {"plan": "pro"},
        "allowance": {"amount": "29.97", "amountMinUnits": "29970000", "remainingPeriods": 3},
        "dunning": {"failedAttempts": 1, "remainingAttempts": 3},
    },
    "Bill": {
        "uuid": "sub-hist@1",
        "subscriptionUuid": "sub@1",
        "amount": "9.99",
        "amountUsd": "9.99",
        "currency": USDC,
        "productName": "Pro",
        "settlement": {"feePercent": "0.99"},
    },
    "TestBill": {"billUuid": "sub-hist@1", "stage": "done", "outcome": "paid", "attempts": 0},
    "Refund": {
        "uuid": "refund@1",
        "txUuid": "pay@1",
        "status": "pending",
        "initiatedBy": "merchant",
        "paid": "10",
        "paidMinUnits": "10000000",
        "refundPercent": "50",
        "amount": "5",
        "amountMinUnits": "5000000",
        "currency": USDC,
        "approval": {"status": "waitingConfirmation"},
    },
    "Member": {
        "userUuid": "m-1",
        "firstName": "Bob",
        "email": "bob@example.com",
        "organizationFeePercent": "5",
        "joinedAt": TIME,
        "acceptedCurrencies": [USDC, ETH],
        "spaceUuid": "s-1",
    },
    "HeldFunds": {
        "ledgers": [
            {
                "txUuid": "pay@1",
                "type": "payment",
                "amountUsd": "10",
                "owed": "9.4",
                "owedMinUnits": "9400000",
                "owedUsd": "9.4",
                "currency": USDC,
            }
        ],
        "totalUsd": "-10.0042",
    },
    "MemberHeldFunds": {"userUuid": "m-1", "totalUsd": "9.4", "count": 2, "oldestAt": TIME},
    "Invitation": {
        "uuid": "i-1",
        "email": "seller@example.com",
        "role": "user",
        "holdFunds": True,
        "organizationFeePercent": "2.5",
        "status": "pending",
        "expiresAt": TIME,
    },
    "Wallet": {
        "uuid": "w-1",
        "address": "0xabc",
        "currency": ETH,
        "tokenWallets": [
            {
                "uuid": "tw-1",
                "currency": USDC,
                "walletUuid": "w-1",
                "balance": {
                    "currency": USDC,
                    "amount": "12.5",
                    "amountMinUnits": "12500000",
                    "amountUsd": "12.5",
                },
            }
        ],
    },
    "AccountingEvent": {
        "txTimeUtc": TIME,
        "type": "refund",
        "chain": "BASE",
        "currency": "USDC",
        "currencyDecimals": 6,
        "grossAmountUsd": "-5",
        "txUuid": "refund@1",
    },
    "WebhookEndpointCreated": {
        "uuid": "e-1",
        "url": "https://x.io/hook",
        "events": ["payment.completed"],
        "payloadVersion": "v2",
        "secret": "whsec_x",
    },
    "Me": {
        "credential": "apiKey",
        "role": "admin",
        "space": {"uuid": "s-1", "organizationName": "Shop", "role": "owner", "test": True},
    },
}
FX["CreatedInvitation"] = dict(FX["Invitation"], link="https://qbitflow.app/invite/i-1")


def fx(name: str, **overrides: Any) -> str:
    return json.dumps(dict(FX[name], **overrides))


def page(item: str) -> str:
    """A page that claims more (``hasMore`` true, a next cursor)."""
    return '{"items":[' + item + '],"hasMore":true,"nextCursor":"' + NEXT + '"}'


def bounded(item: str) -> str:
    """A bounded list's one page."""
    return '{"items":[' + item + '],"hasMore":false}'


Call = Callable[[QBitFlow, Optional[RequestOptions]], Any]


@dataclass
class Route:
    name: str
    call: Call
    method: str
    path: str
    query: str = ""
    body: Optional[Any] = None
    idempotent: bool = False
    accept: str = "application/json"
    status: int = 200
    reply: str = "{}"
    content_type: str = "application/json"
    check: Optional[Callable[[Any], bool]] = field(default=None)


ROUTES: List[Route] = [
    # Products.
    Route(
        "products.list",
        lambda c, o: c.products.list(
            limit=50,
            cursor=CURSOR,
            include_hidden=True,
            subscription=False,
            reference=REF,
            options=o,
        ),
        "GET",
        "/products",
        "cursor=" + CURSOR + "&includeHidden=true&limit=50&" + REF_Q + "&subscription=false",
        reply=page(fx("Product")),
        check=lambda v: len(v.items) == 1
        and v.items[0].uuid == "p-1"
        and v.items[0].subscription is not None
        and v.has_more
        and v.next_cursor == NEXT,
    ),
    Route(
        "products.list default",
        lambda c, o: c.products.list(options=o),
        "GET",
        "/products",
        reply='{"items":[],"hasMore":false}',
        check=lambda v: v.items == [] and not v.has_more and v.next_cursor is None,
    ),
    Route(
        "products.create",
        lambda c, o: c.products.create(
            name="Pro",
            price_usd="9.99",
            reference="pro",
            subscription=SubscriptionTermsParams(
                frequency=Duration(value=1, unit=DurationUnit.MONTHS),
                trial_period=Duration(),
                min_periods=3,
            ),
            metadata={"sku": "PRO"},
            options=o,
        ),
        "POST",
        "/products",
        body={
            "name": "Pro",
            "priceUsd": "9.99",
            "reference": "pro",
            "subscription": {
                "frequency": {"value": 1, "unit": "months"},
                "trialPeriod": {"value": 0},
                "minPeriods": 3,
            },
            "metadata": {"sku": "PRO"},
        },
        idempotent=True,
        status=201,
        reply=fx("Product"),
        check=lambda v: v.uuid == "p-1" and v.price_usd == "9.99" and v.metadata == {"sku": "PRO"},
    ),
    Route(
        "products.get",
        lambda c, o: c.products.get(UUID_A, options=o),
        "GET",
        "/products/" + UUID_A,
        reply=fx("Product"),
    ),
    Route(
        "products.get_by_reference",
        lambda c, o: c.products.get_by_reference(REF, options=o),
        "GET",
        "/products",
        REF_Q,
        reply=bounded(fx("Product")),
        check=lambda v: v.uuid == "p-1" and v.reference == REF,
    ),
    Route(
        "products.update",
        lambda c, o: c.products.update(
            UUID_A,
            description="",
            price_usd=Decimal("12.00"),
            is_active=False,
            metadata={"sku": "PRO-2", "legacy": ""},
            options=o,
        ),
        "PATCH",
        "/products/" + UUID_A,
        body={
            "description": "",
            "priceUsd": "12.00",
            "isActive": False,
            "metadata": {"sku": "PRO-2", "legacy": ""},
        },
        reply=fx("Product"),
    ),
    Route(
        "products.delete",
        lambda c, o: c.products.delete(UUID_A, options=o),
        "DELETE",
        "/products/" + UUID_A,
        status=204,
        reply="",
        check=lambda v: v is None,
    ),
    # Customers.
    Route(
        "customers.create",
        lambda c, o: c.customers.create(
            first_name="Ada",
            last_name="Lovelace",
            email="ada@example.com",
            phone_number="+33 6 12 34 56 78",
            reference="crm-1",
            metadata={"crm": "C-1"},
            options=o,
        ),
        "POST",
        "/customers",
        body={
            "firstName": "Ada",
            "lastName": "Lovelace",
            "email": "ada@example.com",
            "phoneNumber": "+33 6 12 34 56 78",
            "reference": "crm-1",
            "metadata": {"crm": "C-1"},
        },
        idempotent=True,
        status=201,
        reply=fx("Customer"),
        check=lambda v: v.uuid == "c-1"
        and v.first_name == "Ada"
        and not hasattr(v, "verified")
        and v.user_uuid == "m-1",
    ),
    Route(
        "customers.update",
        lambda c, o: c.customers.update(
            UUID_A, email="new@example.com", last_name="", phone_number="", options=o
        ),
        "PATCH",
        "/customers/" + UUID_A,
        body={"email": "new@example.com", "lastName": "", "phoneNumber": ""},
        reply=fx("Customer"),
    ),
    Route(
        "customers.list",
        lambda c, o: c.customers.list(
            limit=5,
            cursor=CURSOR,
            email="ada+1@example.com",
            reference=REF,
            options=o,
        ),
        "GET",
        "/customers",
        "cursor=" + CURSOR + "&email=ada%2B1%40example.com&limit=5&" + REF_Q,
        reply=page(fx("Customer")),
        check=lambda v: len(v.items) == 1 and v.has_more and v.next_cursor == NEXT,
    ),
    Route(
        "customers.get",
        lambda c, o: c.customers.get(UUID_A, options=o),
        "GET",
        "/customers/" + UUID_A,
        reply=fx("Customer"),
    ),
    Route(
        "customers.get_by_reference",
        lambda c, o: c.customers.get_by_reference(REF, options=o),
        "GET",
        "/customers",
        REF_Q,
        reply=bounded(fx("Customer")),
        check=lambda v: v.uuid == "c-1",
    ),
    Route(
        "customers.delete",
        lambda c, o: c.customers.delete(UUID_A, options=o),
        "DELETE",
        "/customers/" + UUID_A,
        status=204,
        reply="",
        check=lambda v: v is None,
    ),
    # Checkout sessions.
    Route(
        "checkout_sessions.create_payment",
        lambda c, o: c.checkout_sessions.create_payment(
            reference="order-1",
            product_name="T-shirt",
            description="Blue",
            price_usd="4.50",
            success_url="https://shop.example/ok?id={{UUID}}",
            cancel_url="https://shop.example/ko",
            customer_reference="crm-1",
            expires_in_minutes=30,
            metadata={"orderId": "order-1"},
            options=o,
        ),
        "POST",
        "/checkout-sessions/payment",
        body={
            "reference": "order-1",
            "productName": "T-shirt",
            "description": "Blue",
            "priceUsd": "4.50",
            "successUrl": "https://shop.example/ok?id={{UUID}}",
            "cancelUrl": "https://shop.example/ko",
            "customerReference": "crm-1",
            "expiresInMinutes": 30,
            "metadata": {"orderId": "order-1"},
        },
        idempotent=True,
        status=201,
        reply=fx("CreatedCheckoutSession"),
        check=lambda v: v.uuid == "pay@1"
        and v.link
        and v.expires_at == datetime(2026, 10, 1, 12, 30, tzinfo=timezone.utc),
    ),
    Route(
        "checkout_sessions.create_subscription",
        lambda c, o: c.checkout_sessions.create_subscription(
            product_uuid=UUID_A,
            customer_uuid=UUID_B,
            frequency=Duration(value=1, unit=DurationUnit.WEEKS),
            trial_period=Duration(value=14, unit="days"),
            min_periods=0,
            options=o,
        ),
        "POST",
        "/checkout-sessions/subscription",
        body={
            "productUuid": UUID_A,
            "customerUuid": UUID_B,
            "frequency": {"value": 1, "unit": "weeks"},
            "trialPeriod": {"value": 14, "unit": "days"},
            "minPeriods": 0,
        },
        idempotent=True,
        status=201,
        reply=fx("CreatedCheckoutSession"),
    ),
    Route(
        "checkout_sessions.get",
        lambda c, o: c.checkout_sessions.get(PAY_ID, options=o),
        "GET",
        "/checkout-sessions/" + PAY_ID,
        reply=fx("CheckoutSessionStatus"),
        check=lambda v: v.status == CheckoutSessionStatusValue.CREATED
        and v.last_attempt is not None
        and v.expires_at is not None,
    ),
    Route(
        "checkout_sessions.get bare uuid",
        lambda c, o: c.checkout_sessions.get(PAY_ID[4:], options=o),
        "GET",
        "/checkout-sessions/" + PAY_ID[4:],
        reply=fx("CheckoutSessionStatus"),
    ),
    Route(
        "checkout_sessions.expire",
        lambda c, o: c.checkout_sessions.expire(SUB_ID, options=o),
        "POST",
        "/checkout-sessions/" + SUB_ID + "/expire",
        reply='{"uuid":"' + SUB_ID + '","status":"expired","expiresAt":"' + TIME + '"}',
        check=lambda v: v.status == CheckoutSessionStatusValue.EXPIRED and v.expires_at,
    ),
    # Payments, the transactions feed, failures.
    Route(
        "payments.list",
        lambda c, o: c.payments.list(
            limit=50,
            cursor=CURSOR,
            customer_uuid=UUID_B,
            product_uuid=UUID_A,
            created_after=AFTER,
            created_before=BEFORE,
            user_uuid=MEMBER_UUID,
            reference=REF,
            refunded=False,
            options=o,
        ),
        "GET",
        "/payments",
        "createdAfter="
        + AFTER_Q
        + "&createdBefore="
        + BEFORE_Q
        + "&cursor="
        + CURSOR
        + "&customerUuid="
        + UUID_B
        + "&limit=50&productUuid="
        + UUID_A
        + "&"
        + REF_Q
        + "&refunded=false&userUuid="
        + MEMBER_UUID,
        reply=page(fx("Payment")),
        check=lambda v: v.items[0].uuid == "pay@1" and v.items[0].currency.code == "BASE:USDC",
    ),
    Route(
        "payments.get",
        lambda c, o: c.payments.get(PAY_ID, include_members=True, options=o),
        "GET",
        "/payments/" + PAY_ID,
        "includeMembers=true",
        reply=fx("Payment"),
        check=lambda v: v.reference == REF
        and v.amount == "10"
        and v.price_usd == "9"
        and v.settlement.organization_fee is not None
        and v.settlement.organization_fee.fee_percent == "5",
    ),
    Route(
        "payments.get bare uuid",
        lambda c, o: c.payments.get(PAY_ID[4:], options=o),
        "GET",
        "/payments/" + PAY_ID[4:],
        reply=fx("Payment"),
    ),
    Route(
        "payments.get_by_reference",
        lambda c, o: c.payments.get_by_reference(REF, options=o),
        "GET",
        "/payments",
        REF_Q,
        reply=bounded(fx("Payment")),
        check=lambda v: v.uuid == "pay@1",
    ),
    Route(
        "transactions.list",
        lambda c, o: c.transactions.list(
            include_members=True,
            refunded=True,
            type=TransactionKind.BILL,
            subscription_uuid=SUB_ID,
            options=o,
        ),
        "GET",
        "/transactions",
        (
            "includeMembers=true&refunded=true"
            "&subscriptionUuid=sub%40019eca82-5680-7b00-8000-0000000000d2&type=bill"
        ),
        reply=page(fx("Transaction")),
        check=lambda v: v.items[0].type == TransactionKind.BILL
        and v.items[0].subscription_uuid == "sub@1",
    ),
    Route(
        "failures.list",
        lambda c, o: c.failures.list(
            limit=3,
            kind=FailureKind.BILL,
            category=FailureCategory.ALLOWANCE_EXHAUSTED,
            subscription_uuid=SUB_ID,
            options=o,
        ),
        "GET",
        "/payment-failures",
        (
            "category=allowanceExhausted&kind=bill&limit=3&subscriptionUu"
            "id=sub%40019eca82-5680-7b00-8000-0000000000d2"
        ),
        reply=page(fx("Failure")),
        check=lambda v: v.items[0].kind == FailureKind.BILL and v.items[0].attempted == "9.99",
    ),
    # Subscriptions.
    Route(
        "subscriptions.list",
        lambda c, o: c.subscriptions.list(
            customer_uuid=UUID_B,
            created_after=AFTER,
            status=SubscriptionStatus.PAST_DUE,
            reference=REF,
            options=o,
        ),
        "GET",
        "/subscriptions",
        "createdAfter=" + AFTER_Q + "&customerUuid=" + UUID_B + "&" + REF_Q + "&status=pastDue",
        reply=page(fx("Subscription")),
        check=lambda v: v.items[0].status == SubscriptionStatus.STOPPED
        and v.items[0].dunning is not None
        and v.items[0].allowance is not None
        and v.items[0].allowance.remaining_periods == 3,
    ),
    Route(
        "subscriptions.list unknown status sent as is",
        lambda c, o: c.subscriptions.list(status="hibernating", options=o),
        "GET",
        "/subscriptions",
        "status=hibernating",
        reply='{"items":[],"hasMore":false}',
    ),
    Route(
        "subscriptions.get",
        lambda c, o: c.subscriptions.get(SUB_ID, include_members=True, options=o),
        "GET",
        "/subscriptions/" + SUB_ID,
        "includeMembers=true",
        reply=fx("Subscription"),
    ),
    Route(
        "subscriptions.get_by_reference",
        lambda c, o: c.subscriptions.get_by_reference(REF, options=o),
        "GET",
        "/subscriptions",
        REF_Q,
        reply=bounded(fx("Subscription")),
        check=lambda v: v.uuid == "sub@1",
    ),
    Route(
        "subscriptions.update",
        lambda c, o: c.subscriptions.update(
            SUB_ID, metadata={"plan": "pro-annual", "coupon": ""}, options=o
        ),
        "PATCH",
        "/subscriptions/" + SUB_ID,
        body={"metadata": {"plan": "pro-annual", "coupon": ""}},
        reply=fx("Subscription", metadata={"plan": "pro-annual"}),
        check=lambda v: v.metadata == {"plan": "pro-annual"},
    ),
    Route(
        "subscriptions.list_bills",
        lambda c, o: c.subscriptions.list_bills(SUB_ID, limit=100, cursor=CURSOR, options=o),
        "GET",
        "/subscriptions/" + SUB_ID + "/bills",
        "cursor=" + CURSOR + "&limit=100",
        reply=page(fx("Bill")),
        check=lambda v: v.items[0].uuid == "sub-hist@1" and v.items[0].subscription_uuid == "sub@1",
    ),
    Route(
        "subscriptions.get_bill",
        lambda c, o: c.subscriptions.get_bill(BILL_ID, include_members=True, options=o),
        "GET",
        "/bills/" + BILL_ID,
        "includeMembers=true",
        reply=fx("Bill"),
        check=lambda v: v.amount == "9.99" and v.settlement.fee_percent == "0.99",
    ),
    Route(
        "subscriptions.cancel 202",
        lambda c, o: c.subscriptions.cancel(SUB_ID, immediate=False, options=o),
        "POST",
        "/subscriptions/" + SUB_ID + "/cancel",
        "immediate=false",
        status=202,
        reply=fx("Subscription"),
        check=lambda v: v.pending and v.subscription.uuid == "sub@1",
    ),
    Route(
        "subscriptions.cancel 200",
        lambda c, o: c.subscriptions.cancel(SUB_ID, options=o),
        "POST",
        "/subscriptions/" + SUB_ID + "/cancel",
        reply='{"uuid":"sub@1","status":"cancelled","cancellationReason":"merchant"}',
        check=lambda v: not v.pending and v.subscription.status == SubscriptionStatus.CANCELLED,
    ),
    Route(
        "subscriptions.test_bill",
        lambda c, o: c.subscriptions.test_bill(SUB_ID, options=o),
        "POST",
        "/subscriptions/" + SUB_ID + "/test-bill",
        reply=fx("TestBill"),
        check=lambda v: v.stage == BillingStage.DONE
        and v.outcome == BillingOutcome.PAID
        and v.bill_uuid == "sub-hist@1",
    ),
    # Refunds.
    Route(
        "refunds.list",
        lambda c, o: c.refunds.list(
            limit=25,
            cursor=CURSOR,
            status=[RefundStatus.APPROVED, "rejected"],
            tx_uuid=PAY_ID,
            held=False,
            include_members=True,
            options=o,
        ),
        "GET",
        "/refunds",
        "cursor="
        + CURSOR
        + "&held=false&includeMembers=true&limit=25&status=approved&status=rejected"
        + "&txUuid=pay%40019eca82-5680-7b00-8000-0000000000d1",
        reply=page(fx("Refund")),
        check=lambda v: len(v.items) == 1
        and v.items[0].approval is not None
        and v.items[0].status == RefundStatus.PENDING
        and v.items[0].refund_percent == "50",
    ),
    Route(
        "refunds.list pending for a member",
        lambda c, o: c.refunds.list(
            status=[RefundStatus.PENDING], user_uuid=MEMBER_UUID, include_members=False, options=o
        ),
        "GET",
        "/refunds",
        "includeMembers=false&status=pending&userUuid=" + MEMBER_UUID,
        reply='{"items":[],"hasMore":false}',
    ),
    Route(
        "refunds.get",
        lambda c, o: c.refunds.get(REFUND_ID, options=o),
        "GET",
        "/refunds/" + REFUND_ID,
        reply=fx("Refund"),
        check=lambda v: v.uuid == "refund@1" and v.amount == "5",
    ),
    # Members.
    Route(
        "members.list",
        lambda c, o: c.members.list(limit=20, cursor=CURSOR, options=o),
        "GET",
        "/members",
        "cursor=" + CURSOR + "&limit=20",
        reply=page(fx("Member")),
        check=lambda v: v.items[0].user_uuid == "m-1"
        and [c.code for c in v.items[0].accepted_currencies] == ["BASE:USDC", "ETH"],
    ),
    Route(
        "members.get",
        lambda c, o: c.members.get(MEMBER_UUID, options=o),
        "GET",
        "/members/" + MEMBER_UUID,
        reply=fx("Member"),
        check=lambda v: v.organization_fee_percent == "5" and v.first_name == "Bob",
    ),
    Route(
        "members.update",
        lambda c, o: c.members.update(MEMBER_UUID, organization_fee_percent="7.5", options=o),
        "PATCH",
        "/members/" + MEMBER_UUID,
        body={"organizationFeePercent": "7.5"},
        reply=fx("Member"),
    ),
    Route(
        "members.remove",
        lambda c, o: c.members.remove(MEMBER_UUID, options=o),
        "DELETE",
        "/members/" + MEMBER_UUID,
        status=204,
        reply="",
        check=lambda v: v is None,
    ),
    Route(
        "members.trust",
        lambda c, o: c.members.trust(MEMBER_UUID, options=o),
        "POST",
        "/members/" + MEMBER_UUID + "/trust",
        reply='{"userUuid":"' + MEMBER_UUID + '","trustedAt":"2026-10-07T10:00:00Z"}',
        check=lambda v: v.trusted_at is not None,
    ),
    Route(
        "members.list_held_funds",
        lambda c, o: c.members.list_held_funds(options=o),
        "GET",
        "/members/held-funds",
        reply=bounded(fx("MemberHeldFunds")),
        check=lambda v: len(v) == 1 and v[0].count == 2 and v[0].total_usd == "9.4",
    ),
    Route(
        "members.get_held_funds",
        lambda c, o: c.members.get_held_funds(MEMBER_UUID, options=o),
        "GET",
        "/members/" + MEMBER_UUID + "/held-funds",
        reply=fx("HeldFunds"),
        check=lambda v: len(v.ledgers) == 1
        and v.total_usd == "-10.0042"
        and v.ledgers[0].owed == "9.4",
    ),
    Route(
        "members.get_own_held_funds",
        lambda c, o: c.members.get_own_held_funds(options=o),
        "GET",
        "/held-funds",
        reply='{"ledgers":[],"totalUsd":"0"}',
        check=lambda v: v.ledgers == [] and v.total_usd == "0",
    ),
    # Invitations.
    Route(
        "invitations.create",
        lambda c, o: c.invitations.create(
            email="seller@example.com",
            hold_funds=True,
            organization_fee_percent="2.5",
            redirect_url="https://shop.example/welcome",
            send_email=False,
            options=o,
        ),
        "POST",
        "/invitations",
        body={
            "email": "seller@example.com",
            "role": "user",
            "holdFunds": True,
            "organizationFeePercent": "2.5",
            "redirectUrl": "https://shop.example/welcome",
            "sendEmail": False,
        },
        idempotent=True,
        status=201,
        reply=fx("CreatedInvitation"),
        check=lambda v: v.link
        and v.uuid == "i-1"
        and v.status == InvitationStatus.PENDING
        and v.hold_funds is True,
    ),
    Route(
        "invitations.create minimal",
        lambda c, o: c.invitations.create(email="seller@example.com", hold_funds=False, options=o),
        "POST",
        "/invitations",
        body={"email": "seller@example.com", "role": "user", "holdFunds": False},
        idempotent=True,
        status=201,
        reply=fx("CreatedInvitation"),
    ),
    Route(
        "invitations.list",
        lambda c, o: c.invitations.list(status=InvitationStatus.PENDING, options=o),
        "GET",
        "/invitations",
        "status=pending",
        reply=page(fx("Invitation")),
    ),
    Route(
        "invitations.revoke",
        lambda c, o: c.invitations.revoke(UUID_A, options=o),
        "DELETE",
        "/invitations/" + UUID_A,
        status=204,
        reply="",
        check=lambda v: v is None,
    ),
    # Wallets.
    Route(
        "wallets.list",
        lambda c, o: c.wallets.list(with_balances=True, options=o),
        "GET",
        "/wallets",
        "withBalances=true",
        reply=bounded(fx("Wallet")),
        check=lambda v: len(v) == 1
        and v[0].address == "0xabc"
        and v[0].token_wallets[0].balance is not None
        and v[0].token_wallets[0].balance.amount == "12.5",
    ),
    Route(
        "wallets.list_for_member",
        lambda c, o: c.wallets.list_for_member(MEMBER_UUID, options=o),
        "GET",
        "/members/" + MEMBER_UUID + "/wallets",
        reply=bounded(fx("Wallet")),
    ),
    Route(
        "wallets.list_accepted_currencies",
        lambda c, o: c.wallets.list_accepted_currencies(user_uuid=MEMBER_UUID, options=o),
        "GET",
        "/wallets/accepted-currencies",
        "userUuid=" + MEMBER_UUID,
        reply=bounded(json.dumps(USDC)),
        check=lambda v: len(v) == 1 and v[0].main_currency_id == 2,
    ),
    # Accounting.
    Route(
        "accounting.export_json",
        lambda c, o: c.accounting.export_json("2026-09-01", "2026-09-30", options=o),
        "GET",
        "/accounting/export",
        "format=json&from=2026-09-01&to=2026-09-30",
        reply=bounded(fx("AccountingEvent")),
        check=lambda v: len(v) == 1 and v[0].type == "refund" and v[0].gross_amount_usd == "-5",
    ),
    Route(
        "accounting.export_csv",
        lambda c, o: c.accounting.export_csv("2026-09-01", "2026-09-30", options=o),
        "GET",
        "/accounting/export",
        "format=csv&from=2026-09-01&to=2026-09-30",
        accept="text/csv, application/json",
        reply="txUuid,type\npay@1,payment\n",
        content_type="text/csv",
        check=lambda v: v == "txUuid,type\npay@1,payment\n",
    ),
    # Webhooks.
    Route(
        "webhooks.verify_remote",
        lambda c, o: c.webhooks.verify_remote(
            UUID_A, b'{"id":"evt_1"}', "t=1790856000,v1=abc", options=o
        ),
        "POST",
        "/webhooks/verify",
        body={"endpointUuid": UUID_A, "body": '{"id":"evt_1"}', "signature": "t=1790856000,v1=abc"},
        reply="{}",
        check=lambda v: v is None,
    ),
    Route(
        "webhooks.endpoints.list",
        lambda c, o: c.webhooks.endpoints.list(limit=10, cursor=CURSOR, options=o),
        "GET",
        "/webhooks/endpoints",
        "cursor=" + CURSOR + "&limit=10",
        reply=page(fx("WebhookEndpointCreated")),
        check=lambda v: len(v.items) == 1 and v.items[0].url == "https://x.io/hook" and v.has_more,
    ),
    Route(
        "webhooks.endpoints.create",
        lambda c, o: c.webhooks.endpoints.create(
            url="https://shop.example/hooks",
            events=[EventType.PAYMENT_COMPLETED, "member.joined"],
            include_members=False,
            description="Shop",
            options=o,
        ),
        "POST",
        "/webhooks/endpoints",
        body={
            "url": "https://shop.example/hooks",
            "events": ["payment.completed", "member.joined"],
            "includeMembers": False,
            "description": "Shop",
        },
        idempotent=True,
        status=201,
        reply=fx("WebhookEndpointCreated"),
        check=lambda v: v.secret == "whsec_x" and v.uuid == "e-1",
    ),
    Route(
        "webhooks.endpoints.get",
        lambda c, o: c.webhooks.endpoints.get(UUID_A, options=o),
        "GET",
        "/webhooks/endpoints/" + UUID_A,
        reply=fx("WebhookEndpointCreated"),
    ),
    Route(
        "webhooks.endpoints.update",
        lambda c, o: c.webhooks.endpoints.update(
            UUID_A,
            events=[],
            description="",
            enabled=True,
            options=o,
        ),
        "PATCH",
        "/webhooks/endpoints/" + UUID_A,
        body={"events": [], "description": "", "enabled": True},
        reply=fx("WebhookEndpointCreated"),
    ),
    Route(
        "webhooks.endpoints.delete",
        lambda c, o: c.webhooks.endpoints.delete(UUID_A, options=o),
        "DELETE",
        "/webhooks/endpoints/" + UUID_A,
        status=204,
        reply="",
        check=lambda v: v is None,
    ),
    Route(
        "webhooks.events.list",
        lambda c, o: c.webhooks.events.list(
            limit=2, cursor=CURSOR, type=EventType.WEBHOOK_TEST, include_members=True, options=o
        ),
        "GET",
        "/webhooks/events",
        "cursor=" + CURSOR + "&includeMembers=true&limit=2&type=webhook.test",
        reply='{"items":[' + EVT + '],"hasMore":false}',
        check=lambda v: len(v.items) == 1
        and not v.has_more
        and isinstance(v.items[0], WebhookTestEvent)
        and v.items[0].data.endpoint_uuid,
    ),
    Route(
        "webhooks.events.list unknown type sent as is",
        lambda c, o: c.webhooks.events.list(type="invoice.created", options=o),
        "GET",
        "/webhooks/events",
        "type=invoice.created",
        reply='{"items":[],"hasMore":false}',
    ),
    Route(
        "webhooks.events.get",
        lambda c, o: c.webhooks.events.get(EVENT_ID, options=o),
        "GET",
        "/webhooks/events/" + EVENT_ID,
        reply=EVT.strip()[:-1]
        + ',"deliveries":[{"endpointUuid":"'
        + UUID_A
        + '","url":"https://x.io","delivered":true,'
        '"attempts":[{"uuid":"'
        + UUID_B
        + '","eventId":"'
        + EVENT_ID
        + '","eventType":"webhook.test","endpointUuid":"'
        + UUID_A
        + '","attempt":1,'
        '"delivered":true,"statusCode":200,"durationMs":12,'
        '"attemptedAt":"2026-10-01T12:00:01+02:00"}]}]}',
        check=lambda v: v.event.type == EventType.WEBHOOK_TEST
        and len(v.deliveries) == 1
        and len(v.deliveries[0].attempts) == 1
        and v.deliveries[0].attempts[0].skipped is False
        and v.deliveries[0].delivered,
    ),
    Route(
        "webhooks.events.get escapes the id",
        lambda c, o: c.webhooks.events.get("evt_a/b c", options=o),
        "GET",
        "/webhooks/events/evt_a%2Fb%20c",
        reply=EVT,
    ),
    # Currencies.
    Route(
        "currencies.list",
        lambda c, o: c.currencies.list(test=True, main=True, options=o),
        "GET",
        "/currencies",
        "main=true&test=true",
        reply=bounded(json.dumps(ETH)),
        check=lambda v: [c.code for c in v] == ["ETH"],
    ),
    Route(
        "currencies.list default",
        lambda c, o: c.currencies.list(options=o),
        "GET",
        "/currencies",
        reply=bounded(json.dumps(USDC) + "," + json.dumps(ETH)),
        check=lambda v: [c.id for c in v] == [8, 1] and v[0].format_amount("1500000") == "1.5",
    ),
    Route(
        "currencies.get",
        lambda c, o: c.currencies.get(8, options=o),
        "GET",
        "/currencies/8",
        reply=json.dumps(USDC),
        check=lambda v: v.id == 8 and v.symbol == "USDC" and v.code == "BASE:USDC",
    ),
    # The client.
    Route(
        "me",
        lambda c, o: c.me(options=o),
        "GET",
        "/me",
        reply=fx("Me"),
        check=lambda v: v.space.organization_name == "Shop",
    ),
]


def serve(route: Route) -> Callable[[httpx.Request, int], httpx.Response]:
    return lambda _r, _n: httpx.Response(
        route.status, content=route.reply.encode(), headers={"Content-Type": route.content_type}
    )


@pytest.mark.parametrize("route", ROUTES, ids=[r.name for r in ROUTES])
def test_service_requests(route: Route) -> None:
    client, server, _ = make_client(serve(route))
    result = route.call(client, None)
    if route.check is not None:
        assert route.check(result), result
    # Request options: On-Behalf-Of, X-Request-Id and a caller's Idempotency-Key.
    route.call(
        client,
        RequestOptions(on_behalf_of=MEMBER_UUID, request_id="req-42", idempotency_key="order-42"),
    )

    assert len(server.requests) == 2
    for r in server.requests:
        assert (r.method, r.path) == (route.method, route.path)
        assert (
            sorted(parse_qsl(r.query)) == sorted(parse_qsl(route.query)) and r.query == route.query
        )
        assert "+" not in r.query
        if route.body is None:
            assert r.body == b"" and "Content-Type" not in r.headers
        else:
            assert r.headers["Content-Type"] == "application/json"
            assert json.loads(r.body) == route.body
        assert r.headers["Accept"] == route.accept
        assert r.headers["X-API-Key"] == TEST_API_KEY

    plain, opted = server.requests
    assert "On-Behalf-Of" not in plain.headers
    assert opted.headers["On-Behalf-Of"] == MEMBER_UUID
    assert opted.headers["X-Request-Id"] == "req-42"
    if route.idempotent:
        assert UUID_RE.fullmatch(plain.headers["Idempotency-Key"])
        assert opted.headers["Idempotency-Key"] == "order-42"
    else:
        assert "Idempotency-Key" not in plain.headers and "Idempotency-Key" not in opted.headers


@pytest.mark.parametrize("route", ROUTES, ids=[r.name for r in ROUTES])
def test_service_on_behalf_of_empty_omits_the_header(route: Route) -> None:
    client, server, _ = make_client(serve(route), on_behalf_of=MEMBER_UUID)
    route.call(client, RequestOptions(on_behalf_of=""))
    route.call(client, None)
    forced, default = server.requests
    assert "On-Behalf-Of" not in forced.headers  # "" = organization level: omitted, never blank
    assert default.headers["On-Behalf-Of"] == MEMBER_UUID


@pytest.mark.parametrize("route", ROUTES, ids=[r.name for r in ROUTES])
def test_service_retries(route: Route) -> None:
    def handler(req: httpx.Request, n: int) -> httpx.Response:
        if n == 0:
            return reply(503, '{"error":"unavailable","code":"network_unavailable"}')
        return serve(route)(req, n)

    client, server, _ = make_client(handler)
    if route.method != "GET" and not route.idempotent:
        with pytest.raises(ServerError) as info:
            route.call(client, None)
        assert info.value.status == 503 and len(server.requests) == 1
        return
    route.call(client, None)
    assert len(server.requests) == 2
    if route.idempotent:
        first, second = server.requests
        assert first.headers["Idempotency-Key"] == second.headers["Idempotency-Key"] != ""
        assert first.body == second.body


def test_six_idempotent_creates() -> None:
    names = {r.name for r in ROUTES if r.idempotent and not r.name.endswith("minimal")}
    assert names == {
        "products.create",
        "customers.create",
        "checkout_sessions.create_payment",
        "checkout_sessions.create_subscription",
        "invitations.create",
        "webhooks.endpoints.create",
    }
    assert {(r.method, r.path) for r in ROUTES if r.idempotent} == {
        ("POST", "/products"),
        ("POST", "/customers"),
        ("POST", "/checkout-sessions/payment"),
        ("POST", "/checkout-sessions/subscription"),
        ("POST", "/invitations"),
        ("POST", "/webhooks/endpoints"),
    }


def test_updates_are_patch_and_deletes_204() -> None:
    updates = {r.name for r in ROUTES if r.method == "PATCH"}
    assert updates == {
        "products.update",
        "customers.update",
        "subscriptions.update",
        "members.update",
        "webhooks.endpoints.update",
    }
    deletes = {r.name: r for r in ROUTES if r.method == "DELETE"}
    assert set(deletes) == {
        "products.delete",
        "customers.delete",
        "members.remove",
        "invitations.revoke",
        "webhooks.endpoints.delete",
    }
    assert all(r.status == 204 and r.reply == "" for r in deletes.values())


def test_removed_and_renamed_methods() -> None:
    client, _, _ = make_client(static(200, "{}"))
    gone = {
        "customers": ["get_by_email"],
        "subscriptions": ["get_public_history", "execute_test_billing"],
        "checkout_sessions": ["get_status"],
        "payments": ["list_combined", "iterate_combined"],
        "refunds": ["initiate", "create", "list_inactive", "iterate_inactive"],
        "wallets": ["list_supported_currencies"],
        "currencies": ["list_available", "list_main"],
    }
    for service, names in gone.items():
        for name in names:
            assert not hasattr(getattr(client, service), name), f"{service}.{name}"
    for service, name in (
        ("transactions", "list"),
        ("transactions", "iterate"),
        ("refunds", "get"),
        ("subscriptions", "update"),
        ("subscriptions", "test_bill"),
        ("checkout_sessions", "get"),
        ("products", "iterate"),
    ):
        assert callable(getattr(getattr(client, service), name))
    assert callable(client.webhooks.endpoints.iterate)


def test_errors_typed() -> None:
    client, _, _ = make_client(
        static(409, '{"error":"Already sent","code":"tx_already_sent","requestId":"r-1"}')
    )
    with pytest.raises(ConflictError) as info:
        client.checkout_sessions.expire(PAY_ID)
    assert info.value.code == "tx_already_sent" and info.value.request_id == "r-1"

    client2, _, _ = make_client(static(400, '{"error":"test mode only","code":"test_mode_only"}'))
    with pytest.raises(BadRequestError) as bad:
        client2.subscriptions.test_bill(SUB_ID)
    assert bad.value.code == "test_mode_only"

    # Another space's subscription (or none) is still a 404.
    client3, _, _ = make_client(static(404, '{"error":"not found","code":"not_found"}'))
    with pytest.raises(NotFoundError):
        client3.subscriptions.cancel(SUB_ID)
    with pytest.raises(NotFoundError):
        client3.subscriptions.test_bill(SUB_ID)
    with pytest.raises(NotFoundError):
        client3.products.delete(UUID_A)
    with pytest.raises(NotFoundError):
        client3.refunds.get(REFUND_ID)
    with pytest.raises(NotFoundError):
        list(client3.customers.iterate())

    client4, _, _ = make_client(
        static(400, '{"error":"too long","code":"validation_failed","details":{"max":92}}')
    )
    with pytest.raises(ValidationError) as window:
        client4.accounting.export_csv("2026-01-01", "2026-09-30")
    assert window.value.status == 400 and window.value.details == {"max": 92}


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.subscriptions.cancel(SUB_ID),
        lambda c: c.subscriptions.cancel(SUB_ID, immediate=False),
        lambda c: c.subscriptions.test_bill(SUB_ID),
    ],
    ids=["cancel", "cancel-at-period-end", "test_bill"],
)
def test_cancelled_subscription_is_a_conflict(call: Callable[[Any], Any]) -> None:
    """A cancelled subscription's cancel and test bill answer 409, not 404."""
    client, server, _ = make_client(
        static(
            409,
            '{"error":"subscription already stopped or inactive",'
            '"code":"subscription_already_stopped_or_inactive","requestId":"r-5"}',
        )
    )
    with pytest.raises(ConflictError) as info:
        call(client)
    assert not isinstance(info.value, NotFoundError)
    assert info.value.status == 409
    assert info.value.code == "subscription_already_stopped_or_inactive"
    assert info.value.request_id == "r-5"
    assert len(server.requests) == 1  # never retried


def test_cancel_without_body() -> None:
    client, _, _ = make_client(lambda _r, _n: httpx.Response(202))
    with pytest.raises(ServerError):
        client.subscriptions.cancel(SUB_ID)


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.products.get(UUID_A),
        lambda c: c.payments.list(),
        lambda c: c.currencies.list(),
        lambda c: c.wallets.list(),
        lambda c: c.members.list_held_funds(),
        lambda c: c.accounting.export_json("2026-09-01", "2026-09-01"),
        lambda c: c.products.get_by_reference(REF),
    ],
    ids=["object", "page", "currencies", "wallets", "held funds", "export", "get_by_reference"],
)
@pytest.mark.parametrize("body", ["[]", "null", '[{"id":8}]', '"x"', ""], ids=repr)
def test_wrong_body_shapes_are_server_errors(call: Callable[[QBitFlow], Any], body: str) -> None:
    # Every answer is a JSON object (lists are pages): a bare array, null or nothing is a fault.
    client, _, _ = make_client(static(200, body))
    with pytest.raises(ServerError) as info:
        call(client)
    assert info.value.status == 200


# ── get_by_reference: a list filter, compared exactly ────────────────────────

LOOKUPS = [
    ("products", "/products", "Product"),
    ("customers", "/customers", "Customer"),
    ("payments", "/payments", "Payment"),
    ("subscriptions", "/subscriptions", "Subscription"),
]


@pytest.mark.parametrize("service, path, model", LOOKUPS, ids=[x[0] for x in LOOKUPS])
def test_get_by_reference_returns_the_exact_match(service: str, path: str, model: str) -> None:
    other = fx(model, uuid="other", reference="crm:41")
    match = fx(model, uuid="match", reference=REF)
    client, server, _ = make_client(static(200, bounded(other + "," + match)))
    got = getattr(client, service).get_by_reference(REF)
    assert got.uuid == "match" and got.reference == REF
    assert [(r.method, r.path, r.query) for r in server.requests] == [("GET", path, REF_Q)]


@pytest.mark.parametrize("service, path, model", LOOKUPS, ids=[x[0] for x in LOOKUPS])
@pytest.mark.parametrize(
    "items",
    [
        "",  # an empty page
        "CASE",  # the same reference in another case: not the one asked
        "OTHER",  # a server that ignored the filter
    ],
)
def test_get_by_reference_not_found(service: str, path: str, model: str, items: str) -> None:
    item = {
        "": "",
        "CASE": fx(model, reference=REF.upper()),
        "OTHER": fx(model, reference="team"),
    }[items]

    def handler(_r: httpx.Request, _n: int) -> httpx.Response:
        return reply(200, bounded(item), {"X-Request-Id": "req-7"})

    client, server, _ = make_client(handler)
    with pytest.raises(NotFoundError) as info:
        getattr(client, service).get_by_reference(REF)
    err = info.value
    assert err.status == 404 and err.code == "not_found" and err.request_id == "req-7"
    assert err.details == {} and err.field_errors == []
    assert "with this reference" in err.message
    assert len(server.requests) == 1  # a 200 answer: never retried


def test_get_by_reference_errors_pass_through() -> None:
    client, _, _ = make_client(static(401, '{"error":"bad key","code":"unauthorized"}'))
    with pytest.raises(AuthenticationError):
        client.customers.get_by_reference(REF)


@pytest.mark.parametrize("service", [x[0] for x in LOOKUPS])
@pytest.mark.parametrize("ref", ["bad ref", "", None, "r" * 101, "a/b"], ids=repr)
def test_get_by_reference_validates_first(service: str, ref: Any) -> None:
    client, server, _ = make_client(static(200, bounded("")))
    with pytest.raises(ValidationError) as info:
        getattr(client, service).get_by_reference(ref)
    assert [f.field for f in info.value.field_errors] == ["reference"]
    assert server.requests == []


# ── Bounded lists: items unwrapped, a claimed next page followed ─────────────

BOUNDED = [
    (
        "currencies.list",
        lambda c: c.currencies.list(test=True),
        "/currencies",
        "test=true",
        lambda i: json.dumps(dict(USDC, id=i)),
        lambda v: v.id,
    ),
    (
        "wallets.list",
        lambda c: c.wallets.list(with_balances=True),
        "/wallets",
        "withBalances=true",
        lambda i: json.dumps({"uuid": str(i)}),
        lambda v: int(v.uuid),
    ),
    (
        "wallets.list_for_member",
        lambda c: c.wallets.list_for_member(MEMBER_UUID),
        "/members/" + MEMBER_UUID + "/wallets",
        "",
        lambda i: json.dumps({"uuid": str(i)}),
        lambda v: int(v.uuid),
    ),
    (
        "wallets.list_accepted_currencies",
        lambda c: c.wallets.list_accepted_currencies(user_uuid=MEMBER_UUID),
        "/wallets/accepted-currencies",
        "userUuid=" + MEMBER_UUID,
        lambda i: json.dumps({"id": i}),
        lambda v: v.id,
    ),
    (
        "members.list_held_funds",
        lambda c: c.members.list_held_funds(),
        "/members/held-funds",
        "",
        lambda i: json.dumps({"userUuid": str(i), "count": i}),
        lambda v: v.count,
    ),
    (
        "accounting.export_json",
        lambda c: c.accounting.export_json("2026-09-01", "2026-09-30"),
        "/accounting/export",
        "format=json&from=2026-09-01&to=2026-09-30",
        lambda i: json.dumps({"txUuid": "pay@" + str(i), "currencyDecimals": i}),
        lambda v: v.currency_decimals,
    ),
]


def _page_of(item: Callable[[int], str], ids: List[int], more: bool, cursor: str = "") -> str:
    body: Dict[str, Any] = {"items": [json.loads(item(i)) for i in ids], "hasMore": more}
    if cursor:
        body["nextCursor"] = cursor
    return json.dumps(body)


@pytest.mark.parametrize(
    "name, call, path, filters, item, key", BOUNDED, ids=[b[0] for b in BOUNDED]
)
def test_bounded_list_one_page(
    name: str, call: Any, path: str, filters: str, item: Any, key: Any
) -> None:
    client, server, _ = make_client(static(200, _page_of(item, [1, 2], False)))
    assert [key(v) for v in call(client)] == [1, 2]
    assert len(server.requests) == 1
    assert server.requests[0].path == path and server.requests[0].query == filters
    empty, _, _ = make_client(static(200, '{"items":[],"hasMore":false}'))
    assert call(empty) == []
    absent, _, _ = make_client(static(200, "{}"))
    assert call(absent) == []


@pytest.mark.parametrize(
    "name, call, path, filters, item, key", BOUNDED, ids=[b[0] for b in BOUNDED]
)
def test_bounded_list_follows_has_more(
    name: str, call: Any, path: str, filters: str, item: Any, key: Any
) -> None:
    def handler(req: httpx.Request, _n: int) -> httpx.Response:
        cursor = req.url.params.get("cursor", "")
        if cursor == "":
            return reply(200, _page_of(item, [1, 2], True, "djF8Mg"))
        if cursor == "djF8Mg":
            return reply(200, _page_of(item, [3], True, "djF8Mw"))
        return reply(200, _page_of(item, [4], False))

    client, server, _ = make_client(handler)
    assert [key(v) for v in call(client)] == [1, 2, 3, 4]
    assert len(server.requests) == 3
    want_filters = sorted(parse_qsl(filters))
    for r, cursor in zip(server.requests, ["", "djF8Mg", "djF8Mw"]):
        q = parse_qsl(r.query)
        assert r.path == path
        assert sorted(kv for kv in q if kv[0] != "cursor") == want_filters  # filters kept
        assert dict(q).get("cursor", "") == cursor


@pytest.mark.parametrize(
    "pages, requests",
    [
        # hasMore true without a nextCursor: stop.
        ([(1, True, "")], 1),
        # A cursor that does not move: stop after it was requested once.
        ([(1, True, "djF8YQ"), (2, True, "djF8YQ")], 2),
        # An empty page that claims more: stop.
        ([(1, True, "djF8YQ"), (None, True, "djF8Yg")], 2),
    ],
    ids=["no cursor", "cursor did not move", "empty page"],
)
def test_bounded_list_guards(pages: List[Any], requests: int) -> None:
    def handler(_r: httpx.Request, n: int) -> httpx.Response:
        ident, more, cursor = pages[min(n, len(pages) - 1)]
        items = [] if ident is None else [dict(USDC, id=ident)]
        body: Dict[str, Any] = {"items": items, "hasMore": more}
        if cursor:
            body["nextCursor"] = cursor
        return reply(200, json.dumps(body))

    client, server, _ = make_client(handler)
    got = client.currencies.list()
    assert len(server.requests) == requests
    assert [c.id for c in got] == [p[0] for p in pages if p[0] is not None]


def test_bounded_list_error_mid_walk() -> None:
    def handler(req: httpx.Request, _n: int) -> httpx.Response:
        if req.url.params.get("cursor", "") == "":
            return reply(200, '{"items":[{"id":1}],"hasMore":true,"nextCursor":"djF8YQ"}')
        return reply(401, '{"error":"unauthorized","code":"unauthorized"}')

    client, _, _ = make_client(handler)
    with pytest.raises(AuthenticationError):
        client.currencies.list()


# ── Client-side validation: nothing is sent ──────────────────────────────────


VALIDATION_CASES: Dict[str, Any] = {
    # Path ids.
    "products.get empty": ("uuid", lambda c: c.products.get("")),
    "products.get not uuid": ("uuid", lambda c: c.products.get("42")),
    "products.update": ("uuid", lambda c: c.products.update("../x")),
    "products.delete": ("uuid", lambda c: c.products.delete("")),
    "products.get_by_reference": ("reference", lambda c: c.products.get_by_reference("  ")),
    "customers.get": ("uuid", lambda c: c.customers.get("pay@" + UUID_A)),
    "customers.update": ("uuid", lambda c: c.customers.update("")),
    "customers.delete": ("uuid", lambda c: c.customers.delete("x")),
    "customers.get_by_reference": ("reference", lambda c: c.customers.get_by_reference("")),
    "checkout_sessions.get": ("uuid", lambda c: c.checkout_sessions.get("")),
    "checkout_sessions.expire": ("uuid", lambda c: c.checkout_sessions.expire("cs_123")),
    "payments.get": ("uuid", lambda c: c.payments.get("pay@123")),
    "payments.get_by_reference": ("reference", lambda c: c.payments.get_by_reference("")),
    "subscriptions.get": ("uuid", lambda c: c.subscriptions.get("bad@" + UUID_A)),
    "subscriptions.get_by_reference": ("reference", lambda c: c.subscriptions.get_by_reference("")),
    "subscriptions.update uuid": ("uuid", lambda c: c.subscriptions.update("x", metadata={})),
    "subscriptions.list_bills": ("uuid", lambda c: c.subscriptions.list_bills("")),
    "subscriptions.get_bill": ("billUuid", lambda c: c.subscriptions.get_bill("1")),
    "subscriptions.cancel": ("uuid", lambda c: c.subscriptions.cancel("", immediate=True)),
    "subscriptions.test_bill": ("uuid", lambda c: c.subscriptions.test_bill("sub")),
    "refunds.get": ("uuid", lambda c: c.refunds.get("refund@x")),
    "members.get": ("userUuid", lambda c: c.members.get("")),
    "members.update": ("userUuid", lambda c: c.members.update("1", organization_fee_percent="0")),
    "members.remove": ("userUuid", lambda c: c.members.remove("")),
    "members.trust": ("userUuid", lambda c: c.members.trust("x")),
    "members.get_held_funds": ("userUuid", lambda c: c.members.get_held_funds("")),
    "invitations.revoke": ("uuid", lambda c: c.invitations.revoke("")),
    "wallets.list_for_member": ("userUuid", lambda c: c.wallets.list_for_member("1")),
    "webhooks.endpoints.get": ("uuid", lambda c: c.webhooks.endpoints.get("")),
    "webhooks.endpoints.update": ("uuid", lambda c: c.webhooks.endpoints.update("x")),
    "webhooks.endpoints.delete": ("uuid", lambda c: c.webhooks.endpoints.delete("")),
    "webhooks.events.get": ("id", lambda c: c.webhooks.events.get("")),
    "webhooks.events.get dot": ("id", lambda c: c.webhooks.events.get("..")),
    "webhooks.verify_remote uuid": (
        "endpointUuid",
        lambda c: c.webhooks.verify_remote("", b"{}", "t=1,v1=a"),
    ),
    "webhooks.verify_remote body": (
        "body",
        lambda c: c.webhooks.verify_remote(UUID_A, b"", "t=1,v1=a"),
    ),
    "webhooks.verify_remote utf8": (
        "body",
        lambda c: c.webhooks.verify_remote(UUID_A, b"\xff", "t=1,v1=a"),
    ),
    "webhooks.verify_remote type": (
        "body",
        lambda c: c.webhooks.verify_remote(UUID_A, 5, "t=1,v1=a"),
    ),
    "currencies.get": ("id", lambda c: c.currencies.get(0)),
    "currencies.get bool": ("id", lambda c: c.currencies.get(True)),
    # Required params.
    "products.create name": ("name", lambda c: c.products.create(name=None, price_usd=None)),
    "products.create price": ("priceUsd", lambda c: c.products.create(name="Pro", price_usd=None)),
    "customers.create email": ("email", lambda c: c.customers.create(first_name="Ada", email=None)),
    "customers.create first name": (
        "firstName",
        lambda c: c.customers.create(first_name=None, email="a@b.co"),
    ),
    "checkout_sessions.create_payment": (
        "productUuid",
        lambda c: c.checkout_sessions.create_payment(),
    ),
    "members.update fee": (
        "organizationFeePercent",
        lambda c: c.members.update(MEMBER_UUID, organization_fee_percent=None),
    ),
    "invitations.create email": (
        "email",
        lambda c: c.invitations.create(email=None, hold_funds=False),
    ),
    "invitations.create hold funds": (
        "holdFunds",
        lambda c: c.invitations.create(email="a@b.co", hold_funds=None),
    ),
    "webhooks.endpoints.create": ("url", lambda c: c.webhooks.endpoints.create(url=None)),
    # Money is never a float or an int.
    "products.create float price": (
        "priceUsd",
        lambda c: c.products.create(name="Pro", price_usd=9.99),
    ),
    "products.create int price": (
        "priceUsd",
        lambda c: c.products.create(name="Pro", price_usd=10),
    ),
    "products.update float price": (
        "priceUsd",
        lambda c: c.products.update(UUID_A, price_usd=9.99),
    ),
    "checkout_sessions.create_payment float price": (
        "priceUsd",
        lambda c: c.checkout_sessions.create_payment(product_name="Pro", price_usd=4.99),
    ),
    "checkout_sessions.create_payment float fee": (
        "fees.items[0].amountUsd",
        lambda c: c.checkout_sessions.create_payment(
            product_uuid=UUID_A, fees=CheckoutFees(items=[FeeItem("Tax", 1.5)])
        ),
    ),
    "members.update int fee": (
        "organizationFeePercent",
        lambda c: c.members.update(MEMBER_UUID, organization_fee_percent=5),
    ),
    "invitations.create float fee": (
        "organizationFeePercent",
        lambda c: c.invitations.create(
            email="a@b.co", hold_funds=False, organization_fee_percent=2.5
        ),
    ),
    # Invalid params.
    "products.create price zero": (
        "priceUsd",
        lambda c: c.products.create(name="Pro", price_usd="0.00"),
    ),
    "products.create metadata": (
        "metadata",
        lambda c: c.products.create(name="Pro", price_usd="1", metadata={"bad key": "x"}),
    ),
    "products.update name": ("name", lambda c: c.products.update(UUID_A, name="<b>")),
    "products.list cursor": ("cursor", lambda c: c.products.list(cursor="c" * 201)),
    "products.list reference": ("reference", lambda c: c.products.list(reference="a b")),
    "customers.update phone": (
        "phoneNumber",
        lambda c: c.customers.update(UUID_A, phone_number="call me"),
    ),
    "customers.update metadata value": (
        "metadata.note",
        lambda c: c.customers.update(UUID_A, metadata={"note": "a\tb"}),
    ),
    "customers.list email": ("email", lambda c: c.customers.list(email="x")),
    "checkout_sessions.create_payment mixed": (
        "productUuid",
        lambda c: c.checkout_sessions.create_payment(product_uuid=UUID_A, product_reference="pro"),
    ),
    "checkout_sessions.create_subscription fee label": (
        "fees.items[0].label",
        lambda c: c.checkout_sessions.create_subscription(
            product_uuid=UUID_A, fees=CheckoutFees(items=[FeeItem("", "2")])
        ),
    ),
    "checkout_sessions.create_subscription frequency": (
        "frequency.unit",
        lambda c: c.checkout_sessions.create_subscription(
            product_uuid=UUID_A, frequency=Duration(value=1)
        ),
    ),
    "payments.list exclusive": (
        "userUuid",
        lambda c: c.payments.list(include_members=True, user_uuid=MEMBER_UUID),
    ),
    "transactions.list type": ("type", lambda c: c.transactions.list(type="subscriptionHistory")),
    "transactions.list subscription": (
        "subscriptionUuid",
        lambda c: c.transactions.list(subscription_uuid="sub@x"),
    ),
    "failures.list kind": ("kind", lambda c: c.failures.list(kind="refund")),
    "subscriptions.update metadata": (
        "metadata.k",
        lambda c: c.subscriptions.update(SUB_ID, metadata={"k": "x" * 501}),
    ),
    "refunds.list user_uuid": ("userUuid", lambda c: c.refunds.list(user_uuid="1")),
    "refunds.list exclusive": (
        "userUuid",
        lambda c: c.refunds.list(include_members=True, user_uuid=MEMBER_UUID),
    ),
    "refunds.list status": ("status[0]", lambda c: c.refunds.list(status=["completed"])),
    "refunds.list too many statuses": (
        "status",
        lambda c: c.refunds.list(status=[RefundStatus.PENDING] * 6),
    ),
    "members.update over 50": (
        "organizationFeePercent",
        lambda c: c.members.update(MEMBER_UUID, organization_fee_percent="51"),
    ),
    "invitations.create empty": (
        "email",
        lambda c: c.invitations.create(email="", hold_funds=True),
    ),
    "invitations.list status": ("status", lambda c: c.invitations.list(status="open")),
    "wallets.list_accepted_currencies": (
        "userUuid",
        lambda c: c.wallets.list_accepted_currencies(user_uuid="x"),
    ),
    "accounting.export_json order": (
        "to",
        lambda c: c.accounting.export_json("2026-09-30", "2026-09-01"),
    ),
    "accounting.export_csv date": (
        "from",
        lambda c: c.accounting.export_csv("2026-02-30", "2026-03-01"),
    ),
    "webhooks.endpoints.create url": ("url", lambda c: c.webhooks.endpoints.create(url="ftp://x")),
    "webhooks.endpoints.update test event": (
        "events[0]",
        lambda c: c.webhooks.endpoints.update(UUID_A, events=[EventType.WEBHOOK_TEST]),
    ),
    "webhooks.endpoints.list cursor": (
        "cursor",
        lambda c: c.webhooks.endpoints.list(cursor="e" * 201),
    ),
    "webhooks.events.list cursor": ("cursor", lambda c: c.webhooks.events.list(cursor=7)),
}


@pytest.mark.parametrize("name", sorted(VALIDATION_CASES))
def test_validation_before_request(name: str) -> None:
    field_name, call = VALIDATION_CASES[name]
    client, server, _ = make_client(static(200, "{}"))
    with pytest.raises(ValidationError) as info:
        call(client)
    assert info.value.status is None and info.value.code == ""
    assert field_name in [f.field for f in info.value.field_errors]
    assert server.requests == []


def test_iterate_validation_is_lazy_and_sends_nothing() -> None:
    client, server, _ = make_client(static(200, "{}"))
    it = client.subscriptions.iterate_bills("nope")
    with pytest.raises(ValidationError):
        next(it)
    with pytest.raises(ValidationError):
        list(client.members.iterate(options=RequestOptions(on_behalf_of="x")))
    with pytest.raises(ValidationError):
        list(client.refunds.iterate(status=["nope"]))
    with pytest.raises(ValidationError):
        list(client.transactions.iterate(type="nope"))
    assert server.requests == []


@pytest.mark.parametrize(
    "status, body, check",
    [
        (200, "{}", lambda e: e is None),
        (204, "", lambda e: e is None),
        (
            400,
            '{"error":"invalid signature","code":"invalid_signature","requestId":"r-9"}',
            lambda e: isinstance(e, WebhookSignatureError)
            and e.reason == WebhookSignatureReason.INVALID_SIGNATURE
            and e.status == 400
            and e.code == "invalid_signature"
            and e.request_id == "r-9",
        ),
        (
            400,
            (
                '{"error":"invalid","code":"validation_failed","details":{"er'
                'rors":[{"field":"signature","message":"required"}]}}'
            ),
            lambda e: isinstance(e, ValidationError)
            and e.status == 400
            and not isinstance(e, WebhookSignatureError),
        ),
        (
            400,
            '{"error":"bad","code":"foreign_key_violation"}',
            lambda e: isinstance(e, BadRequestError) and not isinstance(e, WebhookSignatureError),
        ),
        (404, '{"error":"not found","code":"not_found"}', lambda e: isinstance(e, NotFoundError)),
        (500, '{"error":"boom","code":"internal"}', lambda e: isinstance(e, ServerError)),
    ],
)
def test_verify_remote_errors(
    status: int, body: str, check: Callable[[Optional[Exception]], bool]
) -> None:
    client, server, _ = make_client(static(status, body))
    error: Optional[Exception] = None
    try:
        client.webhooks.verify_remote(UUID_A, b'{"id":"evt_1"}', "t=1790856000,v1=abc")
    except Exception as exc:  # noqa: BLE001 - checked below
        error = exc
    assert check(error), error
    assert len(server.requests) == 1  # verify is never retried


def test_verify_remote_local_failures() -> None:
    client, server, _ = make_client(static(200, "{}"))
    with pytest.raises(WebhookSignatureError) as info:
        client.webhooks.verify_remote(UUID_A, b'{"id":"evt_1"}', "")
    assert info.value.reason == WebhookSignatureReason.MISSING_HEADER
    with pytest.raises(ValidationError):
        client.webhooks.verify_remote(UUID_A, b"a" * ((1 << 20) + 1), "t=1,v1=a")
    client.webhooks.verify_remote(UUID_A, "a str body ☃", "t=1,v1=a")
    assert len(server.requests) == 1
    assert json.loads(server.requests[0].body)["body"] == "a str body ☃"


# ── Iterators over two pages, per method ─────────────────────────────────────


def uuid_item(i: int) -> str:
    return f'{{"uuid":"id{i}"}}'


ITER_CASES = [
    (
        "products.iterate",
        "/products",
        "includeHidden=true&limit=2",
        uuid_item,
        lambda c: c.products.iterate(limit=2, include_hidden=True),
        lambda v: v.uuid,
    ),
    (
        "customers.iterate",
        "/customers",
        "email=a%40b.co&limit=2",
        uuid_item,
        lambda c: c.customers.iterate(limit=2, email="a@b.co"),
        lambda v: v.uuid,
    ),
    (
        "payments.iterate",
        "/payments",
        "createdAfter=" + AFTER_Q + "&limit=2",
        uuid_item,
        lambda c: c.payments.iterate(limit=2, created_after=AFTER),
        lambda v: v.uuid,
    ),
    (
        "transactions.iterate",
        "/transactions",
        "type=payment",
        uuid_item,
        lambda c: c.transactions.iterate(type=TransactionKind.PAYMENT),
        lambda v: v.uuid,
    ),
    (
        "failures.iterate",
        "/payment-failures",
        "category=reverted",
        uuid_item,
        lambda c: c.failures.iterate(category=FailureCategory.REVERTED),
        lambda v: v.uuid,
    ),
    (
        "subscriptions.iterate",
        "/subscriptions",
        "includeMembers=true&status=active",
        uuid_item,
        lambda c: c.subscriptions.iterate(include_members=True, status=SubscriptionStatus.ACTIVE),
        lambda v: v.uuid,
    ),
    (
        "subscriptions.iterate_bills",
        "/subscriptions/" + SUB_ID + "/bills",
        "limit=100",
        uuid_item,
        lambda c: c.subscriptions.iterate_bills(SUB_ID, limit=100),
        lambda v: v.uuid,
    ),
    (
        "refunds.iterate",
        "/refunds",
        "held=false&status=pending",
        uuid_item,
        lambda c: c.refunds.iterate(held=False, status=[RefundStatus.PENDING]),
        lambda v: v.uuid,
    ),
    (
        "members.iterate",
        "/members",
        "limit=1",
        lambda i: f'{{"userUuid":"id{i}"}}',
        lambda c: c.members.iterate(limit=1),
        lambda v: v.user_uuid,
    ),
    (
        "invitations.iterate",
        "/invitations",
        "status=expired",
        uuid_item,
        lambda c: c.invitations.iterate(status=InvitationStatus.EXPIRED),
        lambda v: v.uuid,
    ),
    (
        "webhooks.endpoints.iterate",
        "/webhooks/endpoints",
        "limit=5",
        uuid_item,
        lambda c: c.webhooks.endpoints.iterate(limit=5),
        lambda v: v.uuid,
    ),
    (
        "webhooks.events.iterate",
        "/webhooks/events",
        "type=payment.completed",
        lambda i: f'{{"id":"id{i}","type":"payment.completed","version":"v2",'
        '"createdAt":"2026-10-01T12:00:00Z","data":{}}',
        lambda c: c.webhooks.events.iterate(type=EventType.PAYMENT_COMPLETED),
        lambda v: v.id,
    ),
]


@pytest.mark.parametrize(
    "name, path, filters, item, walk, key", ITER_CASES, ids=[c[0] for c in ITER_CASES]
)
def test_service_iterators(
    name: str, path: str, filters: str, item: Callable[[int], str], walk: Any, key: Any
) -> None:
    def handler(req: httpx.Request, _n: int) -> httpx.Response:
        cursor = req.url.params.get("cursor", "")
        if cursor == "":
            return reply(
                200,
                '{"items":[' + item(0) + "," + item(1) + '],"hasMore":true,"nextCursor":"djF8MQ"}',
            )
        if cursor == "djF8MQ":
            return reply(200, '{"items":[' + item(2) + '],"hasMore":false}')
        return reply(400, '{"error":"bad cursor","code":"validation_failed"}')

    client, server, _ = make_client(handler)
    assert [key(v) for v in walk(client)] == ["id0", "id1", "id2"]
    assert len(server.requests) == 2
    for i, r in enumerate(server.requests):
        assert r.method == "GET" and r.path == path
        q = dict(parse_qsl(r.query))
        cursor = q.pop("cursor", "")
        assert "&".join(f"{k}={v}" for k, v in sorted(q.items())) == "&".join(
            f"{k}={v}" for k, v in sorted(parse_qsl(filters))
        )
        assert cursor == ["", "djF8MQ"][i]
    # An early break stops after the first page.
    for v in walk(client):
        break
    assert len(server.requests) == 3


def test_iterator_stops_on_has_more_false_even_with_a_cursor() -> None:
    client, server, _ = make_client(
        static(200, '{"items":[{"uuid":"a"}],"hasMore":false,"nextCursor":"djF8eA"}')
    )
    assert [p.uuid for p in client.payments.iterate()] == ["a"]
    assert len(server.requests) == 1


def test_iterator_errors_and_resume() -> None:
    def handler(req: httpx.Request, _n: int) -> httpx.Response:
        if req.url.params.get("cursor", "") == "":
            return reply(200, '{"items":[{"uuid":"id0"}],"hasMore":true,"nextCursor":"djF8MA"}')
        return reply(401, '{"error":"unauthorized","code":"unauthorized"}')

    client, _, _ = make_client(handler)
    got = []
    with pytest.raises(AuthenticationError):
        for p in client.payments.iterate():
            got.append(p.uuid)
    assert got == ["id0"]


# ── Checkout fees: the create_payment body ───────────────────────────────────

ABSENT = object()

FEES_BODIES: List[Any] = [
    ("no fees", None, ABSENT),
    ("empty", CheckoutFees(), {}),
    ("processing fee on", CheckoutFees(processing_fee=True), {"processingFee": True}),
    ("processing fee off", CheckoutFees(processing_fee=False), {"processingFee": False}),
    (
        "a string",
        CheckoutFees(items=[FeeItem("Shipping", "0.75", "Standard, 3 to 5 days")]),
        {
            "items": [
                {"label": "Shipping", "description": "Standard, 3 to 5 days", "amountUsd": "0.75"}
            ]
        },
    ),
    (
        "a Decimal",
        CheckoutFees(items=[FeeItem("VAT", Decimal("12.50"))]),
        {"items": [{"label": "VAT", "amountUsd": "12.50"}]},
    ),
    (
        "trailing zeros kept",
        CheckoutFees(items=[FeeItem("Tax", "3.00")]),
        {"items": [{"label": "Tax", "amountUsd": "3.00"}]},
    ),
    (
        "empty description omitted",
        CheckoutFees(items=[FeeItem("VAT", "1", "")]),
        {"items": [{"label": "VAT", "amountUsd": "1"}]},
    ),
    (
        "lines in order, then the processing fee flag",
        CheckoutFees(processing_fee=True, items=[FeeItem("A", "1"), FeeItem("B", "2.5")]),
        {
            "processingFee": True,
            "items": [{"label": "A", "amountUsd": "1"}, {"label": "B", "amountUsd": "2.5"}],
        },
    ),
]


@pytest.mark.parametrize("name, fees, want", FEES_BODIES, ids=[c[0] for c in FEES_BODIES])
def test_create_payment_fees_body(name: str, fees: Any, want: Any) -> None:
    client, server, _ = make_client(static(201, fx("CreatedCheckoutSession")))
    client.checkout_sessions.create_payment(
        product_name="T-shirt", description="Blue, size M", price_usd="3.99", fees=fees
    )
    body = server.requests[0].json()
    assert body["productName"] == "T-shirt" and body["priceUsd"] == "3.99"
    if want is ABSENT:
        assert "fees" not in body
    else:
        assert body["fees"] == want
        # Amounts are always JSON strings.
        for item in body["fees"].get("items", []):
            assert isinstance(item["amountUsd"], str)


def test_create_payment_fees_wire_strings() -> None:
    client, server, _ = make_client(static(201, fx("CreatedCheckoutSession")))
    client.checkout_sessions.create_payment(
        product_uuid=UUID_A,
        fees=CheckoutFees(
            items=[FeeItem("A", "0.10"), FeeItem("B", Decimal("19.9")), FeeItem("C", "4.99")]
        ),
    )
    raw = server.requests[0].body.decode()
    assert '"amountUsd":"0.10"' in raw and '"amountUsd":"19.9"' in raw
    assert '"amountUsd":"4.99"' in raw


def test_create_payment_fee_number_refused() -> None:
    client, server, _ = make_client(static(201, fx("CreatedCheckoutSession")))
    with pytest.raises(ValidationError) as info:
        client.checkout_sessions.create_payment(
            product_uuid=UUID_A, fees=CheckoutFees(items=[FeeItem("A", 0.1)])
        )
    assert [f.field for f in info.value.field_errors] == ["fees.items[0].amountUsd"]
    assert server.requests == []


def test_create_subscription_fees_body() -> None:
    # The same fees as a payment's, sent only when given.
    client, server, _ = make_client(static(201, fx("CreatedCheckoutSession")))
    client.checkout_sessions.create_subscription(
        product_name="Pro",
        price_usd=Decimal("9.99"),
        frequency=Duration(value=1, unit=DurationUnit.MONTHS),
        fees=CheckoutFees(processing_fee=True, items=[FeeItem("VAT (20%)", "2", "French VAT")]),
    )
    client.checkout_sessions.create_subscription(
        product_uuid=UUID_A, fees=CheckoutFees(processing_fee=False)
    )
    client.checkout_sessions.create_subscription(product_uuid=UUID_A)
    first, off, none = (r.json() for r in server.requests)
    assert first == {
        "productName": "Pro",
        "priceUsd": "9.99",
        "frequency": {"value": 1, "unit": "months"},
        "fees": {
            "processingFee": True,
            "items": [{"label": "VAT (20%)", "description": "French VAT", "amountUsd": "2"}],
        },
    }
    assert off == {"productUuid": UUID_A, "fees": {"processingFee": False}}
    assert none == {"productUuid": UUID_A}
    assert {r.path for r in server.requests} == {"/checkout-sessions/subscription"}
