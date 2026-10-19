"""Payments, bills, the transactions feed and the failures log."""

from __future__ import annotations

from typing import List, Optional

from pydantic import Field

from ._base import ZERO_TIME, Bool, Int, Model, Str, Time
from ._fields import (
    ChainT,
    FailureCategoryT,
    FailureKindT,
    NotRefundableReasonT,
    TransactionKindT,
)
from .common import Currency, CustomerSummary, FeeLine, Metadata, RefundSummary, Settlement

__all__ = ["Payment", "Bill", "Transaction", "Failure"]


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
    #: What was sent, in the currency's units, exact (a decimal string: ``"10"`` for 10 USDC):
    #: ``amount_min_units / 10^decimals``.
    amount: Str = ""
    #: The same in the currency's smallest unit, a string of digits (``"10000000"`` for 10 USDC).
    amount_min_units: Str = Field(default="", alias="amountMinUnits")
    #: The same in USD, a decimal string.
    amount_usd: Str = Field(default="", alias="amountUsd")
    #: The currency paid in.
    currency: Currency = Field(default_factory=Currency)
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
    """A confirmed one-time payment. ``uuid`` (``pay@…``) is also its checkout session's id.

    ``amount`` is what the customer paid, in the currency's units, exact: what the contracts
    split; the network fee paid on top is not in it (``settlement.split.network_fee``).
    ``amount_usd`` is the same in USD: ``price_usd`` plus every line of ``fees``.
    """

    #: Your reference for the payment (an order or invoice id), set when creating its checkout.
    reference: Optional[Str] = None
    #: The product's price in USD, as the checkout had it, a decimal string: ``amount_usd`` is the
    #: price plus the ``fees`` lines.
    price_usd: Str = Field(default="", alias="priceUsd")
    #: What the checkout added to the price, line by line, as the customer saw them (a tax,
    #: shipping, the processing fee when the customer paid it); empty without any.
    fees: List[FeeLine] = Field(default_factory=list)
    #: What was paid for: the checkout's product name when the checkout was created (later
    #: product edits don't change it).
    product_name: Str = Field(default="", alias="productName")
    #: The same, for the product's description; ``None`` without one.
    product_description: Optional[Str] = Field(default=None, alias="productDescription")
    #: Your own data, copied (read-only) from the checkout session that created the payment;
    #: ``{}`` without any.
    metadata: Metadata = Field(default_factory=dict)
    #: The product paid for; ``None`` for an inline product.
    product_uuid: Optional[Str] = Field(default=None, alias="productUuid")
    #: The customer, when QBitFlow has one (named by the checkout, found by its
    #: ``customer_reference``, or recorded from the details the customer gave).
    customer_uuid: Optional[Str] = Field(default=None, alias="customerUuid")
    #: Your reference of the customer, as the checkout was given it, whether or not QBitFlow has
    #: a customer with it.
    customer_reference: Optional[Str] = Field(default=None, alias="customerReference")
    #: A qbf.cash tipper's message to the handle's owner.
    note: Optional[Str] = None
    #: Names the customer, even once deleted (API reads only, never in webhooks).
    customer: Optional[CustomerSummary] = None
    #: How it settled: its fees, its split and its transaction.
    settlement: Settlement = Field(default_factory=Settlement)
    #: When the chain confirmed it (its block's time); ``None`` only on records made before it
    #: was recorded.
    confirmed_at: Optional[Time] = Field(default=None, alias="confirmedAt")
    #: Everything the customer's wallet sent, in the currency's units: ``amount`` plus the network
    #: fee paid on top. A refund's base. ``None`` when the split wasn't recorded.
    paid: Optional[Str] = None
    #: The same in the currency's smallest unit.
    paid_min_units: Optional[Str] = Field(default=None, alias="paidMinUnits")
    #: The same in USD, at the payment's time.
    paid_usd: Optional[Str] = Field(default=None, alias="paidUsd")
    #: Its refund (one per transaction), if any (API reads only). A merchant's refund not sent
    #: yet is shown, and doesn't make it unrefundable: a new refund replaces it.
    refund: Optional[RefundSummary] = None
    #: Whether it can be refunded now (API reads only).
    refundable: Optional[Bool] = None
    #: Why not (``refundExists``, ``heldFundsReleased``); ``None`` when refundable.
    not_refundable_reason: Optional[NotRefundableReasonT] = Field(
        default=None, alias="notRefundableReason"
    )
    #: When its checkout session was created.
    checkout_opened_at: Optional[Time] = Field(default=None, alias="checkoutOpenedAt")


class Bill(Transfer):
    """One paid bill of a subscription (``sub-hist@…``): what its customer paid for one period
    (``period_start`` → ``period_end``), in the subscription's token, and how it settled. A failed
    attempt is no bill (``failures.list``, ``subscription.billingFailed``). Bills carry no
    merchant metadata: read the subscription's.

    ``amount_usd`` is what the customer paid in USD: the subscription's ``price_usd`` plus its
    ``fees`` lines.
    """

    #: The subscription's product name when the bill was paid (later product edits don't change
    #: it).
    product_name: Str = Field(default="", alias="productName")
    #: The same, for the product's description; ``None`` without one.
    product_description: Optional[Str] = Field(default=None, alias="productDescription")
    #: The subscription's product.
    product_uuid: Optional[Str] = Field(default=None, alias="productUuid")
    #: The subscription it bills (``sub@…``).
    subscription_uuid: Str = Field(default="", alias="subscriptionUuid")
    #: The customer, when QBitFlow has one.
    customer_uuid: Optional[Str] = Field(default=None, alias="customerUuid")
    #: Your reference of the customer, as the checkout was given it.
    customer_reference: Optional[Str] = Field(default=None, alias="customerReference")
    #: Names the customer, even once deleted (API reads only).
    customer: Optional[CustomerSummary] = None
    #: How it settled: its fees, its split and its transaction.
    settlement: Settlement = Field(default_factory=Settlement)
    #: The start of the period the bill paid: its due date (the subscription's start for its
    #: first bill); ``None`` on bills recorded before it was.
    period_start: Optional[Time] = Field(default=None, alias="periodStart")
    #: The end of the period the bill paid (the subscription's next bill): paid until then;
    #: ``None`` on bills recorded before it was.
    period_end: Optional[Time] = Field(default=None, alias="periodEnd")
    #: When the chain confirmed it (its block's time).
    confirmed_at: Optional[Time] = Field(default=None, alias="confirmedAt")
    #: Everything the customer's wallet sent, in the currency's units (``amount`` plus the network
    #: fee): a refund's base.
    paid: Optional[Str] = None
    #: The same in the currency's smallest unit.
    paid_min_units: Optional[Str] = Field(default=None, alias="paidMinUnits")
    #: The same in USD.
    paid_usd: Optional[Str] = Field(default=None, alias="paidUsd")
    #: Its refund, if any (API reads only).
    refund: Optional[RefundSummary] = None
    #: Whether it can be refunded now (API reads only).
    refundable: Optional[Bool] = None
    #: Why not.
    not_refundable_reason: Optional[NotRefundableReasonT] = Field(
        default=None, alias="notRefundableReason"
    )


class Transaction(Model):
    """A row of the transactions feed (``transactions.list``): a one-time payment or a
    subscription's bill, with the fields of its resource (a :class:`Payment` or a :class:`Bill`).
    Open the row's detail by its ``type`` and ``uuid`` (``payments.get``,
    ``subscriptions.get_bill``)."""

    #: ``payment`` (``pay@…``) or ``bill`` (``sub-hist@…``).
    type: TransactionKindT = ""
    #: The payment's (``pay@…``) or the bill's (``sub-hist@…``) id.
    uuid: Str = ""
    #: When it was recorded, once confirmed on-chain.
    created_at: Time = Field(default=ZERO_TIME, alias="createdAt")
    #: The customer's wallet that paid (``from`` on the wire).
    from_: Str = Field(default="", alias="from")
    #: The wallet that received it.
    to: Str = ""
    #: What was paid for (a payment: its checkout's product name; a bill: its subscription's
    #: product name when it was billed).
    product_name: Str = Field(default="", alias="productName")
    #: The same, for the description; ``None`` without one.
    product_description: Optional[Str] = Field(default=None, alias="productDescription")
    #: The price in USD, a decimal string: a payment's checkout price, a bill's subscription's
    #: locked price; ``None`` on a bill of a subscription without a locked price.
    price_usd: Optional[Str] = Field(default=None, alias="priceUsd")
    #: What was added to the price, line by line; empty without any.
    fees: List[FeeLine] = Field(default_factory=list)
    #: What the customer paid, in the currency's units, exact (a decimal string).
    amount: Str = ""
    #: The same in the currency's smallest unit, a string of digits.
    amount_min_units: Str = Field(default="", alias="amountMinUnits")
    #: What the customer paid in USD: the price and the fees' lines.
    amount_usd: Str = Field(default="", alias="amountUsd")
    #: The currency paid in.
    currency: Currency = Field(default_factory=Currency)
    #: The product paid for; ``None`` for an inline product.
    product_uuid: Optional[Str] = Field(default=None, alias="productUuid")
    #: The transaction that paid it.
    tx_hash: Str = Field(default="", alias="txHash")
    #: The customer, when QBitFlow has one.
    customer_uuid: Optional[Str] = Field(default=None, alias="customerUuid")
    #: Names the customer, even once deleted (API reads only).
    customer: Optional[CustomerSummary] = None
    #: Your reference of the customer, as the checkout was given it.
    customer_reference: Optional[Str] = Field(default=None, alias="customerReference")
    #: A bill's subscription (``sub@…``); ``None`` on a payment.
    subscription_uuid: Optional[Str] = Field(default=None, alias="subscriptionUuid")
    #: A bill's period's start (its due date); ``None`` on a payment.
    period_start: Optional[Time] = Field(default=None, alias="periodStart")
    #: A bill's period's end: paid until then; ``None`` on a payment.
    period_end: Optional[Time] = Field(default=None, alias="periodEnd")
    #: A payment's own reference (a bill has none of its own).
    reference: Optional[Str] = None
    #: The reference of a bill's subscription.
    subscription_reference: Optional[Str] = Field(default=None, alias="subscriptionReference")
    #: A payment's merchant data (copied from its checkout session); ``{}`` for a bill (its
    #: subscription's is on the subscription).
    metadata: Metadata = Field(default_factory=dict)
    #: The chain it was paid on.
    chain: Optional[ChainT] = None
    #: The transaction on the chain's block explorer.
    explorer_url: Optional[Str] = Field(default=None, alias="explorerUrl")
    #: True in test mode.
    test: Bool = False
    #: The member whose space the row is in; ``None`` for the organization's own.
    user_uuid: Optional[Str] = Field(default=None, alias="userUuid")
    #: Its fees, split and transaction, as on the :class:`Payment` or the :class:`Bill`.
    settlement: Settlement = Field(default_factory=Settlement)
    #: When the chain confirmed it.
    confirmed_at: Optional[Time] = Field(default=None, alias="confirmedAt")
    #: Everything the customer's wallet sent, in the currency's units.
    paid: Optional[Str] = None
    #: The same in the currency's smallest unit.
    paid_min_units: Optional[Str] = Field(default=None, alias="paidMinUnits")
    #: The same in USD.
    paid_usd: Optional[Str] = Field(default=None, alias="paidUsd")
    #: Its refund, if any.
    refund: Optional[RefundSummary] = None
    #: Whether it can be refunded now.
    refundable: Optional[Bool] = None
    #: Why not.
    not_refundable_reason: Optional[NotRefundableReasonT] = Field(
        default=None, alias="notRefundableReason"
    )


class Failure(Model):
    """A failed payment attempt (the failures log): what the customer tried to pay, and why it
    failed. Recorded once per attempt, never changed; it never moved money."""

    #: The failure's own id, a plain UUID (a failed attempt is no transaction: no prefix).
    uuid: Str = ""
    #: ``payment``, ``subscriptionCheckout`` or ``bill``.
    kind: FailureKindT = ""
    #: What failed: the checkout (``pay@…``, ``sub@…``: the id its payment or subscription would
    #: have had) or the bill (``sub-hist@…``: its id once paid).
    tx_uuid: Str = Field(default="", alias="txUuid")
    #: Its number among its transaction's failed attempts, from 1.
    attempt: Int = 0
    #: A bill's subscription (``sub@…``).
    subscription_uuid: Optional[Str] = Field(default=None, alias="subscriptionUuid")
    #: The error code (e.g. ``insufficient_funds``).
    code: Str = ""
    #: What it means, from the code.
    category: FailureCategoryT = ""
    #: What the customer was told; ``None`` without a message.
    message: Optional[Str] = None
    #: What the customer tried to pay, in the currency's units, exact (a decimal string): never
    #: received.
    attempted: Str = ""
    #: The same in the currency's smallest unit, a string of digits.
    attempted_min_units: Str = Field(default="", alias="attemptedMinUnits")
    #: The same in USD, a decimal string.
    attempted_usd: Str = Field(default="", alias="attemptedUsd")
    #: The currency it was tried in.
    currency: Currency = Field(default_factory=Currency)
    #: The customer's wallet (``from`` on the wire).
    from_: Str = Field(default="", alias="from")
    #: The transaction, when one was sent (a revert, a timeout).
    tx_hash: Optional[Str] = Field(default=None, alias="txHash")
    #: The customer, when QBitFlow has one.
    customer_uuid: Optional[Str] = Field(default=None, alias="customerUuid")
    #: The product, when it had one.
    product_uuid: Optional[Str] = Field(default=None, alias="productUuid")
    #: When it failed.
    created_at: Time = Field(default=ZERO_TIME, alias="createdAt")
    #: Names the customer (API reads only).
    customer: Optional[CustomerSummary] = None
    #: True in test mode.
    test: Bool = False
    #: The member whose space it was paid to; ``None`` for the organization's own.
    user_uuid: Optional[Str] = Field(default=None, alias="userUuid")
