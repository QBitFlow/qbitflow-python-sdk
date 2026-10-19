"""Models shared by several resources: durations, currencies, token amounts, settlements and
splits, fee lines, pages.

Typing rule (the same in every QBitFlow SDK): a field the API always sends has a zero default
(``""``, ``0``, ``False``, an empty nested model); a field the API leaves out when it has no value
is ``Optional`` (``None`` when absent); lists default to ``[]`` and merchant ``metadata`` to
``{}``. The API never sends ``null``. **Money, token amounts and fee rates are decimal strings**
(``"12.5"``, ``"10004200"``, ``"0.99"``), never parsed into floats: convert token amounts with
:func:`qbitflow.format_amount` and :func:`qbitflow.parse_amount` (or
:meth:`Currency.format_amount`). Timestamps are timezone-aware ``datetime`` values.
"""

from __future__ import annotations

from typing import Dict, Generic, List, Optional, TypeVar

from pydantic import Field

from .._helpers import format_amount
from ._base import ZERO_TIME, Bool, Model, Str, Time, UInt
from ._fields import (
    AttemptStatusT,
    ChainT,
    DurationUnitT,
    FeeLineTypeT,
    RefundInitiatorT,
    RefundStatusT,
)

__all__ = [
    "Duration",
    "Currency",
    "TokenAmount",
    "CustomerSummary",
    "RefundSummary",
    "Attempt",
    "Settlement",
    "OrganizationFee",
    "ReferralFee",
    "Split",
    "SettlementTransaction",
    "TransferSettlement",
    "FeeLine",
    "Page",
]

T = TypeVar("T")

#: Merchant metadata as models carry it: string keys and string values (``{}`` without any).
Metadata = Dict[str, Str]


class Duration(Model):
    """A length of time as the API writes it: a value in the largest exact unit
    (``Duration(value=1, unit=DurationUnit.MONTHS)`` = 30 days). Used in requests and responses.

    Attributes:
        value: The number of units, 0 to 4294967295; 0 means no duration (a unit is then
            optional).
        unit: Required when ``value`` > 0: seconds, minutes, hours, days, weeks, months (30 days)
            or years (365 days).
    """

    value: UInt = 0
    unit: Optional[DurationUnitT] = None


class Currency(Model):
    """A currency of the catalog: a chain's native coin (ETH, SOL; its chain is itself) or a token
    on a chain (USDC on Base). The one currency object of every response
    (``currencies.list``, :attr:`Payment.currency`, :attr:`Member.accepted_currencies`, …)."""

    #: The currency's id (``client.currencies.get(id)``): a public catalog, unique across test
    #: and live.
    id: UInt = 0
    #: What requests name it by: ``CHAIN:TOKEN`` for a token (``"BASE:USDC"``), the chain's
    #: symbol for its native coin (``"ETH"``).
    code: Str = ""
    #: Its symbol (``"USDC"``, ``"ETH"``).
    symbol: Str = ""
    #: Its full name (``"USD Coin"``, ``"Ethereum"``).
    name: Str = ""
    #: The chain it is on, by its native coin's symbol: ``ETH``, ``BASE`` or ``SOL``.
    chain: ChainT = ""
    #: The decimals of its on-chain amounts: min units = amount × 10^decimals (6 for USDC).
    #: :meth:`format_amount` converts with it.
    decimals: UInt = 0
    #: A token's contract address (EVM) or mint (Solana); ``None`` on a native coin.
    address: Optional[Str] = None
    #: A token's chain, by its native coin's id; ``None`` on a native coin.
    main_currency_id: Optional[UInt] = Field(default=None, alias="mainCurrencyId")
    #: True for a test network's currency, False for a live one.
    test: Bool = False

    def format_amount(self, min_units: str) -> str:
        """An amount of this currency in minimal units as a decimal string, exactly:
        :func:`qbitflow.format_amount` with this currency's ``decimals``
        (``usdc.format_amount("1500000") == "1.5"``).

        Raises:
            ValidationError: ``min_units`` is not an integer string (``-?[0-9]+``).
        """
        return format_amount(min_units, self.decimals)


class TokenAmount(Model):
    """An amount of a token (or of a chain's native coin, when its field says so) as responses
    write it: the exact amount in the token's units and its on-chain integer, always together, and
    its USD value when a price is known. Its currency is the resource's::

        {"amount": "12.5", "amountMinUnits": "12500000", "amountUsd": "12.5"}
    """

    #: The amount in the token's units, exact: ``amount_min_units / 10^decimals``, a decimal
    #: string (``"12.5"``).
    amount: Str = ""
    #: The on-chain integer, in the token's smallest unit, a string of digits (``"12500000"``).
    amount_min_units: Str = Field(default="", alias="amountMinUnits")
    #: Its value in USD, a decimal string; ``None`` when no price was known.
    amount_usd: Optional[Str] = Field(default=None, alias="amountUsd")


class CustomerSummary(Model):
    """A customer as a transaction row names it (a payment, a bill, a subscription, a refund): who
    paid, even once the merchant deleted the customer. Merchant API reads only: never in
    webhooks."""

    #: The customer (``customers.get``).
    uuid: Str = ""
    #: The first name.
    first_name: Str = Field(default="", alias="firstName")
    #: The last name; ``None`` when not given.
    last_name: Optional[Str] = Field(default=None, alias="lastName")
    #: The email, lowercase.
    email: Str = ""
    #: The merchant's reference of the customer; ``None`` without one.
    reference: Optional[Str] = None
    #: True when the merchant deleted the customer: it still names its rows, but
    #: ``customers.get`` answers 404.
    deleted: Bool = False


class RefundSummary(Model):
    """A payment's or bill's refund, as the payment shows it (``refunds.get`` has the rest of the
    refund with the same id)."""

    #: The refund (``refund@…``).
    uuid: Str = ""
    #: pending, approved or rejected.
    status: RefundStatusT = ""
    #: ``customer`` (a request) or ``merchant``.
    initiated_by: RefundInitiatorT = Field(default="", alias="initiatedBy")
    #: The share of what the customer paid it sends back, a percent string (``"100"``: all of it).
    refund_percent: Str = Field(default="", alias="refundPercent")
    #: What it sends back, in the currency's units (a decimal string); ``None`` when its currency
    #: isn't known (a refund requested before refunds named it).
    amount: Optional[Str] = None
    #: The same in the currency's smallest unit (a string of digits).
    amount_min_units: Str = Field(default="", alias="amountMinUnits")
    #: The same in USD, at the payment's time (a decimal string); ``None`` when unknown.
    amount_usd: Optional[Str] = Field(default=None, alias="amountUsd")
    #: When it was requested or prepared.
    created_at: Time = Field(default=ZERO_TIME, alias="createdAt")
    #: When it was approved (confirmed) or rejected; ``None`` while pending.
    responded_at: Optional[Time] = Field(default=None, alias="respondedAt")


class Attempt(Model):
    """How a session's (or a refund approval's) last attempt failed, while it waits for another:
    never final."""

    #: ``failed``.
    status: AttemptStatusT = ""
    #: The error code (e.g. ``insufficient_funds``, ``token_not_approved``): what to do about it.
    code: Optional[Str] = None
    #: The reason, for the customer.
    message: Optional[Str] = None
    #: The attempt's transaction, if it was sent.
    tx_hash: Optional[Str] = Field(default=None, alias="txHash")
    #: When it failed.
    at: Time = ZERO_TIME


class OrganizationFee(Model):
    """The organization's fee on its member's payment or bill (a marketplace's commission)."""

    #: The organization's wallet that receives the fee.
    address: Str = ""
    #: The fee, a percent string, taken from what remains after QBitFlow's fee.
    fee_percent: Str = Field(default="", alias="feePercent")


class ReferralFee(Model):
    """The referrer's share of QBitFlow's fee on a payment or bill."""

    #: The referrer's wallet that receives the fee.
    address: Str = ""
    #: The referrer's share of the platform fee, a percent string (``"20"`` = 20 % of it).
    fee_percent: Str = Field(default="", alias="feePercent")
    #: Until when the referrer earns its share.
    deadline: Time = ZERO_TIME


class Split(Model):
    """How a payment or a bill was split, as the contracts paid it. Each part is an amount of the
    payment's currency (USD values in proportion to the payment's, to 6 decimals):
    ``platform + organization + referral + merchant`` = the payment's amount, exactly, in each
    unit."""

    #: QBitFlow's fee (the referrer's share not included).
    platform: TokenAmount = Field(default_factory=TokenAmount)
    #: The organization's fee; ``None`` without one.
    organization: Optional[TokenAmount] = None
    #: The referrer's share of QBitFlow's fee; ``None`` without one.
    referral: Optional[TokenAmount] = None
    #: What the merchant (the member, for a member's payment) received, net of every fee.
    merchant: TokenAmount = Field(default_factory=TokenAmount)
    #: The network fee the payer paid on top of the amount, in the payment's currency; ``None`` on
    #: records made before it was recorded (``"0"`` once recorded as none).
    network_fee: Optional[TokenAmount] = Field(default=None, alias="networkFee")


class SettlementTransaction(Model):
    """The transaction that paid (or refunded, or released): where and when it landed, and what it
    cost its sender in the chain's native coin."""

    #: The block (Ethereum, Base) or slot (Solana) it landed in, a string of digits.
    block_number: Str = Field(default="", alias="blockNumber")
    #: When its block was produced (UTC); ``None`` only on records made before it was recorded.
    block_time: Optional[Time] = Field(default=None, alias="blockTime")
    #: The gas it consumed (Ethereum, Base); ``None`` on Solana.
    gas_used: Optional[UInt] = Field(default=None, alias="gasUsed")
    #: What the transaction cost its sender, in the chain's native coin (ETH, SOL): its gas and,
    #: on Base, its L1 data fee; its ``amount_usd`` at ``native_price_usd``.
    fee: TokenAmount = Field(default_factory=TokenAmount)
    #: The part of ``fee`` that paid Base's L1 data fee, in the native coin; ``None`` off Base.
    l1_fee: Optional[TokenAmount] = Field(default=None, alias="l1Fee")
    #: The USD price of the chain's native coin when the transaction was recorded (a decimal
    #: string); ``None`` when no price was available.
    native_price_usd: Optional[Str] = Field(default=None, alias="nativePriceUsd")


class Settlement(Model):
    """QBitFlow's record of how a payment or a bill settled, made once at confirmation: its fee
    terms, how the contracts split what the payer paid, and the transaction that paid it. Every
    fee record, export, held-funds total and refund reads it. Merchant only (API reads and
    webhooks)."""

    #: QBitFlow's fee on the payment, a percent string (``"0.99"`` = 0.99 %), deducted from the
    #: amount paid.
    fee_percent: Str = Field(default="", alias="feePercent")
    #: The organization's fee on its member's payment (a marketplace's commission), taken from
    #: what remains after QBitFlow's fee; ``None`` when none.
    organization_fee: Optional[OrganizationFee] = Field(default=None, alias="organizationFee")
    #: The referrer's share of QBitFlow's fee; ``None`` when none.
    referral_fee: Optional[ReferralFee] = Field(default=None, alias="referralFee")
    #: How the contracts split what the payer paid; ``None`` on records made before the split was
    #: recorded. For a payment the organization held for its member, it is the split a direct
    #: payment would have had (the organization's fee withheld, not paid on-chain).
    split: Optional[Split] = None
    #: The transaction that paid it; ``None`` before its confirmation.
    transaction: Optional[SettlementTransaction] = None


class TransferSettlement(Model):
    """What a refund or a held-funds release records of its transfer: the transaction only (a
    transfer pays no fee and has no split)."""

    #: The transfer's transaction; ``None`` before it was confirmed.
    transaction: Optional[SettlementTransaction] = None


class FeeLine(Model):
    """An amount a checkout adds to its product's price (a tax, shipping, QBitFlow's processing
    fee), shown to the customer line by line and paid with the price, a subscription's with every
    bill (:attr:`Payment.fees`, :attr:`Subscription.fees`, :attr:`Transaction.fees`,
    :attr:`PaymentSessionData.fees`)."""

    #: ``custom`` (the merchant's line) or ``processingFee`` (QBitFlow's fee, which the merchant
    #: has the customer pay).
    type: FeeLineTypeT = ""
    #: The line's name, as the checkout shows it (``Processing fee`` for the processing fee).
    label: Str = ""
    #: More about the line, as the merchant wrote it; ``None`` without one.
    description: Optional[Str] = None
    #: The line's amount in USD, a decimal string with at most 2 decimals (``"4.99"``).
    amount_usd: Str = Field(default="", alias="amountUsd")


class Page(Model, Generic[T]):
    """One page of a cursor-paginated list, newest first (members by when they joined).

    Attributes:
        items: The page's rows; empty when there are none.
        has_more: Whether another page follows: pass ``next_cursor`` back as ``cursor=`` to read
            it. A full last page answers False: there is never an extra empty page.
        next_cursor: The next page's cursor, opaque: pass it back verbatim, never build or parse
            it. ``None`` when ``has_more`` is False.
    """

    items: List[T] = Field(default_factory=list)
    has_more: Bool = Field(default=False, alias="hasMore")
    next_cursor: Optional[Str] = Field(default=None, alias="nextCursor")
