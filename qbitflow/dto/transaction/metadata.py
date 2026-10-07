"""
Typed payment metadata models.

These models describe the structured metadata attached to a payment or a
subscription-billing record: the fee breakdown, on-chain transaction metadata,
and the computed per-party amounts.

All decimal amounts expressed in the smallest currency units ("min units") are
returned as strings to preserve full precision, while USD amounts are floats.
"""

from typing import Optional

from pydantic import Field

from qbitflow.dto.base_model import GO_ZERO_TIME, Float, Int, ResponseModel, Str, Timestamp


class OrganizationFee(ResponseModel):
    """
    An additional fee kept by the organization, on top of the QBitFlow platform fee.

    Attributes:
        organization_id: ID of the organization receiving the fee.
        organization: On-chain address receiving the fee.
        fee_bps: Fee in basis points (1% = 100 bps).
    """

    organization_id: Int = 0
    organization: Str = ""
    fee_bps: Int = 0


class ReferralFee(ResponseModel):
    """
    An optional fee paid to a referrer.

    Attributes:
        referral_id: ID of the referral receiving the fee.
        referrer: On-chain address of the referrer receiving the fee.
        fee_bps: Fee in basis points (1% = 100 bps).
        deadline: Deadline until which the referral fee is valid.
    """

    referral_id: Int = 0
    referrer: Str = ""
    fee_bps: Int = 0
    deadline: Timestamp = GO_ZERO_TIME


class NetworkFees(ResponseModel):
    """
    On-chain network fees, expressed in the smallest native-currency units.

    Attributes:
        amount: Network fees as a decimal string, in native-currency min units.
        units_consumed: Units of gas (or equivalent) consumed by the transaction.
    """

    amount: Str = ""
    units_consumed: Int = 0


class BlockData(ResponseModel):
    """
    Identifies the block in which a transaction was included.

    Attributes:
        number: Block number (or slot) the transaction was included in.
        timestamp: Unix timestamp of the block.
    """

    number: Str = ""
    timestamp: Int = 0


class TxMetadata(ResponseModel):
    """
    On-chain details parsed from a settled transaction.

    Attributes:
        network_fees: Network fees of the transaction.
        block_data: Block data (number and timestamp) of the transaction.
        main_currency_price_usd: Native-currency USD price at transaction time (``0.0`` when
            not recorded). Used for accounting on refunds or when the merchant pays the
            network fees.
    """

    network_fees: NetworkFees = Field(default_factory=NetworkFees)
    block_data: BlockData = Field(default_factory=BlockData)
    main_currency_price_usd: Float = Field(default=0.0, alias="mainCurrencyPriceUSD")


class TxAmountsUSD(ResponseModel):
    """
    Per-party transaction amounts in USD.

    Attributes:
        platform: Platform (QBitFlow) fee amount in USD.
        organization: Organization fee amount in USD (``0.0`` when there is none).
        referral: Referral fee amount in USD (``0.0`` when there is none).
        merchant: Merchant net amount in USD.
    """

    platform: Float = 0.0
    organization: Float = 0.0
    referral: Float = 0.0
    merchant: Float = 0.0


class TxAmountsMinUnits(ResponseModel):
    """
    Per-party transaction amounts in the smallest currency units (decimal strings).

    Attributes:
        platform: Platform (QBitFlow) fee amount in min units.
        organization: Organization fee amount in min units.
        referral: Referral fee amount in min units.
        merchant: Merchant net amount in min units.
    """

    platform: Str = ""
    organization: Str = ""
    referral: Str = ""
    merchant: Str = ""


class TxAmountsFull(ResponseModel):
    """
    Computed per-party transaction amounts, in both USD and min units.

    Attributes:
        usd: Per-party amounts in USD.
        min_units: Per-party amounts in the smallest currency units.
    """

    usd: TxAmountsUSD = Field(default_factory=TxAmountsUSD)
    min_units: TxAmountsMinUnits = Field(default_factory=TxAmountsMinUnits)


class PaymentMetadata(ResponseModel):
    """
    Structured metadata attached to a payment or subscription-billing record.

    Combines the fee breakdown, on-chain transaction metadata, and the computed
    per-party amounts.

    Attributes:
        fee_bps: QBitFlow platform fee in basis points (1% = 100 bps), deducted from
            the amount paid; the merchant receives amount - platform fee - organization fee.
        organization_fee: Additional fee kept by the organization, or ``None``.
        referral_fee: Fee paid to a referrer, or ``None``.
        tx_metadata: On-chain metadata (populated after confirmation).
        tx_amounts: Computed fee/merchant amounts.
    """

    fee_bps: Int = 0
    organization_fee: Optional[OrganizationFee] = None
    referral_fee: Optional[ReferralFee] = None
    tx_metadata: TxMetadata = Field(default_factory=TxMetadata)
    tx_amounts: TxAmountsFull = Field(default_factory=TxAmountsFull)
