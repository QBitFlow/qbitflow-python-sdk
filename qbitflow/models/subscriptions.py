"""Subscriptions, products' subscription terms, test billing."""

from __future__ import annotations

from typing import Optional

from pydantic import Field

from ._base import ZERO_TIME, Bool, Model, Str, Time, UInt
from ._fields import (
    ActionRequiredT,
    BillingOutcomeT,
    BillingStageT,
    CancellationReasonT,
    SubscriptionStatusT,
)
from .common import Currency, CustomerSummary, Duration

__all__ = [
    "Subscription",
    "DunningStatus",
    "SubscriptionCancellation",
    "BillingState",
    "SubscriptionTerms",
]


class DunningStatus(Model):
    """A past-due subscription's retries."""

    #: The bill's failed attempts so far.
    failed_attempts: UInt = Field(default=0, alias="failedAttempts")
    #: The attempts left: after the last one fails, it is cancelled.
    remaining_attempts: UInt = Field(default=0, alias="remainingAttempts")
    failing_since: Optional[Time] = Field(default=None, alias="failingSince")
    #: When the bill is tried again at the latest.
    next_attempt_at: Optional[Time] = Field(default=None, alias="nextAttemptAt")
    #: When it started waiting for the customer to raise their maximum.
    awaiting_maximum_since: Optional[Time] = Field(default=None, alias="awaitingMaximumSince")


class Subscription(Model):
    """A subscription. **Grant access while** ``now < current_period_end``, whatever the status."""

    #: The subscription's id (``sub@…``), its checkout session's for life.
    uuid: Str = ""
    #: The merchant's reference, set when creating its checkout.
    reference: Optional[Str] = None
    created_at: Time = Field(default=ZERO_TIME, alias="createdAt")
    updated_at: Time = Field(default=ZERO_TIME, alias="updatedAt")
    #: The subscriber's wallet (``from`` on the wire).
    from_: Str = Field(default="", alias="from")
    #: The wallet that receives the bills.
    to: Str = ""
    product_uuid: Str = Field(default="", alias="productUuid")
    #: The transaction that created it on-chain (``""`` on a trial until confirmed).
    subscription_hash: Str = Field(default="", alias="subscriptionHash")
    currency_id: UInt = Field(default=0, alias="currencyId")
    currency: Optional[Currency] = None
    #: The billing interval.
    frequency: Duration = Field(default_factory=Duration)
    #: What remains of the allowance the subscriber granted, in min units (a decimal string).
    allowance: Str = ""
    #: trial, trialExpired, active, pastDue, paused, stopped or cancelled.
    status: SubscriptionStatusT = ""
    #: What its customer must do (topUpAllowance, raiseMaximum, confirmTrial); ``None``: nothing.
    action_required: Optional[ActionRequiredT] = Field(default=None, alias="actionRequired")
    #: The end of the period paid for (or of the trial): grant access while now is before it.
    current_period_end: Optional[Time] = Field(default=None, alias="currentPeriodEnd")
    #: The price per period the customer subscribed at, in USD (a decimal string; "0" for old
    #: v1 subscriptions).
    price_usd: Str = Field(default="", alias="priceUsd")
    #: The customer's maximum per period, in min units (a decimal string).
    max_amount_per_period: Optional[Str] = Field(default=None, alias="maxAmountPerPeriod")
    last_billing_date: Time = Field(default=ZERO_TIME, alias="lastBillingDate")
    #: When the next bill is due (a trial: when it ends; stopped: when it is cancelled).
    next_billing_date: Optional[Time] = Field(default=None, alias="nextBillingDate")
    cancelled_at: Optional[Time] = Field(default=None, alias="cancelledAt")
    cancellation_reason: Optional[CancellationReasonT] = Field(
        default=None, alias="cancellationReason"
    )
    #: The earliest date it can be cancelled (its minimum periods).
    minimum_cancellation_date: Optional[Time] = Field(default=None, alias="minimumCancellationDate")
    test: Bool = False
    user_uuid: Optional[Str] = Field(default=None, alias="userUuid")
    customer_uuid: Optional[Str] = Field(default=None, alias="customerUuid")
    customer_reference: Optional[Str] = Field(default=None, alias="customerReference")
    #: Names the customer (API reads only).
    customer: Optional[CustomerSummary] = None
    #: The failing bill's retries, while past due (API reads only).
    dunning: Optional[DunningStatus] = None


class SubscriptionCancellation(Model):
    """``subscriptions.cancel``'s answer.

    Attributes:
        subscription: The subscription as the API answered it.
        pending: True when the API answered 202: the cancellation is still confirming on-chain
            and ``subscription.status`` is not updated yet.
    """

    subscription: Subscription = Field(default_factory=Subscription)
    pending: Bool = False


class BillingState(Model):
    """A test billing run's state (``subscriptions.execute_test_billing``)."""

    #: The bill's id, bare (its history entry is ``sub-hist@<bill_uuid>``).
    bill_uuid: Str = Field(default="", alias="billUuid")
    #: running, waiting, pending or done.
    stage: BillingStageT = ""
    #: How it ended, once done.
    outcome: Optional[BillingOutcomeT] = None
    #: The failed attempts so far.
    attempts: UInt = 0
    #: When it tries again at the latest, while waiting or pending.
    next_attempt: Optional[Time] = Field(default=None, alias="nextAttempt")
    #: The charge's transaction, once paid.
    tx_hash: Optional[Str] = Field(default=None, alias="txHash")
    #: The last failure's code (e.g. ``insufficient_allowance``).
    failure_code: Optional[Str] = Field(default=None, alias="failureCode")


class SubscriptionTerms(Model):
    """A subscription product's terms."""

    #: How often it bills (e.g. 1 month: 30 days).
    frequency: Duration = Field(default_factory=Duration)
    #: A free trial before the first bill; ``None`` without one.
    trial_period: Optional[Duration] = Field(default=None, alias="trialPeriod")
    #: The periods the customer commits to before cancelling; ``None`` without a minimum.
    min_periods: Optional[UInt] = Field(default=None, alias="minPeriods")
