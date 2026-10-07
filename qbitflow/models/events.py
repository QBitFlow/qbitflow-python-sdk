"""
Webhook events: the envelope, one class per event type, and their data.

:data:`Event` is a discriminated union on ``type``: parsing a body gives the event class of its
type (``PaymentCompletedEvent`` with ``data: PaymentCompleted``, …), or :class:`UnknownEvent`
(raw ``data``) for a type this SDK does not know yet. Narrow it with ``isinstance`` (or compare
``event.type``)::

    if isinstance(event, PaymentCompletedEvent):
        print(event.data.reference, event.data.amount)

Webhook data never carries what only API reads return (``customer``, ``refund``,
``refundable``, ``not_refundable_reason``, ``dunning``, ``approval``, ``product_name``): those
fields are ``None`` on events.
"""

from __future__ import annotations

from typing import Annotated, Any, List, Literal, Optional, Union

from pydantic import Discriminator, Field, Tag, model_validator

from ._base import ZERO_TIME, Bool, Float, Model, Str, Time, UInt
from ._fields import (
    ActionRequiredT,
    BillingFailureReasonT,
    SubscriptionStatusT,
    TransferTypeT,
    WebhookPayloadVersionT,
)
from .checkout import PaymentSessionData, SubscriptionSessionData
from .common import TxMetadata
from .enums import EventType, TransactionType
from .payments import Bill, Payment, Transfer
from .resources import EndpointDelivery, LedgerEntry, Member, Refund
from .subscriptions import Subscription

__all__ = [
    # Data
    "PaymentCompleted",
    "SubscriptionCreated",
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
    "RefundCompletedEvent",
    "RefundDeniedEvent",
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
    """``payment.completed``'s data: the payment, confirmed."""

    #: The payment's page for its customer.
    management_page_link: Optional[Str] = Field(default=None, alias="managementPageLink")


class SubscriptionCreated(Subscription):
    """``subscription.created``'s data (status ``active``, or ``trial``)."""

    management_page_link: Optional[Str] = Field(default=None, alias="managementPageLink")


class SubscriptionBilled(Bill):
    """``subscription.billed``'s data: the paid bill."""

    #: The subscription's merchant reference, if it has one.
    subscription_reference: Optional[Str] = Field(default=None, alias="subscriptionReference")
    #: The subscription's status once the bill is paid.
    subscription_status: SubscriptionStatusT = Field(default="", alias="subscriptionStatus")


class SubscriptionStatusChanged(Subscription):
    """``subscription.statusChanged``'s data."""

    #: The status before the change.
    previous_status: SubscriptionStatusT = Field(default="", alias="previousStatus")
    management_page_link: Optional[Str] = Field(default=None, alias="managementPageLink")


class SubscriptionActionRequiredChanged(Subscription):
    """``subscription.actionRequiredChanged``'s data."""

    #: What its customer had to do before (``None``: nothing).
    previous_action_required: Optional[ActionRequiredT] = Field(
        default=None, alias="previousActionRequired"
    )
    management_page_link: Optional[Str] = Field(default=None, alias="managementPageLink")


class SubscriptionBillingFailed(Subscription):
    """``subscription.billingFailed``'s data: a bill attempt failed."""

    #: insufficientBalance, allowanceExhausted, approvalRevoked, maxAmountExceeded or other.
    reason: BillingFailureReasonT = ""
    #: The charge's error code (e.g. ``insufficient_funds``).
    failure_code: Optional[Str] = Field(default=None, alias="failureCode")
    #: The bill that failed (``sub-hist@…``).
    bill_uuid: Str = Field(default="", alias="billUuid")
    #: The bill, in USD: a decimal **string** here (a number on ``subscription.upcomingBill``).
    amount_usd: Str = Field(default="", alias="amountUsd")
    #: This bill's failed attempts so far, this one included.
    attempt: UInt = 0
    remaining_attempts: UInt = Field(default=0, alias="remainingAttempts")
    #: When the bill is tried again at the latest.
    next_attempt_at: Optional[Time] = Field(default=None, alias="nextAttemptAt")
    #: The subscription's management page, where its customer fixes it.
    management_page_link: Optional[Str] = Field(default=None, alias="managementPageLink")


class SubscriptionUpcomingBill(Subscription):
    """``subscription.upcomingBill``'s data: a bill (or a trial's end) is near."""

    #: When it is billed (for a trial: when the trial ends).
    billing_date: Time = Field(default=ZERO_TIME, alias="billingDate")
    #: The bill, in USD: a **number** here (a string on ``subscription.billingFailed``).
    amount_usd: Float = Field(default=0.0, alias="amountUsd")
    #: True when the trial ends then: the customer must confirm it to be billed.
    trial_ending: Bool = Field(default=False, alias="trialEnding")
    #: Whether the wallet holds the bill; ``None`` for a trial.
    balance_sufficient: Optional[Bool] = Field(default=None, alias="balanceSufficient")
    #: Whether the remaining allowance covers the bill; ``None`` for a trial.
    allowance_sufficient: Optional[Bool] = Field(default=None, alias="allowanceSufficient")


class MemberJoined(Member):
    """``member.joined``'s data: the member, and the invitation they accepted."""

    #: The invitation they accepted (``invitations.create``'s).
    invitation_uuid: Str = Field(default="", alias="invitationUuid")


class HeldFundsReleased(Transfer):
    """``heldFunds.released``'s data: the transfer paying a member the funds the organization
    held for them (``uuid`` is ``transfer@…``), and the lines it settled."""

    #: True once the recipient received it.
    received: Bool = False
    #: ``heldFundsRelease``.
    type: TransferTypeT = ""
    tx_metadata: TxMetadata = Field(default_factory=TxMetadata, alias="txMetadata")
    #: The held-funds lines it settled.
    ledgers: List[LedgerEntry] = Field(default_factory=list)


class WebhookTest(Model):
    """``webhook.test``'s data (the dashboard's test delivery)."""

    endpoint_uuid: Str = Field(default="", alias="endpointUuid")
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
    #: The payload version (``v2``).
    version: WebhookPayloadVersionT = ""
    #: When it happened.
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
    """``subscription.created``: a subscription started (paid, or in trial)."""

    type: Literal["subscription.created"] = "subscription.created"
    data: SubscriptionCreated = Field(default_factory=SubscriptionCreated)


class SubscriptionBilledEvent(BaseEvent):
    """``subscription.billed``: a bill was paid."""

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
    """``refund.requested``: a pending refund."""

    type: Literal["refund.requested"] = "refund.requested"
    data: Refund = Field(default_factory=Refund)


class RefundCompletedEvent(BaseEvent):
    """``refund.completed``: an approved refund was sent."""

    type: Literal["refund.completed"] = "refund.completed"
    data: Refund = Field(default_factory=Refund)


class RefundDeniedEvent(BaseEvent):
    """``refund.denied``: a refund was rejected."""

    type: Literal["refund.denied"] = "refund.denied"
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
        RefundCompletedEvent,
        RefundDeniedEvent,
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
        Annotated[RefundCompletedEvent, Tag("refund.completed")],
        Annotated[RefundDeniedEvent, Tag("refund.denied")],
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
