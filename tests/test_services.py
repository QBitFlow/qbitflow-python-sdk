"""Every service method: the request it sends, the decoding of its answer, its retry policy, and
its client-side checks (Go services_test.go, services_check_test.go)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import parse_qsl

import httpx
import pytest

from qbitflow import (
    AuthenticationError,
    BadRequestError,
    BillingOutcome,
    BillingStage,
    CheckoutSessionStatusValue,
    CombinedPaymentSource,
    ConflictError,
    Duration,
    DurationUnit,
    EventType,
    FailureCategory,
    FailureKind,
    InvitationStatus,
    NotFoundError,
    QBitFlow,
    RefundStatus,
    RequestOptions,
    ServerError,
    SubscriptionStatus,
    SubscriptionTermsParams,
    ValidationError,
    WebhookPayloadVersion,
    WebhookSignatureError,
    WebhookSignatureReason,
    WebhookTestEvent,
)

from .conftest import FIXTURES, MEMBER_UUID, TEST_API_KEY, make_client, reply, static
from .test_models import fx

UUID_A = "019eca82-5680-7b00-8000-0000000000c1"
UUID_B = "019eca82-5680-7b00-8000-0000000000c2"
PAY_ID = "pay@019eca82-5680-7b00-8000-0000000000d1"
SUB_ID = "sub@019eca82-5680-7b00-8000-0000000000d2"
BILL_ID = "sub-hist@019eca82-5680-7b00-8000-0000000000d3"
EVENT_ID = "evt_bd1a913d-188e-5ac5-a2d6-5fd25cd67301"
ODD_REF = "a/b c@d"
ODD_REF_ES = "a%2Fb%20c@d"

AFTER = datetime(2026, 9, 1, 12, tzinfo=timezone(timedelta(hours=2)))
BEFORE = datetime(2026, 10, 1, 0, 0, 0, 500_000, tzinfo=timezone.utc)
AFTER_Q = "2026-09-01T12%3A00%3A00%2B02%3A00"
BEFORE_Q = "2026-10-01T00%3A00%3A00.5Z"

UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
EVT = (FIXTURES / "events" / "webhook.test.json").read_text()


def page(item: str) -> str:
    return '{"items":[' + item + '],"nextCursor":"' + UUID_B + '"}'


def lst(item: str) -> str:
    return "[" + item + "]"


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
        lambda c, o: c.products.list(include_hidden=True, subscription=False, options=o),
        "GET",
        "/product",
        "includeHidden=true&subscription=false",
        reply=lst(fx("Product")),
        check=lambda v: len(v) == 1 and v[0].uuid == "p-1" and v[0].subscription is not None,
    ),
    Route(
        "products.list default",
        lambda c, o: c.products.list(options=o),
        "GET",
        "/product",
        reply="[]",
    ),
    Route(
        "products.create",
        lambda c, o: c.products.create(
            name="Pro",
            price=9.99,
            reference="pro",
            subscription=SubscriptionTermsParams(
                frequency=Duration(value=1, unit=DurationUnit.MONTHS),
                trial_period=Duration(),
                min_periods=3,
            ),
            options=o,
        ),
        "POST",
        "/product",
        body={
            "name": "Pro",
            "price": 9.99,
            "reference": "pro",
            "subscription": {
                "frequency": {"value": 1, "unit": "months"},
                "trialPeriod": {"value": 0},
                "minPeriods": 3,
            },
        },
        idempotent=True,
        status=201,
        reply=fx("Product"),
        check=lambda v: v.uuid == "p-1" and v.price == 9.99,
    ),
    Route(
        "products.get",
        lambda c, o: c.products.get(UUID_A, options=o),
        "GET",
        "/product/uuid/" + UUID_A,
        reply=fx("Product"),
    ),
    Route(
        "products.get_by_reference",
        lambda c, o: c.products.get_by_reference(ODD_REF, options=o),
        "GET",
        "/product/reference/" + ODD_REF_ES,
        reply=fx("Product"),
    ),
    Route(
        "products.update",
        lambda c, o: c.products.update(
            UUID_A, description="", price=12.0, is_active=False, options=o
        ),
        "PUT",
        "/product/" + UUID_A,
        body={"description": "", "price": 12, "isActive": False},
        reply=fx("Product"),
    ),
    Route(
        "products.delete",
        lambda c, o: c.products.delete(UUID_A, options=o),
        "DELETE",
        "/product/" + UUID_A,
        reply='{"message":"Product deleted successfully"}',
        check=lambda v: v is None,
    ),
    # Customers.
    Route(
        "customers.create",
        lambda c, o: c.customers.create(
            name="Ada",
            last_name="Lovelace",
            email="ada@example.com",
            phone_number="+33 6 12 34 56 78",
            reference="crm-1",
            options=o,
        ),
        "POST",
        "/customer",
        body={
            "name": "Ada",
            "lastName": "Lovelace",
            "email": "ada@example.com",
            "phoneNumber": "+33 6 12 34 56 78",
            "reference": "crm-1",
        },
        idempotent=True,
        status=201,
        reply=fx("Customer"),
        check=lambda v: v.uuid == "c-1" and v.verified and v.user_uuid == "m-1",
    ),
    Route(
        "customers.update",
        lambda c, o: c.customers.update(
            UUID_A, email="new@example.com", phone_number="", options=o
        ),
        "PUT",
        "/customer/" + UUID_A,
        body={"email": "new@example.com", "phoneNumber": ""},
        reply=fx("Customer"),
    ),
    Route(
        "customers.list",
        lambda c, o: c.customers.list(
            limit=5, cursor=UUID_A, email="ada+1@example.com", verified=True, options=o
        ),
        "GET",
        "/customer/all",
        "cursor=" + UUID_A + "&email=ada%2B1%40example.com&limit=5&verified=true",
        reply=page(fx("Customer")),
        check=lambda v: len(v.items) == 1 and v.has_more and v.next_cursor == UUID_B,
    ),
    Route(
        "customers.get",
        lambda c, o: c.customers.get(UUID_A, options=o),
        "GET",
        "/customer/uuid/" + UUID_A,
        reply=fx("Customer"),
    ),
    Route(
        "customers.get_by_email",
        lambda c, o: c.customers.get_by_email("ada+1@example.com", options=o),
        "GET",
        "/customer/email/ada+1@example.com",
        reply=fx("Customer"),
    ),
    Route(
        "customers.get_by_reference",
        lambda c, o: c.customers.get_by_reference(ODD_REF, options=o),
        "GET",
        "/customer/reference/" + ODD_REF_ES,
        reply=fx("Customer"),
    ),
    Route(
        "customers.delete",
        lambda c, o: c.customers.delete(UUID_A, options=o),
        "DELETE",
        "/customer/uuid/" + UUID_A,
        reply='{"message":"Customer deleted successfully"}',
    ),
    # Checkout sessions.
    Route(
        "checkout_sessions.create_payment",
        lambda c, o: c.checkout_sessions.create_payment(
            reference="order-1",
            product_name="T-shirt",
            description="Blue",
            price=4.5,
            success_url="https://shop.example/ok?id={{UUID}}",
            cancel_url="https://shop.example/ko",
            customer_reference="crm-1",
            expires_in_minutes=30,
            options=o,
        ),
        "POST",
        "/transaction/session-checkout/new/payment",
        body={
            "reference": "order-1",
            "productName": "T-shirt",
            "description": "Blue",
            "price": 4.5,
            "successUrl": "https://shop.example/ok?id={{UUID}}",
            "cancelUrl": "https://shop.example/ko",
            "customerReference": "crm-1",
            "expiresInMinutes": 30,
        },
        idempotent=True,
        status=201,
        reply=fx("CheckoutSession"),
        check=lambda v: v.uuid == "pay@1" and v.link and v.expires_at is not None,
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
        "/transaction/session-checkout/new/subscription",
        body={
            "productUuid": UUID_A,
            "customerUuid": UUID_B,
            "frequency": {"value": 1, "unit": "weeks"},
            "trialPeriod": {"value": 14, "unit": "days"},
            "minPeriods": 0,
        },
        idempotent=True,
        status=201,
        reply=fx("CheckoutSession"),
    ),
    Route(
        "checkout_sessions.get_status",
        lambda c, o: c.checkout_sessions.get_status(PAY_ID, options=o),
        "GET",
        "/transaction/session-checkout/" + PAY_ID + "/status",
        reply=fx("CheckoutSessionStatus"),
        check=lambda v: v.status == CheckoutSessionStatusValue.CREATED
        and v.last_attempt is not None,
    ),
    Route(
        "checkout_sessions.expire",
        lambda c, o: c.checkout_sessions.expire(SUB_ID, options=o),
        "POST",
        "/transaction/session-checkout/" + SUB_ID + "/expire",
        reply='{"uuid":"' + SUB_ID + '","status":"expired"}',
        check=lambda v: v.status == CheckoutSessionStatusValue.EXPIRED,
    ),
    # Payments and failures.
    Route(
        "payments.list",
        lambda c, o: c.payments.list(
            limit=50,
            cursor=UUID_A,
            customer_uuid=UUID_B,
            product_uuid=UUID_A,
            created_after=AFTER,
            created_before=BEFORE,
            user_uuid=MEMBER_UUID,
            refunded=False,
            options=o,
        ),
        "GET",
        "/transaction/payments",
        "createdAfter="
        + AFTER_Q
        + "&createdBefore="
        + BEFORE_Q
        + "&cursor="
        + UUID_A
        + "&customerUuid="
        + UUID_B
        + "&limit=50&productUuid="
        + UUID_A
        + "&refunded=false&userUuid="
        + MEMBER_UUID,
        reply=page(fx("Payment")),
        check=lambda v: v.items[0].uuid == "pay@1" and v.items[0].currency is not None,
    ),
    Route(
        "payments.list_combined",
        lambda c, o: c.payments.list_combined(
            include_members=True,
            refunded=True,
            source=CombinedPaymentSource.SUBSCRIPTION_HISTORY,
            subscription_uuid=SUB_ID,
            options=o,
        ),
        "GET",
        "/transaction/payments/combined",
        (
            "includeMembers=true&refunded=true&source=subscriptionHistory"
            "&subscriptionUuid=sub%40019eca82-5680-7b00-8000-0000000000d2"
        ),
        reply=page(fx("CombinedPayment")),
        check=lambda v: v.items[0].source == CombinedPaymentSource.SUBSCRIPTION_HISTORY,
    ),
    Route(
        "payments.get",
        lambda c, o: c.payments.get(PAY_ID, include_members=True, options=o),
        "GET",
        "/transaction/payment/" + PAY_ID,
        "includeMembers=true",
        reply=fx("Payment"),
        check=lambda v: v.reference == "order-1" and v.metadata.organization_fee is not None,
    ),
    Route(
        "payments.get bare uuid",
        lambda c, o: c.payments.get(PAY_ID[4:], options=o),
        "GET",
        "/transaction/payment/" + PAY_ID[4:],
        reply=fx("Payment"),
    ),
    Route(
        "payments.get_by_reference",
        lambda c, o: c.payments.get_by_reference(ODD_REF, options=o),
        "GET",
        "/transaction/payment/reference/" + ODD_REF_ES,
        reply=fx("Payment"),
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
        "/transaction/failures",
        (
            "category=allowanceExhausted&kind=bill&limit=3&subscriptionUu"
            "id=sub%40019eca82-5680-7b00-8000-0000000000d2"
        ),
        reply=page(fx("Failure")),
        check=lambda v: v.items[0].kind == FailureKind.BILL,
    ),
    # Subscriptions.
    Route(
        "subscriptions.list",
        lambda c, o: c.subscriptions.list(
            customer_uuid=UUID_B,
            created_after=AFTER,
            status=SubscriptionStatus.PAST_DUE,
            reference="crm:42",
            options=o,
        ),
        "GET",
        "/transaction/subscriptions",
        "createdAfter="
        + AFTER_Q
        + "&customerUuid="
        + UUID_B
        + "&reference=crm%3A42&status=pastDue",
        reply=page(fx("Subscription")),
        check=lambda v: v.items[0].status == SubscriptionStatus.STOPPED
        and v.items[0].dunning is not None,
    ),
    Route(
        "subscriptions.get",
        lambda c, o: c.subscriptions.get(SUB_ID, options=o),
        "GET",
        "/transaction/subscription/" + SUB_ID,
        reply=fx("Subscription"),
    ),
    Route(
        "subscriptions.get_by_reference",
        lambda c, o: c.subscriptions.get_by_reference(ODD_REF, options=o),
        "GET",
        "/transaction/subscription/reference/subscription/" + ODD_REF_ES,
        reply=fx("Subscription"),
    ),
    Route(
        "subscriptions.list_bills",
        lambda c, o: c.subscriptions.list_bills(SUB_ID, limit=100, cursor=UUID_A, options=o),
        "GET",
        "/transaction/subscription/" + SUB_ID + "/bills",
        "cursor=" + UUID_A + "&limit=100",
        reply=page(fx("Bill")),
        check=lambda v: v.items[0].uuid == "sub-hist@1" and v.items[0].subscription_uuid == "sub@1",
    ),
    Route(
        "subscriptions.get_bill",
        lambda c, o: c.subscriptions.get_bill(BILL_ID, include_members=True, options=o),
        "GET",
        "/transaction/subscription/bill/" + BILL_ID,
        "includeMembers=true",
        reply=fx("Bill"),
    ),
    Route(
        "subscriptions.get_public_history",
        lambda c, o: c.subscriptions.get_public_history(SUB_ID, options=o),
        "GET",
        "/transaction/subscription/history/" + SUB_ID,
        reply=(
            '[{"uuid":"sub-hist@1","createdAt":"2026-10-01T12:00:00+02:00'
            '","amount":9.99,"periodStart":"2026-10-01T12:00:00Z"}]'
        ),
        check=lambda v: len(v) == 1
        and v[0].amount == 9.99
        and v[0].customer_uuid is None
        and v[0].metadata.fee_percent == 0,
    ),
    Route(
        "subscriptions.cancel 202",
        lambda c, o: c.subscriptions.cancel(SUB_ID, immediate=False, options=o),
        "POST",
        "/transaction/subscription/processing/force-cancel/" + SUB_ID,
        "immediate=false",
        status=202,
        reply=fx("Subscription"),
        check=lambda v: v.pending and v.subscription.uuid == "sub@1",
    ),
    Route(
        "subscriptions.cancel 200",
        lambda c, o: c.subscriptions.cancel(SUB_ID, options=o),
        "POST",
        "/transaction/subscription/processing/force-cancel/" + SUB_ID,
        reply='{"uuid":"sub@1","status":"cancelled","cancellationReason":"merchant"}',
        check=lambda v: not v.pending and v.subscription.status == SubscriptionStatus.CANCELLED,
    ),
    Route(
        "subscriptions.execute_test_billing",
        lambda c, o: c.subscriptions.execute_test_billing(SUB_ID, options=o),
        "POST",
        "/transaction/subscription/processing/execute-billing/" + SUB_ID,
        reply=fx("BillingState"),
        check=lambda v: v.stage == BillingStage.DONE and v.outcome == BillingOutcome.PAID,
    ),
    # Refunds.
    Route(
        "refunds.list",
        lambda c, o: c.refunds.list(include_members=False, held=True, options=o),
        "GET",
        "/transaction/refunds/all",
        "held=true&includeMembers=false",
        reply=lst(fx("Refund")),
        check=lambda v: len(v) == 1
        and v[0].approval is not None
        and v[0].status == RefundStatus.PENDING,
    ),
    Route(
        "refunds.list_inactive",
        lambda c, o: c.refunds.list_inactive(
            limit=5, cursor=UUID_A, user_uuid=MEMBER_UUID, options=o
        ),
        "GET",
        "/transaction/refunds/all/inactive",
        "cursor=" + UUID_A + "&limit=5&userUuid=" + MEMBER_UUID,
        reply=page(fx("Refund")),
    ),
    Route(
        "refunds.initiate",
        lambda c, o: c.refunds.initiate(
            tx_uuid=BILL_ID,
            refund_percent=50.5,
            reason="Damaged",
            merchant_message="Sorry",
            options=o,
        ),
        "POST",
        "/transaction/refunds/initiate",
        body={
            "txUuid": BILL_ID,
            "refundPercent": 50.5,
            "reason": "Damaged",
            "merchantMessage": "Sorry",
        },
        idempotent=True,
        status=201,
        reply=fx("Refund"),
        check=lambda v: v.uuid == "refund@1" and v.tx_uuid == "pay@1",
    ),
    # Members.
    Route(
        "members.list",
        lambda c, o: c.members.list(limit=20, cursor=MEMBER_UUID, options=o),
        "GET",
        "/members",
        "cursor=" + MEMBER_UUID + "&limit=20",
        reply=page(fx("Member")),
        check=lambda v: v.items[0].user_uuid == "m-1"
        and len(v.items[0].accepted_currency_ids) == 3,
    ),
    Route(
        "members.get",
        lambda c, o: c.members.get(MEMBER_UUID, options=o),
        "GET",
        "/members/" + MEMBER_UUID,
        reply=fx("Member"),
    ),
    Route(
        "members.update",
        lambda c, o: c.members.update(MEMBER_UUID, organization_fee_percent=0, options=o),
        "PUT",
        "/members/" + MEMBER_UUID,
        body={"organizationFeePercent": 0},
        reply=fx("Member"),
    ),
    Route(
        "members.remove",
        lambda c, o: c.members.remove(MEMBER_UUID, options=o),
        "DELETE",
        "/members/" + MEMBER_UUID,
        reply='{"message":"Member removed"}',
    ),
    Route(
        "members.trust",
        lambda c, o: c.members.trust(MEMBER_UUID, options=o),
        "POST",
        "/members/" + MEMBER_UUID + "/trust",
        reply='{"userUuid":"' + MEMBER_UUID + '","trustedAt":"2026-10-07T10:00:00+02:00"}',
        check=lambda v: v.trusted_at is not None,
    ),
    Route(
        "members.list_held_funds",
        lambda c, o: c.members.list_held_funds(options=o),
        "GET",
        "/members/held-funds",
        reply=lst(fx("MemberHeldFundsSummary")),
        check=lambda v: len(v) == 1 and v[0].count == 2,
    ),
    Route(
        "members.get_held_funds",
        lambda c, o: c.members.get_held_funds(MEMBER_UUID, options=o),
        "GET",
        "/members/" + MEMBER_UUID + "/held-funds",
        reply=fx("HeldFunds"),
        check=lambda v: len(v.ledgers) == 1 and v.total_amount == -10.0042,
    ),
    Route(
        "members.get_own_held_funds",
        lambda c, o: c.members.get_own_held_funds(options=o),
        "GET",
        "/user/held-funds",
        reply='{"ledgers":[],"totalAmount":0}',
    ),
    # Invitations.
    Route(
        "invitations.create",
        lambda c, o: c.invitations.create(
            email="seller@example.com",
            trust_layer=True,
            organization_fee_percent=2.5,
            redirect_url="https://shop.example/welcome",
            options=o,
        ),
        "POST",
        "/invitations",
        body={
            "email": "seller@example.com",
            "role": "user",
            "trustLayer": True,
            "organizationFeePercent": 2.5,
            "redirectUrl": "https://shop.example/welcome",
        },
        idempotent=True,
        status=201,
        reply=fx("InvitationCreated"),
        check=lambda v: v.link and v.invitation.status == InvitationStatus.PENDING,
    ),
    Route(
        "invitations.create minimal",
        lambda c, o: c.invitations.create(email="seller@example.com", options=o),
        "POST",
        "/invitations",
        body={"email": "seller@example.com", "role": "user", "trustLayer": False},
        idempotent=True,
        status=201,
        reply=fx("InvitationCreated"),
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
        reply=fx("Invitation"),
        check=lambda v: v.uuid == "i-1",
    ),
    # Wallets.
    Route(
        "wallets.list",
        lambda c, o: c.wallets.list(with_balances=True, options=o),
        "GET",
        "/wallet/user",
        "withBalances=true",
        reply=lst(fx("Wallet")),
        check=lambda v: len(v) == 1 and v[0].token_wallets[0].balance is not None,
    ),
    Route(
        "wallets.list_for_member",
        lambda c, o: c.wallets.list_for_member(MEMBER_UUID, options=o),
        "GET",
        "/wallet/user/" + MEMBER_UUID,
        reply=lst(fx("Wallet")),
    ),
    Route(
        "wallets.list_supported_currencies",
        lambda c, o: c.wallets.list_supported_currencies(user_uuid=MEMBER_UUID, options=o),
        "GET",
        "/wallet/supported-currencies",
        "userUuid=" + MEMBER_UUID,
        reply=lst(fx("Currency")),
        check=lambda v: len(v) == 1 and v[0].main_currency is not None,
    ),
    # Accounting.
    Route(
        "accounting.export_json",
        lambda c, o: c.accounting.export_json("2026-09-01", "2026-09-30", options=o),
        "GET",
        "/accounting/export",
        "format=json&from=2026-09-01&to=2026-09-30",
        reply=lst(fx("AccountingEvent")),
        check=lambda v: len(v) == 1 and v[0].type == "refund",
    ),
    Route(
        "accounting.export_csv",
        lambda c, o: c.accounting.export_csv("2026-09-01", "2026-09-30", options=o),
        "GET",
        "/accounting/export",
        "format=csv&from=2026-09-01&to=2026-09-30",
        accept="text/csv, application/json",
        reply="paymentUuid,type\npay@1,payment\n",
        content_type="text/csv",
        check=lambda v: v == "paymentUuid,type\npay@1,payment\n",
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
        reply='{"message":"Signature valid"}',
        check=lambda v: v is None,
    ),
    Route(
        "webhooks.endpoints.list",
        lambda c, o: c.webhooks.endpoints.list(options=o),
        "GET",
        "/webhooks/endpoints",
        reply=lst(fx("WebhookEndpointCreated")),
        check=lambda v: len(v) == 1 and v[0].url == "https://x.io/hook",
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
            payload_version=WebhookPayloadVersion.V2,
            enabled=True,
            options=o,
        ),
        "PUT",
        "/webhooks/endpoints/" + UUID_A,
        body={"events": [], "description": "", "payloadVersion": "v2", "enabled": True},
        reply=fx("WebhookEndpointCreated"),
    ),
    Route(
        "webhooks.endpoints.delete",
        lambda c, o: c.webhooks.endpoints.delete(UUID_A, options=o),
        "DELETE",
        "/webhooks/endpoints/" + UUID_A,
        reply='{"message":"Endpoint deleted"}',
    ),
    Route(
        "webhooks.events.list",
        lambda c, o: c.webhooks.events.list(
            limit=2, cursor=EVENT_ID, type=EventType.WEBHOOK_TEST, include_members=True, options=o
        ),
        "GET",
        "/webhooks/events",
        "cursor=" + EVENT_ID + "&includeMembers=true&limit=2&type=webhook.test",
        reply='{"items":[' + EVT + '],"nextCursor":null}',
        check=lambda v: len(v.items) == 1
        and not v.has_more
        and isinstance(v.items[0], WebhookTestEvent)
        and v.items[0].data.endpoint_uuid,
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
        check=lambda v: v.event.id == EVENT_ID
        and v.event.type == EventType.WEBHOOK_TEST
        and len(v.deliveries) == 1
        and len(v.deliveries[0].attempts) == 1
        and v.deliveries[0].delivered,
    ),
    # Currencies.
    Route(
        "currencies.list_available",
        lambda c, o: c.currencies.list_available(test=True, options=o),
        "GET",
        "/utils/all-available-currencies",
        "test=true",
        reply=lst(fx("Currency")),
    ),
    Route(
        "currencies.list_main",
        lambda c, o: c.currencies.list_main(options=o),
        "GET",
        "/utils/all-main-currencies",
        reply=lst(fx("Currency")),
    ),
    Route(
        "currencies.get",
        lambda c, o: c.currencies.get(8, options=o),
        "GET",
        "/utils/currency/id/8",
        reply=fx("Currency"),
        check=lambda v: v.id == 8 and v.symbol == "USDC",
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


def test_seven_idempotent_creates() -> None:
    names = {r.name for r in ROUTES if r.idempotent and not r.name.endswith("minimal")}
    assert names == {
        "products.create",
        "customers.create",
        "checkout_sessions.create_payment",
        "checkout_sessions.create_subscription",
        "refunds.initiate",
        "invitations.create",
        "webhooks.endpoints.create",
    }


def test_errors_typed() -> None:
    client, _, _ = make_client(
        static(409, '{"error":"Unknown checkout","code":"tx_already_sent","requestId":"r-1"}')
    )
    with pytest.raises(ConflictError) as info:
        client.checkout_sessions.expire(PAY_ID)
    assert info.value.code == "tx_already_sent" and info.value.request_id == "r-1"

    client2, _, _ = make_client(static(400, '{"error":"window too long","code":"bad_request"}'))
    with pytest.raises(BadRequestError):
        client2.accounting.export_csv("2026-01-01", "2026-09-30")

    client3, _, _ = make_client(static(404, '{"error":"not found","code":"not_found"}'))
    with pytest.raises(NotFoundError):
        client3.subscriptions.cancel(SUB_ID)
    with pytest.raises(NotFoundError):
        client3.products.delete(UUID_A)
    with pytest.raises(NotFoundError):
        list(client3.customers.iterate())


def test_cancel_without_body() -> None:
    client, _, _ = make_client(lambda _r, _n: httpx.Response(202))
    with pytest.raises(ServerError):
        client.subscriptions.cancel(SUB_ID)


def _drop(_: Any) -> None:
    return None


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
    "customers.get_by_email": ("email", lambda c: c.customers.get_by_email("")),
    "customers.get_by_reference": ("reference", lambda c: c.customers.get_by_reference("")),
    "checkout_sessions.get_status": ("uuid", lambda c: c.checkout_sessions.get_status("")),
    "checkout_sessions.expire": ("uuid", lambda c: c.checkout_sessions.expire("cs_123")),
    "payments.get": ("uuid", lambda c: c.payments.get("pay@123")),
    "payments.get_by_reference": ("reference", lambda c: c.payments.get_by_reference("")),
    "subscriptions.get": ("uuid", lambda c: c.subscriptions.get("bad@" + UUID_A)),
    "subscriptions.get_by_reference": ("reference", lambda c: c.subscriptions.get_by_reference("")),
    "subscriptions.list_bills": ("uuid", lambda c: c.subscriptions.list_bills("")),
    "subscriptions.get_bill": ("billUuid", lambda c: c.subscriptions.get_bill("1")),
    "subscriptions.get_public_history": (
        "subscriptionUuid",
        lambda c: c.subscriptions.get_public_history(""),
    ),
    "subscriptions.cancel": ("uuid", lambda c: c.subscriptions.cancel("", immediate=True)),
    "subscriptions.execute_test_billing": (
        "uuid",
        lambda c: c.subscriptions.execute_test_billing("sub"),
    ),
    "members.get": ("userUuid", lambda c: c.members.get("")),
    "members.update": ("userUuid", lambda c: c.members.update("1", organization_fee_percent=0)),
    "members.remove": ("userUuid", lambda c: c.members.remove("")),
    "members.trust": ("userUuid", lambda c: c.members.trust("x")),
    "members.get_held_funds": ("userUuid", lambda c: c.members.get_held_funds("")),
    "invitations.revoke": ("uuid", lambda c: c.invitations.revoke("")),
    "wallets.list_for_member": ("userUuid", lambda c: c.wallets.list_for_member("1")),
    "webhooks.endpoints.get": ("uuid", lambda c: c.webhooks.endpoints.get("")),
    "webhooks.endpoints.update": ("uuid", lambda c: c.webhooks.endpoints.update("x")),
    "webhooks.endpoints.delete": ("uuid", lambda c: c.webhooks.endpoints.delete("")),
    "webhooks.events.get": ("id", lambda c: c.webhooks.events.get("")),
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
    "products.create": ("name", lambda c: c.products.create(name=None, price=None)),
    "customers.create": ("email", lambda c: c.customers.create(name="Ada", email=None)),
    "checkout_sessions.create_payment": (
        "productUuid",
        lambda c: c.checkout_sessions.create_payment(),
    ),
    "refunds.initiate": ("txUuid", lambda c: c.refunds.initiate(tx_uuid=None)),
    "members.update fee": (
        "organizationFeePercent",
        lambda c: c.members.update(MEMBER_UUID, organization_fee_percent=None),
    ),
    "invitations.create": ("email", lambda c: c.invitations.create(email=None)),
    "webhooks.endpoints.create": ("url", lambda c: c.webhooks.endpoints.create(url=None)),
    # Invalid params.
    "products.create price": ("price", lambda c: c.products.create(name="Pro", price=-1)),
    "products.update name": ("name", lambda c: c.products.update(UUID_A, name="<b>")),
    "customers.update phone": (
        "phoneNumber",
        lambda c: c.customers.update(UUID_A, phone_number="call me"),
    ),
    "customers.list email": ("email", lambda c: c.customers.list(email="x")),
    "checkout_sessions.create_payment mixed": (
        "productUuid",
        lambda c: c.checkout_sessions.create_payment(product_uuid=UUID_A, product_reference="pro"),
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
    "payments.list_combined source": ("source", lambda c: c.payments.list_combined(source="bills")),
    "failures.list kind": ("kind", lambda c: c.failures.list(kind="refund")),
    "subscriptions.list status": ("status", lambda c: c.subscriptions.list(status="lowOnFunds")),
    "refunds.list user_uuid": ("userUuid", lambda c: c.refunds.list(user_uuid="1")),
    "refunds.list_inactive exclusive": (
        "userUuid",
        lambda c: c.refunds.list_inactive(include_members=True, user_uuid=MEMBER_UUID),
    ),
    "refunds.initiate percent": (
        "refundPercent",
        lambda c: c.refunds.initiate(tx_uuid=PAY_ID, refund_percent=0.0),
    ),
    "members.update over 50": (
        "organizationFeePercent",
        lambda c: c.members.update(MEMBER_UUID, organization_fee_percent=51),
    ),
    "invitations.create empty": ("email", lambda c: c.invitations.create(email="")),
    "invitations.list status": ("status", lambda c: c.invitations.list(status="open")),
    "wallets.list_supported_currencies": (
        "userUuid",
        lambda c: c.wallets.list_supported_currencies(user_uuid="x"),
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
    "webhooks.events.list type": ("type", lambda c: c.webhooks.events.list(type="payment.failed")),
}


@pytest.mark.parametrize("name", sorted(VALIDATION_CASES))
def test_validation_before_request(name: str) -> None:
    field_name, call = VALIDATION_CASES[name]
    client, server, _ = make_client(static(200, "{}"))
    with pytest.raises(ValidationError) as info:
        call(client)
    assert info.value.status is None
    assert field_name in [f.field for f in info.value.field_errors]
    assert server.requests == []


def test_iterate_validation_is_lazy_and_sends_nothing() -> None:
    client, server, _ = make_client(static(200, "{}"))
    it = client.subscriptions.iterate_bills("nope")
    with pytest.raises(ValidationError):
        next(it)
    with pytest.raises(ValidationError):
        list(client.members.iterate(options=RequestOptions(on_behalf_of="x")))
    assert server.requests == []


@pytest.mark.parametrize(
    "status, body, check",
    [
        (200, '{"message":"ok"}', lambda e: e is None),
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
            '{"error":"bad","code":"bad_request"}',
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
        "customers.iterate",
        "/customer/all",
        "email=a%40b.co&limit=2&verified=false",
        uuid_item,
        lambda c: c.customers.iterate(limit=2, email="a@b.co", verified=False),
        lambda v: v.uuid,
    ),
    (
        "payments.iterate",
        "/transaction/payments",
        "createdAfter=" + AFTER_Q + "&limit=2",
        uuid_item,
        lambda c: c.payments.iterate(limit=2, created_after=AFTER),
        lambda v: v.uuid,
    ),
    (
        "payments.iterate_combined",
        "/transaction/payments/combined",
        "source=payment",
        uuid_item,
        lambda c: c.payments.iterate_combined(source=CombinedPaymentSource.PAYMENT),
        lambda v: v.uuid,
    ),
    (
        "failures.iterate",
        "/transaction/failures",
        "category=reverted",
        uuid_item,
        lambda c: c.failures.iterate(category=FailureCategory.REVERTED),
        lambda v: v.uuid,
    ),
    (
        "subscriptions.iterate",
        "/transaction/subscriptions",
        "includeMembers=true&status=active",
        uuid_item,
        lambda c: c.subscriptions.iterate(include_members=True, status=SubscriptionStatus.ACTIVE),
        lambda v: v.uuid,
    ),
    (
        "subscriptions.iterate_bills",
        "/transaction/subscription/" + SUB_ID + "/bills",
        "limit=100",
        uuid_item,
        lambda c: c.subscriptions.iterate_bills(SUB_ID, limit=100),
        lambda v: v.uuid,
    ),
    (
        "refunds.iterate_inactive",
        "/transaction/refunds/all/inactive",
        "held=false",
        uuid_item,
        lambda c: c.refunds.iterate_inactive(held=False),
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
            return reply(200, '{"items":[' + item(0) + "," + item(1) + '],"nextCursor":"id1"}')
        if cursor == "id1":
            return reply(200, '{"items":[' + item(2) + '],"nextCursor":null}')
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
        assert cursor == ["", "id1"][i]
    # An early break stops after the first page.
    for v in walk(client):
        break
    assert len(server.requests) == 3


def test_iterator_errors_and_resume() -> None:
    def handler(req: httpx.Request, _n: int) -> httpx.Response:
        if req.url.params.get("cursor", "") == "":
            return reply(200, '{"items":[{"uuid":"id0"}],"nextCursor":"id0"}')
        return reply(401, '{"error":"unauthorized","code":"unauthorized"}')

    client, _, _ = make_client(handler)
    got = []
    with pytest.raises(AuthenticationError):
        for p in client.payments.iterate():
            got.append(p.uuid)
    assert got == ["id0"]
