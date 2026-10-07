"""Payments, bills, the combined feed and the failures log."""

from __future__ import annotations

from typing import Optional

from pydantic import Field

from ._base import ZERO_TIME, Bool, Float, Int, Model, Str, Time, UInt
from ._fields import (
    ChainT,
    CombinedPaymentSourceT,
    FailureCategoryT,
    FailureKindT,
    NotRefundableReasonT,
)
from .common import Currency, CustomerSummary, PaymentMetadata, RefundSummary

__all__ = ["Payment", "Bill", "CombinedPayment", "Failure"]


class Transfer(Model):
    """The fields every on-chain transfer has (a payment, a bill, a held-funds release)."""

    #: The transfer's id (``pay@…``, ``sub-hist@…``, ``transfer@…``).
    uuid: Str = ""
    #: When it was recorded, once confirmed on-chain.
    created_at: Time = Field(default=ZERO_TIME, alias="createdAt")
    #: The sender's wallet (``from`` on the wire).
    from_: Str = Field(default="", alias="from")
    #: The wallet that received it.
    to: Str = ""
    #: The amount, in USD (the network fee paid on top excluded).
    amount: Float = 0.0
    #: The amount in the token's min units (a decimal string).
    amount_min_units: Str = Field(default="", alias="amountMinUnits")
    #: The currency paid in.
    currency_id: UInt = Field(default=0, alias="currencyId")
    #: That currency, as ``client.currencies.get`` returns it.
    currency: Optional[Currency] = None
    #: The transaction's hash.
    tx_hash: Str = Field(default="", alias="txHash")
    #: The chain it was paid on (ETH, BASE, SOL; the testnet's in test mode).
    chain: Optional[ChainT] = None
    #: The transaction on the chain's block explorer.
    explorer_url: Optional[Str] = Field(default=None, alias="explorerUrl")
    #: True in test mode.
    test: Bool = False
    #: The member whose space it is in; ``None`` for the organization's own.
    user_uuid: Optional[Str] = Field(default=None, alias="userUuid")


class Payment(Transfer):
    """A confirmed one-time payment. ``uuid`` (``pay@…``) is also its checkout session's id."""

    #: The merchant's reference for the payment, set when creating its checkout.
    reference: Optional[Str] = None
    #: What was paid for: the checkout's product name when the checkout was created.
    name: Str = ""
    #: The same, for the product's description.
    description: Str = ""
    #: The product paid for; ``None`` for an inline product.
    product_uuid: Optional[Str] = Field(default=None, alias="productUuid")
    #: The customer, when QBitFlow has one.
    customer_uuid: Optional[Str] = Field(default=None, alias="customerUuid")
    #: The merchant's reference of the customer, as the checkout was given it.
    customer_reference: Optional[Str] = Field(default=None, alias="customerReference")
    #: A qbf.cash tipper's message to the handle's owner.
    note: Optional[Str] = None
    #: Names the customer (API reads only, never in webhooks).
    customer: Optional[CustomerSummary] = None
    #: The payment's fees and split.
    metadata: PaymentMetadata = Field(default_factory=PaymentMetadata)
    #: When the chain confirmed it (its block's time), when known.
    confirmed_at: Optional[Time] = Field(default=None, alias="confirmedAt")
    #: Everything the customer's wallet sent (amount plus the network fee on top), in min units:
    #: a refund's base.
    paid_min_units: Optional[Str] = Field(default=None, alias="paidMinUnits")
    #: The same in USD.
    paid_usd: Optional[Float] = Field(default=None, alias="paidUsd")
    #: Its refund, if any (API reads only).
    refund: Optional[RefundSummary] = None
    #: Whether it can be refunded now (API reads only).
    refundable: Optional[Bool] = None
    #: Why not (``refundExists``, ``heldFundsReleased``).
    not_refundable_reason: Optional[NotRefundableReasonT] = Field(
        default=None, alias="notRefundableReason"
    )
    #: When its checkout session was created.
    checkout_opened_at: Optional[Time] = Field(default=None, alias="checkoutOpenedAt")


class Bill(Transfer):
    """A subscription's paid bill (a subscription history entry, ``sub-hist@…``).

    On ``subscriptions.get_public_history`` the fields only the merchant sees (``customer_uuid``,
    ``customer_reference``, ``customer``, ``metadata``, ``user_uuid``, ``paid_min_units``,
    ``paid_usd``, ``refund``…) are empty.
    """

    #: The subscription's product name when the bill was paid.
    name: Str = ""
    #: The same, for the product's description.
    description: Str = ""
    #: The subscription's product.
    product_uuid: Optional[Str] = Field(default=None, alias="productUuid")
    #: The bill's subscription (``sub@…``).
    subscription_uuid: Str = Field(default="", alias="subscriptionUuid")
    customer_uuid: Optional[Str] = Field(default=None, alias="customerUuid")
    customer_reference: Optional[Str] = Field(default=None, alias="customerReference")
    #: Names the customer (API reads only).
    customer: Optional[CustomerSummary] = None
    #: The bill's fees and split.
    metadata: PaymentMetadata = Field(default_factory=PaymentMetadata)
    #: The start of the period the bill paid (its due date).
    period_start: Optional[Time] = Field(default=None, alias="periodStart")
    #: The end of the period the bill paid: paid until then.
    period_end: Optional[Time] = Field(default=None, alias="periodEnd")
    confirmed_at: Optional[Time] = Field(default=None, alias="confirmedAt")
    paid_min_units: Optional[Str] = Field(default=None, alias="paidMinUnits")
    paid_usd: Optional[Float] = Field(default=None, alias="paidUsd")
    refund: Optional[RefundSummary] = None
    refundable: Optional[Bool] = None
    not_refundable_reason: Optional[NotRefundableReasonT] = Field(
        default=None, alias="notRefundableReason"
    )


class CombinedPayment(Model):
    """A row of the combined feed: a one-time payment or a subscription's bill."""

    #: ``payment`` or ``subscriptionHistory``.
    source: CombinedPaymentSourceT = ""
    #: The payment's (``pay@…``) or the bill's (``sub-hist@…``) id.
    uuid: Str = ""
    created_at: Time = Field(default=ZERO_TIME, alias="createdAt")
    #: The customer's wallet (``from`` on the wire).
    from_: Str = Field(default="", alias="from")
    to: Str = ""
    name: Str = ""
    description: Str = ""
    amount: Float = 0.0
    amount_min_units: Str = Field(default="", alias="amountMinUnits")
    currency_id: UInt = Field(default=0, alias="currencyId")
    currency: Optional[Currency] = None
    product_uuid: Optional[Str] = Field(default=None, alias="productUuid")
    tx_hash: Str = Field(default="", alias="txHash")
    customer_uuid: Optional[Str] = Field(default=None, alias="customerUuid")
    customer: Optional[CustomerSummary] = None
    customer_reference: Optional[Str] = Field(default=None, alias="customerReference")
    #: The bill's subscription (``sub@…``); ``None`` on a payment.
    subscription_uuid: Optional[Str] = Field(default=None, alias="subscriptionUuid")
    #: The payment's own reference (payment rows).
    reference: Optional[Str] = None
    #: The reference of the bill's subscription (bill rows).
    subscription_reference: Optional[Str] = Field(default=None, alias="subscriptionReference")
    chain: Optional[ChainT] = None
    explorer_url: Optional[Str] = Field(default=None, alias="explorerUrl")
    test: Bool = False
    user_uuid: Optional[Str] = Field(default=None, alias="userUuid")
    refund: Optional[RefundSummary] = None
    refundable: Optional[Bool] = None
    not_refundable_reason: Optional[NotRefundableReasonT] = Field(
        default=None, alias="notRefundableReason"
    )
    #: Its fees and split; ``None`` only on payments recorded before fees were split (v1).
    metadata: Optional[PaymentMetadata] = None


class Failure(Model):
    """A failed attempt to pay a checkout or a bill (the failures log). Never moved money."""

    uuid: Str = ""
    #: ``payment``, ``subscriptionCheckout`` or ``bill``.
    kind: FailureKindT = ""
    #: What failed: the checkout (``pay@…``, ``sub@…``) or the bill (``sub-hist@…``).
    tx_uuid: Str = Field(default="", alias="txUuid")
    #: Its number among its transaction's failed attempts, from 1.
    attempt: Int = 0
    #: A bill's subscription (``sub@…``).
    subscription_uuid: Optional[Str] = Field(default=None, alias="subscriptionUuid")
    #: The error code (e.g. ``insufficient_funds``).
    code: Str = ""
    #: What it means, from the code.
    category: FailureCategoryT = ""
    #: What the customer was told.
    message: Optional[Str] = None
    #: What the customer tried to pay, in USD: never received.
    attempted_usd: Float = Field(default=0.0, alias="attemptedUsd")
    #: The same in the currency's min units (a decimal string).
    attempted_min_units: Str = Field(default="", alias="attemptedMinUnits")
    currency_id: UInt = Field(default=0, alias="currencyId")
    #: The customer's wallet (``from`` on the wire).
    from_: Str = Field(default="", alias="from")
    #: The transaction, when one was sent (a revert, a timeout).
    tx_hash: Optional[Str] = Field(default=None, alias="txHash")
    customer_uuid: Optional[Str] = Field(default=None, alias="customerUuid")
    product_uuid: Optional[Str] = Field(default=None, alias="productUuid")
    created_at: Time = Field(default=ZERO_TIME, alias="createdAt")
    customer: Optional[CustomerSummary] = None
    test: Bool = False
    user_uuid: Optional[Str] = Field(default=None, alias="userUuid")
