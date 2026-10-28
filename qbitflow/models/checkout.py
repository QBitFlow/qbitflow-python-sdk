"""Checkout sessions: a session just created, its status, and its data in ``checkout.expired``."""

from __future__ import annotations

from typing import List, Optional

from pydantic import Field

from ._base import ZERO_TIME, Bool, Model, Str, Time, UInt
from ._fields import CheckoutSessionStatusValueT, TransactionTypeT
from .common import Attempt, Duration, FeeLine, Metadata

__all__ = [
    "CreatedCheckoutSession",
    "CheckoutSessionStatus",
    "PaymentSessionData",
    "SubscriptionSessionData",
]


class CreatedCheckoutSession(Model):
    """A checkout session just opened (``checkout_sessions.create_payment`` /
    ``create_subscription``): the page to send the customer to, its id, and how long it can be
    paid."""

    #: The checkout page for the customer:
    #: ``<the merchant's checkout base URL>/checkout?uuid=<uuid>``.
    link: Str = ""
    #: The session's id (``pay@…``, ``sub@…``), also the id of the payment or subscription it
    #: creates.
    uuid: Str = ""
    #: When the checkout can no longer be paid (``checkout.expired`` is sent then, if it wasn't
    #: paid).
    expires_at: Time = Field(default=ZERO_TIME, alias="expiresAt")


class CheckoutSessionStatus(Model):
    """Where a checkout session stands, for the merchant that created it
    (``checkout_sessions.get`` and ``expire``)."""

    #: The session's id (``pay@…``, ``sub@…``), also the id of the payment or subscription it
    #: creates.
    uuid: Str = ""
    #: ``created`` (waiting for the customer; ``last_attempt``: their last attempt failed, they
    #: may try again until the session expires), ``waitingConfirmation`` (a transaction was sent),
    #: or the final ``completed`` and ``expired``.
    status: CheckoutSessionStatusValueT = ""
    #: The customer's transaction, once sent (not kept for completed subscriptions).
    tx_hash: Optional[Str] = Field(default=None, alias="txHash")
    #: An optional detail, e.g. why the session expired.
    message: Optional[Str] = None
    #: The customer's last failed attempt (its code, reason and time): never final, don't cancel
    #: the order on it; wait for ``completed`` (``payment.completed``, ``subscription.created``)
    #: or ``expired`` (``checkout.expired``).
    last_attempt: Optional[Attempt] = Field(default=None, alias="lastAttempt")
    #: When the checkout can no longer be paid, while it is open (on ``expire``'s answer: when it
    #: was expired); ``None`` once completed, or expired at its time.
    expires_at: Optional[Time] = Field(default=None, alias="expiresAt")


class PaymentSessionData(Model):
    """A one-time payment's checkout session, as ``checkout.expired`` sends it (flat; a
    subscription's is :class:`SubscriptionSessionData`). No customer is named: match it on
    ``uuid``, ``reference`` or ``metadata``."""

    #: The session's id (``pay@…``, ``sub@…``): the id the payment or subscription would have had.
    uuid: Str = ""
    #: The merchant's reference of the checkout (an order id), set when creating it.
    reference: Optional[Str] = None
    #: The product paid for; ``None`` for an inline product of a payment.
    product_uuid: Optional[Str] = Field(default=None, alias="productUuid")
    #: The product's reference, when the checkout named it so.
    product_reference: Optional[Str] = Field(default=None, alias="productReference")
    #: What is paid for: the product's name as the checkout was opened (or the inline one).
    product_name: Optional[Str] = Field(default=None, alias="productName")
    #: The product's description as the checkout was opened; ``None`` without one.
    description: Optional[Str] = None
    #: The product's price in USD, a decimal string.
    price_usd: Str = Field(default="", alias="priceUsd")
    #: What the checkout adds to the price, line by line, in the order the checkout shows them:
    #: the merchant's lines, then the processing fee (when the customer pays it). A
    #: subscription's are charged with every bill. Empty without any.
    fees: List[FeeLine] = Field(default_factory=list)
    #: What the customer pays in USD before the network fee, a decimal string: ``price_usd`` plus
    #: every line of ``fees`` (the payment's ``amount_usd``, or each bill's of a subscription).
    amount_usd: Str = Field(default="", alias="amountUsd")
    #: The merchant's page for the customer after paying (placeholders filled).
    success_url: Optional[Str] = Field(default=None, alias="successUrl")
    #: The merchant's page for a customer who leaves the checkout (placeholders filled).
    cancel_url: Optional[Str] = Field(default=None, alias="cancelUrl")
    #: True for a checkout paid on test networks.
    test: Bool = False
    #: The session's kind: ``payment`` or ``createSubscription``.
    tx_type: TransactionTypeT = Field(default="", alias="txType")
    #: The merchant's own data on the checkout; ``{}`` without any.
    metadata: Metadata = Field(default_factory=dict)
    #: When the session was opened.
    created_at: Optional[Time] = Field(default=None, alias="createdAt")
    #: When it could no longer be paid (when the merchant expired it, if so).
    expires_at: Optional[Time] = Field(default=None, alias="expiresAt")


class SubscriptionSessionData(PaymentSessionData):
    """A subscription's checkout session, as ``checkout.expired`` sends it: the payment
    session's fields and its terms."""

    #: How often it would have billed.
    frequency: Duration = Field(default_factory=Duration)
    #: The free trial; ``None`` without one.
    trial_period: Optional[Duration] = Field(default=None, alias="trialPeriod")
    #: The periods the customer would have committed to; ``None`` without a minimum.
    min_periods: Optional[UInt] = Field(default=None, alias="minPeriods")
    #: True for a checkout confirming a free trial already started (always False in
    #: ``checkout.expired``: such a session sends nothing when it expires).
    upgrading_from_trial: Bool = Field(default=False, alias="upgradingFromTrial")
