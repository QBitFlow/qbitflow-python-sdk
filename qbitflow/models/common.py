"""Models shared by several resources: durations, currencies, fees and splits, pages."""

from __future__ import annotations

from typing import Generic, List, Optional, TypeVar

from pydantic import Field

from .._helpers import format_amount
from ._base import ZERO_TIME, Bool, Float, Model, Str, Time, UInt
from ._fields import (
    AttemptStatusT,
    DurationUnitT,
    FeeLineTypeT,
    RefundInitiatorT,
    RefundStatusT,
)

__all__ = [
    "Duration",
    "Currency",
    "CustomerSummary",
    "RefundSummary",
    "Attempt",
    "FeeLine",
    "PaymentMetadata",
    "OrganizationFee",
    "ReferralFee",
    "TxMetadata",
    "BlockData",
    "NetworkFees",
    "TxAmounts",
    "TxAmountsMinUnits",
    "TxAmountsUsd",
    "Page",
]

T = TypeVar("T")


class Duration(Model):
    """A length of time as the API writes it: a value in the largest exact unit
    (``Duration(value=1, unit=DurationUnit.MONTHS)`` = 30 days). Used in requests and responses.

    Attributes:
        value: The number of units, 0 to 4294967295; 0 means no duration.
        unit: Required when ``value`` > 0: seconds, minutes, hours, days, weeks, months (30 days)
            or years (365 days).
    """

    value: UInt = 0
    unit: Optional[DurationUnitT] = None


class Currency(Model):
    """A currency (a token or a chain's native coin) of the catalog."""

    #: The currency's id (``client.currencies.get(id)``).
    id: UInt = 0
    #: Its full name (e.g. "USD Coin").
    name: Str = ""
    #: Its symbol (e.g. "USDC").
    symbol: Str = ""
    #: Its number of decimals (6 for USDC).
    decimals: UInt = 0
    #: The token's contract address (or mint); ``""`` for a chain's native coin.
    address: Str = ""
    #: The chain's native coin, for a token; ``None`` for a native coin.
    main_currency_id: Optional[UInt] = Field(default=None, alias="mainCurrencyId")
    #: That native coin; ``None`` for a native coin.
    main_currency: Optional[Currency] = Field(default=None, alias="mainCurrency")
    #: True for a testnet currency.
    test: Bool = False

    def format_amount(self, min_units: str) -> str:
        """An amount of this currency in minimal units as a decimal string, exactly:
        :func:`qbitflow.format_amount` with this currency's ``decimals``
        (``usdc.format_amount("1500000") == "1.5"``).

        Raises:
            ValidationError: ``min_units`` is not an integer string (``-?[0-9]+``).
        """
        return format_amount(min_units, self.decimals)


class CustomerSummary(Model):
    """A customer as a payment, bill or refund names it (API reads only; never in webhooks)."""

    uuid: Str = ""
    name: Str = ""
    last_name: Optional[Str] = Field(default=None, alias="lastName")
    email: Str = ""
    reference: Optional[Str] = None
    #: True when the merchant deleted the customer (it still names its rows).
    deleted: Optional[Bool] = None


class RefundSummary(Model):
    """A transaction's refund, as its payment or bill shows it."""

    #: The refund (``refund@…``).
    uuid: Str = ""
    status: RefundStatusT = ""
    initiated_by: RefundInitiatorT = Field(default="", alias="initiatedBy")
    #: The share of what the customer paid it sends back, in percent.
    refund_percent: Float = Field(default=0.0, alias="refundPercent")
    #: What it sends back, in the currency's min units (a decimal string).
    amount_min_units: Str = Field(default="", alias="amountMinUnits")
    amount_usd: Float = Field(default=0.0, alias="amountUsd")
    created_at: Time = Field(default=ZERO_TIME, alias="createdAt")
    #: When it was approved or denied; ``None`` while pending.
    responded_at: Optional[Time] = Field(default=None, alias="respondedAt")


class Attempt(Model):
    """A failed attempt to pay (or to send a refund): never final."""

    status: AttemptStatusT = ""
    #: The error code (e.g. ``insufficient_funds``): what to do about it.
    code: Optional[Str] = None
    #: The reason, for the customer.
    message: Optional[Str] = None
    #: The attempt's transaction, if it was sent.
    tx_hash: Optional[Str] = Field(default=None, alias="txHash")
    at: Time = ZERO_TIME


class FeeLine(Model):
    """An amount a one-time payment's checkout adds to its product's price (a tax, shipping,
    QBitFlow's processing fee), shown to the customer line by line and paid with the price."""

    #: ``custom`` (the merchant's line) or ``processingFee`` (QBitFlow's fee, which the merchant
    #: has the customer pay).
    type: FeeLineTypeT = ""
    #: The line's name, as the checkout shows it (``Processing fee`` for the processing fee).
    label: Str = ""
    #: More about the line, as the merchant wrote it; ``None`` without one.
    description: Optional[Str] = None
    #: The line's amount in USD, a decimal string with at most 2 decimals (``"4.99"``).
    amount_usd: Str = Field(default="", alias="amountUsd")


class OrganizationFee(Model):
    """The organization's fee on a member's payment (a marketplace commission)."""

    #: The address receiving the fee.
    organization: Str = ""
    #: The fee, in percent, taken from what remains after QBitFlow's fee.
    fee_percent: Float = Field(default=0.0, alias="feePercent")


class ReferralFee(Model):
    """A referrer's share of QBitFlow's fee."""

    referrer: Str = ""
    #: The referrer's share of the platform fee, in percent (20 = 20 % of it).
    fee_percent: Float = Field(default=0.0, alias="feePercent")
    deadline: Time = ZERO_TIME


class BlockData(Model):
    """The block that included a transaction."""

    #: The block number (or slot), as a string.
    number: Str = ""
    #: The block's time, in unix seconds.
    timestamp: UInt = 0


class NetworkFees(Model):
    """A transaction's network fees, in the native coin's min units."""

    #: What the sender paid (a decimal string).
    amount: Str = ""
    #: The gas used.
    units_consumed: UInt = Field(default=0, alias="unitsConsumed")
    #: The part of ``amount`` that paid Base's L1 data fee; ``None`` on other networks.
    l1_fee: Optional[Str] = Field(default=None, alias="l1Fee")


class TxMetadata(Model):
    """A transaction's network fees and block."""

    network_fees: NetworkFees = Field(default_factory=NetworkFees, alias="networkFees")
    block_data: BlockData = Field(default_factory=BlockData, alias="blockData")
    #: The native coin's USD price at the transaction's time, when recorded.
    main_currency_price_usd: Optional[Float] = Field(default=None, alias="mainCurrencyPriceUsd")


class TxAmountsUsd(Model):
    """A payment's split in USD."""

    platform: Float = 0.0
    organization: Optional[Float] = None
    referral: Optional[Float] = None
    merchant: Float = 0.0
    #: The network fee the payer paid on top; ``None`` when not recorded.
    network_fee: Optional[Float] = Field(default=None, alias="networkFee")


class TxAmountsMinUnits(Model):
    """A payment's split in the token's min units (decimal strings)."""

    platform: Str = ""
    organization: Str = ""
    referral: Str = ""
    merchant: Str = ""
    network_fee: Optional[Str] = Field(default=None, alias="networkFee")


class TxAmounts(Model):
    """How a payment was split (QBitFlow, referrer, organization, merchant)."""

    usd: TxAmountsUsd = Field(default_factory=TxAmountsUsd)
    min_units: TxAmountsMinUnits = Field(default_factory=TxAmountsMinUnits, alias="minUnits")


class PaymentMetadata(Model):
    """A payment's (or a bill's) fees and split."""

    #: QBitFlow's fee on the payment, in percent (1.5 = 1.5 %).
    fee_percent: Float = Field(default=0.0, alias="feePercent")
    #: The organization's fee on its member's payment; ``None`` when none.
    organization_fee: Optional[OrganizationFee] = Field(default=None, alias="organizationFee")
    #: The referrer's share of QBitFlow's fee; ``None`` when none.
    referral_fee: Optional[ReferralFee] = Field(default=None, alias="referralFee")
    tx_metadata: TxMetadata = Field(default_factory=TxMetadata, alias="txMetadata")
    tx_amounts: TxAmounts = Field(default_factory=TxAmounts, alias="txAmounts")


class Page(Model, Generic[T]):
    """One page of a cursor-paginated list.

    Attributes:
        items: The page's rows.
        next_cursor: The cursor of the next page (pass it back as ``cursor=``, verbatim);
            ``None`` on the last page.
    """

    items: List[T] = Field(default_factory=list)
    next_cursor: Optional[Str] = Field(default=None, alias="nextCursor")

    @property
    def has_more(self) -> bool:
        """Whether another page follows."""
        return self.next_cursor is not None
