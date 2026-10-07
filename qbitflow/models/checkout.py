"""Checkout sessions."""

from __future__ import annotations

from typing import List, Optional

from pydantic import Field

from ._base import Bool, Float, Model, Str, Time, UInt
from ._fields import CheckoutSessionStatusValueT, TransactionTypeT
from .common import Attempt, Duration

__all__ = [
    "CheckoutSession",
    "CheckoutSessionStatus",
    "PaymentSessionData",
    "SubscriptionSessionData",
]


class CheckoutSession(Model):
    """A created checkout session: send the customer to ``link``."""

    #: The checkout page for the customer.
    link: Str = ""
    #: The session's id (``pay@…``, ``sub@…``), also the id of the payment or subscription it
    #: creates.
    uuid: Str = ""
    #: When the checkout can no longer be paid (``checkout.expired`` is sent then).
    expires_at: Optional[Time] = Field(default=None, alias="expiresAt")


class CheckoutSessionStatus(Model):
    """A checkout session's status."""

    uuid: Str = ""
    #: ``created`` (waiting for the customer; ``last_attempt``: their last attempt failed),
    #: ``waitingConfirmation``, ``completed`` or ``expired``.
    status: CheckoutSessionStatusValueT = ""
    #: The customer's transaction, once sent (not kept for completed subscriptions).
    tx_hash: Optional[Str] = Field(default=None, alias="txHash")
    #: An optional detail, e.g. why the session expired.
    message: Optional[Str] = None
    #: The customer's last failed attempt: never final, don't cancel the order on it.
    last_attempt: Optional[Attempt] = Field(default=None, alias="lastAttempt")


class PaymentSessionData(Model):
    """A payment checkout session, as ``checkout.expired`` sends it."""

    uuid: Str = ""
    reference: Optional[Str] = None
    product_uuid: Optional[Str] = Field(default=None, alias="productUuid")
    product_reference: Optional[Str] = Field(default=None, alias="productReference")
    product_name: Optional[Str] = Field(default=None, alias="productName")
    description: Optional[Str] = None
    #: The price in USD.
    price: Optional[Float] = None
    #: Where the customer goes after paying (placeholders filled).
    success_url: Optional[Str] = Field(default=None, alias="successUrl")
    cancel_url: Optional[Str] = Field(default=None, alias="cancelUrl")
    #: The merchant's success page, on QBitFlow's own success page's copy.
    redirect_url: Optional[Str] = Field(default=None, alias="redirectUrl")
    organization_name: Str = Field(default="", alias="organizationName")
    #: The member who created it, for a member's session.
    user_name: Optional[Str] = Field(default=None, alias="userName")
    test: Bool = False
    #: ``payment`` or ``createSubscription``.
    tx_type: TransactionTypeT = Field(default="", alias="txType")
    #: The currencies accepted for the payment.
    available_currency_ids: List[UInt] = Field(default_factory=list, alias="availableCurrencyIds")
    created_at: Optional[Time] = Field(default=None, alias="createdAt")
    expires_at: Optional[Time] = Field(default=None, alias="expiresAt")


class SubscriptionSessionData(PaymentSessionData):
    """A subscription checkout session, as ``checkout.expired`` sends it."""

    #: How often it bills.
    frequency: Duration = Field(default_factory=Duration)
    #: The free trial; ``None`` without one.
    trial_period: Optional[Duration] = Field(default=None, alias="trialPeriod")
    #: The periods the customer commits to; ``None`` without a minimum.
    min_periods: Optional[UInt] = Field(default=None, alias="minPeriods")
    #: True when it upgrades a trial.
    upgrading_from_trial: Optional[Bool] = Field(default=None, alias="upgradingFromTrial")
