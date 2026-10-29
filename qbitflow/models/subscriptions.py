"""Subscriptions, their allowance and retries, products' subscription terms, test bills."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from pydantic import Field

from ..errors import field_error
from ._base import ZERO_TIME, Bool, Model, Str, Time, UInt
from ._fields import (
    ActionRequiredT,
    BillingOutcomeT,
    BillingStageT,
    CancellationReasonT,
    SubscriptionStatusT,
)
from .common import Currency, CustomerSummary, Duration, FeeLine, Metadata, TokenAmount

__all__ = [
    "Subscription",
    "Allowance",
    "DunningStatus",
    "SubscriptionCancellation",
    "TestBill",
    "SubscriptionTerms",
]


class Allowance(TokenAmount):
    """What a subscriber's wallet still lets QBitFlow bill for their subscription (the allowance
    left on-chain), in the subscription's token, how many bills that covers at today's price, and
    the most one bill may charge, as they signed it. ``amount``, ``amount_min_units`` and
    ``amount_usd`` (its value at today's price; ``None`` without one) come from
    :class:`TokenAmount`."""

    #: How many whole bills the allowance still covers at today's price (rounded down, before each
    #: bill's network fee). 0 is a value: the customer must top it up (``actionRequired``
    #: ``topUpAllowance``) before the next bill. ``None`` without a price.
    remaining_periods: Optional[UInt] = Field(default=None, alias="remainingPeriods")
    #: The most one bill may charge, as the subscriber signed it, in the token's units: a bill
    #: above it waits for a new maximum (``actionRequired`` ``raiseMaximum``). ``None`` when none
    #: is recorded.
    max_per_period: Optional[Str] = Field(default=None, alias="maxPerPeriod")
    #: The same as an on-chain integer.
    max_per_period_min_units: Optional[Str] = Field(default=None, alias="maxPerPeriodMinUnits")


class DunningStatus(Model):
    """A past-due subscription's retries."""

    #: The bill's failed attempts so far.
    failed_attempts: UInt = Field(default=0, alias="failedAttempts")
    #: The attempts left: after the last one fails, it is cancelled.
    remaining_attempts: UInt = Field(default=0, alias="remainingAttempts")
    #: The bill's first failed attempt.
    failing_since: Optional[Time] = Field(default=None, alias="failingSince")
    #: When the bill is tried again at the latest.
    next_attempt_at: Optional[Time] = Field(default=None, alias="nextAttemptAt")
    #: When it started waiting for the customer to raise their maximum.
    awaiting_maximum_since: Optional[Time] = Field(default=None, alias="awaitingMaximumSince")


class Subscription(Model):
    """A subscription (``sub@…``). **Grant access while** ``now < access_until``, whatever the
    status (:meth:`has_access`): the status says why, ``action_required`` what its customer must
    do."""

    #: The subscription's id (``sub@…``), its checkout session's for life.
    uuid: Str = ""
    #: Your reference for the subscription (an order or customer id), set when creating its
    #: checkout.
    reference: Optional[Str] = None
    #: When it was created.
    created_at: Time = Field(default=ZERO_TIME, alias="createdAt")
    #: Its last change (a bill, a status, its metadata).
    updated_at: Time = Field(default=ZERO_TIME, alias="updatedAt")
    #: The subscriber's wallet, the one it bills (``from`` on the wire); ``None`` when unknown (a
    #: trial not confirmed yet may have none).
    from_: Optional[Str] = Field(default=None, alias="from")
    #: The wallet its bills pay: the merchant's (or, while the organization holds a member's
    #: funds, the organization's).
    to: Str = ""
    #: Its product (``products.get``); ``None`` without one.
    product_uuid: Optional[Str] = Field(default=None, alias="productUuid")
    #: The transaction that created it on-chain; ``None`` until then (a trial, until its customer
    #: confirms it).
    subscription_hash: Optional[Str] = Field(default=None, alias="subscriptionHash")
    #: The currency (token) billed.
    currency: Currency = Field(default_factory=Currency)
    #: The billing interval.
    frequency: Duration = Field(default_factory=Duration)
    #: trial, trialExpired, active, pastDue, paused, stopped or cancelled. Every change sends
    #: ``subscription.statusChanged``.
    status: SubscriptionStatusT = ""
    #: What its customer must do (topUpAllowance, raiseMaximum, confirmTrial); ``None`` for
    #: nothing. Every change sends ``subscription.actionRequiredChanged``.
    action_required: Optional[ActionRequiredT] = Field(default=None, alias="actionRequired")
    #: The paid-through date, to display ("paid through"). A trial: its end; active, paused,
    #: stopped: the end of the period paid for; pastDue: the start of the unpaid period (past);
    #: cancelled: when it was cancelled, or the end of its last paid period if that came first.
    #: For access, read ``access_until``: an active subscription is renewed a few minutes after
    #: this date. ``None`` when absent.
    current_period_end: Optional[Time] = Field(default=None, alias="currentPeriodEnd")
    #: When access ends: grant it while now < ``access_until``, whatever the status
    #: (:meth:`has_access`). An active subscription: ``current_period_end`` plus 1 hour, since its
    #: renewal is billed within minutes of its due date (a subscriber whose bill is on its way
    #: keeps access; a failed bill makes it pastDue). Every other status: ``current_period_end``.
    #: ``None`` on a subscription stored before the API sent it (:meth:`has_access` then reads
    #: ``current_period_end``).
    access_until: Optional[Time] = Field(default=None, alias="accessUntil")
    #: The price per period the customer subscribed at, in USD (a decimal string, ``"9.99"``),
    #: locked at signup (a free trial's too); never ``"0"``. Every bill charges it plus ``fees``,
    #: converted to the token at the bill's price.
    price_usd: Str = Field(default="", alias="priceUsd")
    #: What its checkout added to the price, line by line, as the customer saw them (a tax,
    #: shipping, the processing fee when the customer pays it), locked at signup with the price:
    #: every bill charges ``price_usd`` plus these lines. Empty without any.
    fees: List[FeeLine] = Field(default_factory=list)
    #: What the subscriber's wallet still lets QBitFlow bill, and the most one bill may charge, at
    #: today's price; ``None`` during a free trial (nothing signed yet).
    allowance: Optional[Allowance] = None
    #: When it was last billed; ``None`` before its first bill (a trial).
    last_billed_at: Optional[Time] = Field(default=None, alias="lastBilledAt")
    #: When its next bill is due (a trial: when it ends; stopped: when it is cancelled); ``None``
    #: once cancelled.
    next_billing_at: Optional[Time] = Field(default=None, alias="nextBillingAt")
    #: When it was cancelled; ``None`` until then.
    cancelled_at: Optional[Time] = Field(default=None, alias="cancelledAt")
    #: Why it stopped or was cancelled; ``None`` while it runs.
    cancellation_reason: Optional[CancellationReasonT] = Field(
        default=None, alias="cancellationReason"
    )
    #: The earliest its customer may cancel it (the checkout's ``min_periods``); ``None`` when
    #: they may cancel it any time.
    cancellable_at: Optional[Time] = Field(default=None, alias="cancellableAt")
    #: Your own data: its checkout session's, copied when the subscription was created, then
    #: changed with ``subscriptions.update`` (merged). ``{}`` without any.
    metadata: Metadata = Field(default_factory=dict)
    #: The subscription's page for its customer: where they top up its allowance, raise its
    #: maximum, pause, resume or cancel it, and confirm a trial. Share it with them.
    management_page_link: Optional[Str] = Field(default=None, alias="managementPageLink")
    #: True in test mode.
    test: Bool = False
    #: The member whose space it is in; ``None`` for the organization's own.
    user_uuid: Optional[Str] = Field(default=None, alias="userUuid")
    #: The customer, when QBitFlow has one.
    customer_uuid: Optional[Str] = Field(default=None, alias="customerUuid")
    #: Your reference of the customer, as the checkout was given it.
    customer_reference: Optional[Str] = Field(default=None, alias="customerReference")
    #: Names the customer, even once deleted (API reads only).
    customer: Optional[CustomerSummary] = None
    #: Where its failing bill's retries stand (API reads only: webhooks tell each failure with
    #: ``subscription.billingFailed``); ``None`` while no bill is failing.
    dunning: Optional[DunningStatus] = None

    def has_access(self, at: Optional[datetime] = None) -> bool:
        """Whether the subscriber has access at ``at`` (default: now): ``at`` is before
        ``access_until``, whatever the status (a cancelled subscription keeps access until the end
        of the period paid for; an active one an hour past ``current_period_end``, while its
        renewal is billed). Without ``access_until`` (a subscription stored before the API sent
        it), it reads ``current_period_end``. False when neither is set.

        Args:
            at: The moment to check; a naive datetime is taken as UTC.

        Raises:
            ValidationError: ``at`` is not a datetime.
        """
        if at is None:
            at = datetime.now(timezone.utc)
        elif not isinstance(at, datetime):
            raise field_error("at", "must be a datetime")
        elif at.tzinfo is None:
            at = at.replace(tzinfo=timezone.utc)
        end = self.access_until if self.access_until is not None else self.current_period_end
        return end is not None and at < end


class SubscriptionCancellation(Model):
    """``subscriptions.cancel``'s answer.

    Attributes:
        subscription: The subscription as the API answered it.
        pending: True when the API answered 202: the cancellation is still confirming on-chain
            and ``subscription.status`` is not updated yet (``subscription.statusChanged`` tells
            the end; the cancellation goes on whatever happens).
    """

    subscription: Subscription = Field(default_factory=Subscription)
    pending: Bool = False


class TestBill(Model):
    """Where a test bill stands once its attempt settled (``subscriptions.test_bill``): done (its
    ``outcome``), waiting for its next attempt after a failure (``failure_code``,
    ``next_attempt_at``), or still running after 2 minutes. Its events are a live bill's
    (``subscription.billed``, ``subscription.billingFailed``, ``subscription.statusChanged``)."""

    # Not a test case: keeps pytest from collecting the class where a test module imports it.
    __test__ = False

    #: The bill (``sub-hist@…``): the id its ``subscription.billed`` and
    #: ``subscriptions.get_bill`` carry once it is paid.
    bill_uuid: Str = Field(default="", alias="billUuid")
    #: running (being charged), waiting (for its next attempt, its due date or a trial's grace
    #: period), pending (over the customer's maximum: waiting for a new one) or done.
    stage: BillingStageT = ""
    #: How it ended, once done: paid, notDue, skipped, cancelled or paused; ``None`` before.
    outcome: Optional[BillingOutcomeT] = None
    #: Its failed attempts so far.
    attempts: UInt = 0
    #: When it is tried again at the latest, while waiting or pending; ``None`` otherwise.
    next_attempt_at: Optional[Time] = Field(default=None, alias="nextAttemptAt")
    #: The charge's transaction, once paid.
    tx_hash: Optional[Str] = Field(default=None, alias="txHash")
    #: Its last failure's code (e.g. ``insufficient_allowance``).
    failure_code: Optional[Str] = Field(default=None, alias="failureCode")


class SubscriptionTerms(Model):
    """A subscription product's terms: billed every ``frequency``, after an optional free trial,
    for at least an optional number of periods."""

    #: How often it bills (e.g. 1 month: 30 days).
    frequency: Duration = Field(default_factory=Duration)
    #: A free trial before the first bill; ``None`` without one.
    trial_period: Optional[Duration] = Field(default=None, alias="trialPeriod")
    #: The periods the customer commits to before they can cancel; ``None`` without a minimum.
    min_periods: Optional[UInt] = Field(default=None, alias="minPeriods")
