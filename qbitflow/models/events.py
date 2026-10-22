"""
Webhook events: the envelope, one class per event type, and their data.

:data:`Event` is a discriminated union on ``type``: parsing a body gives the event class of its
type (``PaymentCompletedEvent`` with ``data: PaymentCompleted``, …), or :class:`UnknownEvent`
(raw ``data``) for a type this SDK does not know yet. Narrow it with ``isinstance`` (or compare
``event.type``)::

    if isinstance(event, PaymentCompletedEvent):
        print(event.data.reference, event.data.amount_usd)

Webhook data never carries what only API reads return (``customer``, ``refund``,
``refundable``, ``not_refundable_reason``, ``dunning``, ``approval``, a refund's
``customer_uuid`` and ``product_name``): those fields are ``None`` on events.
"""

from __future__ import annotations

from typing import Annotated, Any, List, Literal, Optional, Union

from pydantic import Discriminator, Field, Tag, model_validator

from ._base import ZERO_TIME, Bool, Model, Str, Time, UInt
from ._fields import (
    ActionRequiredT,
    BillingFailureReasonT,
    SubscriptionStatusT,
    TransferTypeT,
    WebhookPayloadVersionT,
)
from .checkout import PaymentSessionData, SubscriptionSessionData
from .common import TransferSettlement
from .enums import EventType, TransactionType
from .payments import Bill, Payment, Transfer
from .resources import EndpointDelivery, LedgerEntry, Member, Refund
from .subscriptions import Subscription

__all__ = [
    # Data
    "PaymentCompleted",
    "SubscriptionBilled",
    "SubscriptionStatusChanged",
    "SubscriptionActionRequiredChanged",
    "SubscriptionBillingFailed",
    "SubscriptionUpcomingBill",
    "MemberJoined",
    "HeldFundsReleased",
    "CheckoutExpired",
    "WebhookTest",
    # Events
    "BaseEvent",
    "PaymentCompletedEvent",
    "SubscriptionCreatedEvent",
    "SubscriptionBilledEvent",
    "SubscriptionStatusChangedEvent",
    "SubscriptionActionRequiredChangedEvent",
    "SubscriptionBillingFailedEvent",
    "SubscriptionUpcomingBillEvent",
    "RefundRequestedEvent",
    "RefundApprovedEvent",
    "RefundRejectedEvent",
    "MemberJoinedEvent",
    "MemberRemovedEvent",
    "HeldFundsReleasedEvent",
    "CheckoutExpiredEvent",
    "WebhookTestEvent",
    "UnknownEvent",
    "Event",
    "EventDetail",
]


# ── Event data ───────────────────────────────────────────────────────────────


class PaymentCompleted(Payment):
    """``payment.completed``'s data: the payment, confirmed, as ``payments.get`` returns it to
    its owner (its refund state excepted: API reads only), and its customer page. Fulfil the
    order: ``uuid`` is the checkout session's ``pay@…``, ``reference`` and ``metadata`` yours."""

    #: The payment's page for its customer.
    management_page_link: Optional[Str] = Field(default=None, alias="managementPageLink")


class SubscriptionBilled(Model):
    """``subscription.billed``'s data: the bill paid, and its subscription as the bill leaves it.
    Access is paid until ``bill.period_end``, unless ``subscription.status`` is ``cancelled`` (a
    charge that landed just after a cancellation: record it, grant nothing)."""

    #: The bill paid (as ``subscriptions.get_bill`` returns it): its currency, settlement, and
    #: the period it pays, ``period_start`` → ``period_end``.
    bill: Bill = Field(default_factory=Bill)
    #: The subscription once the bill is paid: active (stopped, paused or cancelled if that
    #: happened while the charge was on its way), its next bill, its allowance, its reference
    #: and its metadata.
    subscription: Subscription = Field(default_factory=Subscription)


class SubscriptionStatusChanged(Subscription):
    """``subscription.statusChanged``'s data: the subscription with its new ``status``, and the
    one before. Every status change sends it, once."""

    #: The status before the change.
    previous_status: SubscriptionStatusT = Field(default="", alias="previousStatus")


class SubscriptionActionRequiredChanged(Subscription):
    """``subscription.actionRequiredChanged``'s data: the subscription with its new
    ``action_required`` (``None`` = nothing to do anymore), and the one before. Its
    ``management_page_link`` is where the customer acts."""

    #: What its customer had to do before (``None``: nothing).
    previous_action_required: Optional[ActionRequiredT] = Field(
        default=None, alias="previousActionRequired"
    )


class SubscriptionBillingFailed(Subscription):
    """``subscription.billingFailed``'s data: the subscription as a failed bill attempt leaves
    it, and the failure. Its ``management_page_link`` is where the customer fixes it. Sent once
    per failed attempt (pastDue), and once when a bill above the customer's maximum starts
    waiting for a new one (``maxAmountExceeded``: no attempt spent)."""

    #: What the customer does: insufficientBalance (add funds to the wallet), allowanceExhausted
    #: (top up the allowance), approvalRevoked (approve the token again), maxAmountExceeded (sign
    #: a new maximum) or other (the network refused the charge).
    reason: BillingFailureReasonT = ""
    #: The charge's error code (e.g. ``insufficient_funds``, ``insufficient_allowance``).
    failure_code: Optional[Str] = Field(default=None, alias="failureCode")
    #: The bill that failed: the ``sub-hist@…`` its ``subscription.billed`` has once it is paid.
    bill_uuid: Str = Field(default="", alias="billUuid")
    #: The bill, in USD, a decimal string: its ``price_usd`` plus its ``fees`` lines.
    amount_usd: Str = Field(default="", alias="amountUsd")
    #: This bill's failed attempts so far, this one included (``maxAmountExceeded`` spends none).
    attempt: UInt = 0
    #: The attempts left (retried 1, 3, 5 and 7 days after the first failed attempt). 0: this was
    #: the last; its cancellation follows (``subscription.statusChanged``).
    remaining_attempts: UInt = Field(default=0, alias="remainingAttempts")
    #: When the bill is tried again at the latest (``maxAmountExceeded``: when it stops waiting
    #: for a new maximum); ``None`` after the last attempt.
    next_attempt_at: Optional[Time] = Field(default=None, alias="nextAttemptAt")


class SubscriptionUpcomingBill(Subscription):
    """``subscription.upcomingBill``'s data: a bill (or a trial's end) is near, sent once per
    bill some days before (3 by default). Remind the customer when ``balance_sufficient`` or
    ``allowance_sufficient`` is False, or when ``trial_ending``."""

    #: When it is billed (for a trial: when the trial ends).
    billing_at: Time = Field(default=ZERO_TIME, alias="billingAt")
    #: What the bill charges, in USD, a decimal string: its ``price_usd`` plus its ``fees``
    #: lines.
    amount_usd: Str = Field(default="", alias="amountUsd")
    #: True when the trial ends then: the customer confirms the subscription (its
    #: ``management_page_link``) to be billed.
    trial_ending: Bool = Field(default=False, alias="trialEnding")
    #: Whether the wallet holds the bill at today's price; ``None`` for a trial, or when it
    #: couldn't be checked.
    balance_sufficient: Optional[Bool] = Field(default=None, alias="balanceSufficient")
    #: Whether the remaining allowance covers the bill; ``None`` for a trial, or without a price.
    allowance_sufficient: Optional[Bool] = Field(default=None, alias="allowanceSufficient")


class MemberJoined(Member):
    """``member.joined``'s data: the member, in the mode they joined, and the invitation they
    accepted. Store ``user_uuid`` for ``on_behalf_of``."""

    #: The invitation they accepted (``invitations.create``'s ``uuid``): match the event to it.
    invitation_uuid: Str = Field(default="", alias="invitationUuid")


class HeldFundsReleased(Transfer):
    """``heldFunds.released``'s data: the transfer paying a member the funds the organization
    held for them (in the member's space: the envelope's ``user_uuid``), and the lines it
    settled. ``uuid`` is the transfer's id (``transfer@…``), ``from_`` the organization's wallet,
    ``to`` the member's; ``amount`` is what the member received, in the currency's units, exact:
    the sum of the lines' ``owed`` (``amount_usd`` at the release's price)."""

    #: True once the recipient received it.
    received: Bool = False
    #: ``heldFundsRelease``.
    type: TransferTypeT = ""
    #: The transfer's transaction: its block and what it cost its sender.
    settlement: TransferSettlement = Field(default_factory=TransferSettlement)
    #: The lines it settled, oldest first: the payments it paid (positive) and the
    #: refunds of them it took off (negative, type refund), each with what it counted for
    #: (``owed``, ``owed_min_units``, ``owed_usd``).
    ledgers: List[LedgerEntry] = Field(default_factory=list)


class WebhookTest(Model):
    """``webhook.test``'s data (the dashboard's test delivery)."""

    #: The endpoint tested.
    endpoint_uuid: Str = Field(default="", alias="endpointUuid")
    #: The test's message.
    message: Str = ""


def _session_tag(value: Any) -> str:
    tx_type = value.get("txType") if isinstance(value, dict) else getattr(value, "tx_type", None)
    return "subscription" if tx_type == TransactionType.CREATE_SUBSCRIPTION else "payment"


#: ``checkout.expired``'s data: a payment session, or a subscription session when its
#: ``tx_type`` is ``createSubscription`` (an unknown ``tx_type`` decodes as a payment session,
#: its raw value kept).
CheckoutExpired = Annotated[
    Union[
        Annotated[SubscriptionSessionData, Tag("subscription")],
        Annotated[PaymentSessionData, Tag("payment")],
    ],
    Discriminator(_session_tag),
]


# ── Events ───────────────────────────────────────────────────────────────────


class BaseEvent(Model):
    """The envelope every event shares.

    Deliveries are at least once: deduplicate on ``id``, and answer 2xx fast (also to the events
    you ignore). ``user_uuid`` names the member whose space the event happened in: pass it to
    ``client.on_behalf_of`` for follow-up reads.
    """

    #: The event's id (``evt_…``): the same on every retry, deduplicate on it.
    id: Str = ""
    #: The payload version: ``v2``, the only one.
    version: WebhookPayloadVersionT = ""
    #: When it happened (at most millisecond precision).
    created_at: Time = Field(default=ZERO_TIME, alias="createdAt")
    #: True when it happened in test mode.
    test: Bool = False
    #: The member whose space it happened in; ``None`` for the organization's own.
    user_uuid: Optional[Str] = Field(default=None, alias="userUuid")


class PaymentCompletedEvent(BaseEvent):
    """``payment.completed``: a payment is confirmed."""

    type: Literal["payment.completed"] = "payment.completed"
    data: PaymentCompleted = Field(default_factory=PaymentCompleted)


class SubscriptionCreatedEvent(BaseEvent):
    """``subscription.created``: a subscription started (status ``active``, or ``trial``). Its
    data is the subscription, as ``subscriptions.get`` returns it, its ``management_page_link``
    included: grant access until ``current_period_end``."""

    type: Literal["subscription.created"] = "subscription.created"
    data: Subscription = Field(default_factory=Subscription)


class SubscriptionBilledEvent(BaseEvent):
    """``subscription.billed``: a bill was paid (``data.bill``, ``data.subscription``)."""

    type: Literal["subscription.billed"] = "subscription.billed"
    data: SubscriptionBilled = Field(default_factory=SubscriptionBilled)


class SubscriptionStatusChangedEvent(BaseEvent):
    """``subscription.statusChanged``: a subscription's status changed."""

    type: Literal["subscription.statusChanged"] = "subscription.statusChanged"
    data: SubscriptionStatusChanged = Field(default_factory=SubscriptionStatusChanged)


class SubscriptionActionRequiredChangedEvent(BaseEvent):
    """``subscription.actionRequiredChanged``: what the customer must do changed."""

    type: Literal["subscription.actionRequiredChanged"] = "subscription.actionRequiredChanged"
    data: SubscriptionActionRequiredChanged = Field(
        default_factory=SubscriptionActionRequiredChanged
    )


class SubscriptionBillingFailedEvent(BaseEvent):
    """``subscription.billingFailed``: a bill attempt failed."""

    type: Literal["subscription.billingFailed"] = "subscription.billingFailed"
    data: SubscriptionBillingFailed = Field(default_factory=SubscriptionBillingFailed)


class SubscriptionUpcomingBillEvent(BaseEvent):
    """``subscription.upcomingBill``: a bill (or a trial's end) is near."""

    type: Literal["subscription.upcomingBill"] = "subscription.upcomingBill"
    data: SubscriptionUpcomingBill = Field(default_factory=SubscriptionUpcomingBill)


class RefundRequestedEvent(BaseEvent):
    """``refund.requested``: a new pending refund, always a customer's request (``initiated_by``
    ``customer``). A merchant's own refund is announced only by ``refund.approved``."""

    type: Literal["refund.requested"] = "refund.requested"
    data: Refund = Field(default_factory=Refund)


class RefundApprovedEvent(BaseEvent):
    """``refund.approved`` (was ``refund.completed``): the refund, approved, its transfer
    confirmed (``tx_hash``, ``settlement.transaction``); ``refund_percent`` and ``amount`` are the
    share actually paid back. Reverse the order, in full or in part. For a merchant's own refund
    (``initiated_by`` ``merchant``) it is the first and only event."""

    type: Literal["refund.approved"] = "refund.approved"
    data: Refund = Field(default_factory=Refund)


class RefundRejectedEvent(BaseEvent):
    """``refund.rejected`` (was ``refund.denied``): a customer's request rejected by whoever
    decides it. A decision, final."""

    type: Literal["refund.rejected"] = "refund.rejected"
    data: Refund = Field(default_factory=Refund)


class MemberJoinedEvent(BaseEvent):
    """``member.joined``: an invited seller joined."""

    type: Literal["member.joined"] = "member.joined"
    data: MemberJoined = Field(default_factory=MemberJoined)


class MemberRemovedEvent(BaseEvent):
    """``member.removed``: a member was removed."""

    type: Literal["member.removed"] = "member.removed"
    data: Member = Field(default_factory=Member)


class HeldFundsReleasedEvent(BaseEvent):
    """``heldFunds.released``: held funds were paid out to a member."""

    type: Literal["heldFunds.released"] = "heldFunds.released"
    data: HeldFundsReleased = Field(default_factory=HeldFundsReleased)


class CheckoutExpiredEvent(BaseEvent):
    """``checkout.expired``: a checkout session expired unpaid."""

    type: Literal["checkout.expired"] = "checkout.expired"
    data: CheckoutExpired = Field(default_factory=PaymentSessionData)


class WebhookTestEvent(BaseEvent):
    """``webhook.test``: the dashboard's test delivery."""

    type: Literal["webhook.test"] = "webhook.test"
    data: WebhookTest = Field(default_factory=WebhookTest)


class UnknownEvent(BaseEvent):
    """An event of a type this SDK does not know yet: ``data`` is the raw JSON value."""

    type: Str = ""
    data: Any = Field(default_factory=dict)


_EVENT_CLASSES = {
    cls.model_fields["type"].default: cls
    for cls in (
        PaymentCompletedEvent,
        SubscriptionCreatedEvent,
        SubscriptionBilledEvent,
        SubscriptionStatusChangedEvent,
        SubscriptionActionRequiredChangedEvent,
        SubscriptionBillingFailedEvent,
        SubscriptionUpcomingBillEvent,
        RefundRequestedEvent,
        RefundApprovedEvent,
        RefundRejectedEvent,
        MemberJoinedEvent,
        MemberRemovedEvent,
        HeldFundsReleasedEvent,
        CheckoutExpiredEvent,
        WebhookTestEvent,
    )
}
assert set(_EVENT_CLASSES) == {t.value for t in EventType}


def _event_tag(value: Any) -> str:
    event_type = value.get("type") if isinstance(value, dict) else getattr(value, "type", None)
    if isinstance(event_type, str) and event_type in _EVENT_CLASSES:
        return event_type
    return "unknown"


#: A webhook event, typed by its ``type`` (:class:`UnknownEvent` for a type this SDK does not
#: know). Every member derives from :class:`BaseEvent`.
Event = Annotated[
    Union[
        Annotated[PaymentCompletedEvent, Tag("payment.completed")],
        Annotated[SubscriptionCreatedEvent, Tag("subscription.created")],
        Annotated[SubscriptionBilledEvent, Tag("subscription.billed")],
        Annotated[SubscriptionStatusChangedEvent, Tag("subscription.statusChanged")],
        Annotated[
            SubscriptionActionRequiredChangedEvent, Tag("subscription.actionRequiredChanged")
        ],
        Annotated[SubscriptionBillingFailedEvent, Tag("subscription.billingFailed")],
        Annotated[SubscriptionUpcomingBillEvent, Tag("subscription.upcomingBill")],
        Annotated[RefundRequestedEvent, Tag("refund.requested")],
        Annotated[RefundApprovedEvent, Tag("refund.approved")],
        Annotated[RefundRejectedEvent, Tag("refund.rejected")],
        Annotated[MemberJoinedEvent, Tag("member.joined")],
        Annotated[MemberRemovedEvent, Tag("member.removed")],
        Annotated[HeldFundsReleasedEvent, Tag("heldFunds.released")],
        Annotated[CheckoutExpiredEvent, Tag("checkout.expired")],
        Annotated[WebhookTestEvent, Tag("webhook.test")],
        Annotated[UnknownEvent, Tag("unknown")],
    ],
    Discriminator(_event_tag),
]


class EventDetail(Model):
    """An event of the log with its deliveries (``webhooks.events.get``).

    Attributes:
        event: The event, typed by its type (the envelope's fields on the wire).
        deliveries: Its deliveries to the space's endpoints.
    """

    event: Event = Field(default_factory=UnknownEvent)
    deliveries: List[EndpointDelivery] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _split_envelope(cls, data: Any) -> Any:
        """The wire is the event's envelope plus ``deliveries``: nest the envelope."""
        if isinstance(data, dict) and "event" not in data:
            envelope = {key: value for key, value in data.items() if key != "deliveries"}
            return {"event": envelope, "deliveries": data.get("deliveries")}
        return data
