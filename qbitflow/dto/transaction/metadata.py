"""
Typed payment metadata models.

These models describe the structured metadata attached to a payment or a
subscription-billing record: the fee breakdown, on-chain transaction metadata,
and the computed per-party amounts.

All decimal amounts expressed in the smallest currency units ("min units") are
returned as strings to preserve full precision, while USD amounts are floats.
"""

from datetime import datetime
from typing import Optional

from pydantic import Field

from qbitflow.dto.base_model import BaseModel


class OrganizationFee(BaseModel):
    """
    An additional fee kept by the organization, on top of the QBitFlow platform fee.

    Attributes:
        organization_id: ID of the organization receiving the fee.
        organization: On-chain address receiving the fee.
        fee_bps: Fee in basis points (1% = 100 bps).
    """

    organization_id: int = Field(..., description="ID of the organization receiving the fee")
    organization: str = Field(..., description="On-chain address receiving the fee")
    fee_bps: int = Field(..., description="Fee in basis points (1% = 100 bps)")


class ReferralFee(BaseModel):
    """
    An optional fee paid to a referrer.

    Attributes:
        referral_id: ID of the referral receiving the fee.
        referrer: On-chain address of the referrer receiving the fee.
        fee_bps: Fee in basis points (1% = 100 bps).
        deadline: Deadline until which the referral fee is valid.
    """

    referral_id: int = Field(..., description="ID of the referral receiving the fee")
    referrer: str = Field(..., description="On-chain address of the referrer")
    fee_bps: int = Field(..., description="Fee in basis points (1% = 100 bps)")
    deadline: datetime = Field(..., description="Deadline until which the referral fee is valid")


class NetworkFees(BaseModel):
    """
    On-chain network fees, expressed in the smallest native-currency units.

    Attributes:
        amount: Network fees as a decimal string, in native-currency min units.
        units_consumed: Units of gas (or equivalent) consumed by the transaction.
    """

    amount: str = Field(..., description="Network fees (decimal string, native min units)")
    units_consumed: int = Field(..., description="Units of gas consumed by the transaction")


class BlockData(BaseModel):
    """
    Identifies the block in which a transaction was included.

    Attributes:
        number: Block number (or slot) the transaction was included in.
        timestamp: Unix timestamp of the block.
    """

    number: str = Field(..., description="Block number or slot")
    timestamp: int = Field(..., description="Unix timestamp of the block")


class TxMetadata(BaseModel):
    """
    On-chain details parsed from a settled transaction.

    Attributes:
        network_fees: Network fees of the transaction.
        block_data: Block data (number and timestamp) of the transaction.
        main_currency_price_usd: Native-currency USD price at transaction time. Used for
            accounting on refunds or when the merchant pays the network fees.
    """

    network_fees: NetworkFees = Field(..., description="Network fees of the transaction")
    block_data: BlockData = Field(..., description="Block data of the transaction")
    main_currency_price_usd: Optional[float] = Field(
        default=None,
        alias="mainCurrencyPriceUSD",
        description="Native-currency USD price at transaction time",
    )


class TxAmountsUSD(BaseModel):
    """
    Per-party transaction amounts in USD.

    Attributes:
        platform: Platform (QBitFlow) fee amount in USD.
        organization: Organization fee amount in USD (optional).
        referral: Referral fee amount in USD (optional).
        merchant: Merchant net amount in USD.
    """

    platform: float = Field(..., description="Platform fee amount in USD")
    organization: Optional[float] = Field(
        default=None, description="Organization fee amount in USD"
    )  # noqa: E501
    referral: Optional[float] = Field(default=None, description="Referral fee amount in USD")
    merchant: float = Field(..., description="Merchant net amount in USD")


class TxAmountsMinUnits(BaseModel):
    """
    Per-party transaction amounts in the smallest currency units (decimal strings).

    Attributes:
        platform: Platform (QBitFlow) fee amount in min units.
        organization: Organization fee amount in min units.
        referral: Referral fee amount in min units.
        merchant: Merchant net amount in min units.
    """

    platform: str = Field(..., description="Platform fee amount (decimal string, min units)")
    organization: str = Field(
        ..., description="Organization fee amount (decimal string, min units)"
    )  # noqa: E501
    referral: str = Field(..., description="Referral fee amount (decimal string, min units)")
    merchant: str = Field(..., description="Merchant net amount (decimal string, min units)")


class TxAmountsFull(BaseModel):
    """
    Computed per-party transaction amounts, in both USD and min units.

    Attributes:
        usd: Per-party amounts in USD.
        min_units: Per-party amounts in the smallest currency units.
    """

    usd: TxAmountsUSD = Field(..., description="Per-party amounts in USD")
    min_units: TxAmountsMinUnits = Field(..., description="Per-party amounts in min units")


class PaymentMetadata(BaseModel):
    """
    Structured metadata attached to a payment or subscription-billing record.

    Combines the fee breakdown, on-chain transaction metadata, and the computed
    per-party amounts.

    Attributes:
        fee_bps: QBitFlow platform fee in basis points (1% = 100 bps), deducted from
            the amount paid; the merchant receives amount - platform fee - organization fee.
        organization_fee: Optional additional fee kept by the organization.
        referral_fee: Optional fee paid to a referrer.
        tx_metadata: On-chain metadata (populated after confirmation).
        tx_amounts: Computed fee/merchant amounts.
    """

    fee_bps: int = Field(..., description="Platform fee in basis points (1% = 100 bps)")
    organization_fee: Optional[OrganizationFee] = Field(
        default=None, description="Optional additional fee kept by the organization"
    )
    referral_fee: Optional[ReferralFee] = Field(
        default=None, description="Optional fee paid to a referrer"
    )
    tx_metadata: TxMetadata = Field(..., description="On-chain metadata (after confirmation)")
    tx_amounts: TxAmountsFull = Field(..., description="Computed fee/merchant amounts")
