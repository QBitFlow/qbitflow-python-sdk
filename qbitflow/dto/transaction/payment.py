"""
Payment-related data models.

This module contains data models for one-time payments.
"""

from datetime import datetime
from typing import Optional

from pydantic import Field

from qbitflow.dto.base_model import BaseModel

from .currency import Currency
from .metadata import PaymentMetadata


class Payment(BaseModel):
    """
    Represents a completed payment transaction.

    Attributes:
        uuid: Unique identifier for the payment.
        created_at: Timestamp when the payment was created.
        from_: Sender's cryptocurrency address.
        to: Recipient's cryptocurrency address.
        name: Product or service name.
        description: Payment description.
        amount: Payment amount in USD.
        amount_min_units: Amount in smallest token units (decimal string).
        currency_id: ID of the cryptocurrency used.
        currency: Cryptocurrency details.
        test: Whether this is a test mode payment.
        product_id: Optional product ID if payment was for a product.
        transaction_hash: Blockchain transaction hash.
        customer_uuid: UUID of the customer who made the payment.
        metadata: Optional additional metadata.

    Example:
        >>> payment = client.one_time_payments.get("payment-uuid")
        >>> print(f"Amount: ${payment.amount} USD")
        >>> print(f"Paid with: {payment.currency.name}")
        >>> print(f"Tx Hash: {payment.transaction_hash}")
    """

    uuid: str = Field(..., description="Payment UUID")
    reference: Optional[str] = Field(
        default=None,
        description="Your own reference for the payment, set when the session was created",
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    from_: str = Field(..., alias="from", description="Sender's address")
    to: str = Field(..., description="Recipient's address")
    name: str = Field(..., description="Product/service name")
    description: str = Field(..., description="Payment description")
    amount: float = Field(..., ge=0, description="Amount in USD")
    amount_min_units: Optional[str] = Field(
        default=None, description="Amount in smallest token units"
    )  # noqa: E501
    currency_id: int = Field(..., description="Currency ID")
    currency: Currency = Field(..., description="Currency details")
    test: bool = Field(..., description="Test mode flag")
    product_id: Optional[int] = Field(default=None, description="Product ID")
    transaction_hash: str = Field(..., description="Blockchain transaction hash")
    customer_uuid: str = Field(..., description="Customer UUID")
    organization_id: Optional[int] = Field(
        default=None, description="Organization ID (returned only when authenticated)"
    )
    user_id: Optional[int] = Field(
        default=None, description="User ID (returned only when authenticated)"
    )
    metadata: Optional[PaymentMetadata] = Field(
        default=None, description="Typed payment metadata (fee breakdown, on-chain details)"
    )


class CombinedPaymentItem(BaseModel):
    """
    A single item in a combined payment list (one-time payment or subscription cycle).

    Attributes:
        source: Origin of the payment: "payment" or "subscription_history".
        uuid: Payment UUID.
        created_at: Creation timestamp.
        from_: Sender's cryptocurrency address.
        to: Recipient's cryptocurrency address.
        name: Product or service name.
        description: Payment description.
        amount: Amount in USD.
        amount_min_units: Amount in smallest token units (string).
        currency_id: Currency ID.
        currency: Currency details.
        product_id: Optional product ID.
        transaction_hash: Blockchain transaction hash.
        customer_uuid: Customer UUID.
        subscription_uuid: Subscription UUID if from a subscription cycle.
        test: Test mode flag.
        metadata: Optional additional metadata.

    Example:
        >>> page = client.one_time_payments.get_all_combined(limit=10)
        >>> for item in page.items:
        ...     print(f"{item.source}: {item.uuid}")
        ...     if item.subscription_uuid:
        ...         print(f"  Subscription: {item.subscription_uuid}")
    """

    source: str = Field(..., description="Payment source: 'payment' or 'subscription_history'")
    uuid: str = Field(..., description="Payment UUID")
    created_at: datetime = Field(..., description="Creation timestamp")
    from_: str = Field(..., alias="from", description="Sender's address")
    to: str = Field(..., description="Recipient's address")
    name: str = Field(..., description="Product/service name")
    description: str = Field(..., description="Payment description")
    amount: float = Field(..., ge=0, description="Amount in USD")
    amount_min_units: Optional[str] = Field(
        default=None, description="Amount in smallest token units"
    )  # noqa: E501
    currency_id: int = Field(..., description="Currency ID")
    currency: Optional[Currency] = Field(default=None, description="Currency details")
    product_id: Optional[int] = Field(default=None, description="Product ID")
    transaction_hash: str = Field(..., description="Blockchain transaction hash")
    customer_uuid: str = Field(..., description="Customer UUID")
    subscription_uuid: Optional[str] = Field(
        default=None, description="Subscription UUID if applicable"
    )  # noqa: E501
    test: bool = Field(..., description="Test mode flag")
    metadata: Optional[PaymentMetadata] = Field(
        default=None, description="Typed payment metadata (fee breakdown, on-chain details)"
    )
