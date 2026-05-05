"""Accounting export data models."""

from datetime import datetime
from pydantic import Field

from qbitflow.dto.base_model import BaseModel


class AccountingEvent(BaseModel):
    """
    Represents a single accounting event (payment, subscription cycle, or refund).

    Decimal values (gross_amount, fees, net_amount, etc.) are returned as strings
    to preserve full precision.

    Example:
        >>> events = client.accounting.export("2025-01-01", "2025-12-31", "json")
        >>> for event in events:
        ...     print(f"{event.payment_id} | {event.type} | ${event.gross_amount_usd}")
    """

    payment_id: str = Field(..., description="Payment identifier")
    type: str = Field(..., description="Event type: one_time | subscription | refund")
    tx_time_utc: datetime = Field(..., description="Transaction time in UTC")
    receipt_url: str = Field(..., description="Receipt URL")
    related_payment_id: str = Field(..., description="For refunds: original payment ID")

    product_id: int = Field(..., description="Product ID")
    product_name: str = Field(..., description="Product name")
    product_description: str = Field(..., description="Product description")
    customer_uuid: str = Field(..., description="Customer UUID")

    chain: str = Field(..., description="Blockchain network")
    block_number_or_slot: str = Field(..., description="Block number or slot")
    tx_hash: str = Field(..., description="Transaction hash")
    from_address: str = Field(..., description="Sender address")
    to_address: str = Field(..., description="Recipient address")

    token_symbol: str = Field(..., description="Token symbol")
    currency_decimals: int = Field(..., description="Token decimal places")
    token_contract_or_mint: str = Field(..., description="Token contract or mint address")

    explorer_url: str = Field(..., description="Blockchain explorer URL")

    gross_amount: str = Field(..., description="Gross amount (decimal string)")
    gross_amount_usd: float = Field(..., description="Gross amount in USD")

    platform_fee_percent: float = Field(..., description="Platform fee percentage")
    platform_fee_usd: float = Field(..., description="Platform fee in USD")
    platform_fee: str = Field(..., description="Platform fee (decimal string)")

    organization_fee_percent: float = Field(..., description="Organization fee percentage")
    organization_fee_usd: float = Field(..., description="Organization fee in USD")
    organization_fee: str = Field(..., description="Organization fee (decimal string)")

    network_fees_usd: float = Field(..., description="Network fees in USD (paid by merchant)")
    network_fees: str = Field(..., description="Network fees (decimal string)")

    net_amount_usd: float = Field(..., description="Net amount received in USD")
    net_amount: str = Field(..., description="Net amount received (decimal string)")
