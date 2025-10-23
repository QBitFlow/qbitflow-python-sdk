
"""
Payment-related data models.

This module contains data models for one-time payments.
"""

from datetime import datetime
from typing import Optional
from pydantic import Field

from qbitflow.dto.base_model import BaseModel
from .currency import Currency


class Payment(BaseModel):
    """
    Represents a completed payment transaction.
    
    This model contains all the details of a processed payment,
    including the transaction details and cryptocurrency information.
    
    Attributes:
        uuid: Unique identifier for the payment.
        created_at: Timestamp when the payment was created.
        from_: Sender's cryptocurrency address.
        to: Recipient's cryptocurrency address.
        name: Product or service name.
        description: Payment description.
        amount: Payment amount in USD.
        currency_id: ID of the cryptocurrency used.
        currency: Cryptocurrency details.
        test: Whether this is a test mode payment.
        product_id: Optional product ID if payment was for a product.
        transaction_hash: Blockchain transaction hash.
        customer_uuid: UUID of the customer who made the payment.
    
    Example:
        >>> payment = client.one_time_payments.get("payment-uuid")
        >>> print(f"Amount: ${payment.amount} USD")
        >>> print(f"Paid with: {payment.currency.name}")
        >>> print(f"Tx Hash: {payment.transaction_hash}")
    """
    
    uuid: str = Field(..., description="Payment UUID")
    created_at: datetime = Field(..., description="Creation timestamp")
    from_: str = Field(..., alias="from", description="Sender's address")
    to: str = Field(..., description="Recipient's address")
    name: str = Field(..., description="Product/service name")
    description: str = Field(..., description="Payment description")
    amount: float = Field(..., ge=0, description="Amount in USD")
    currency_id: int = Field(..., description="Currency ID")
    currency: Currency = Field(..., description="Currency details")
    test: bool = Field(..., description="Test mode flag")
    product_id: Optional[int] = Field(default=None, description="Product ID")
    transaction_hash: str = Field(..., description="Blockchain transaction hash")
    customer_uuid: str = Field(..., description="Customer UUID")


class CombinedPayment(Payment):
    """
    Combined payment information from multiple sources.
    
    This model extends Payment to include information about the payment source,
    useful when fetching payments from multiple sources (one-time payments
    and subscription payments).
    
    Attributes:
        source: Payment source (e.g., "payment" or "subscription_history").
        subscription_uuid: UUID of the subscription if from subscription payment.
    
    Example:
        >>> combined = client.one_time_payments.get_all_combined(limit=10)
        >>> for payment in combined.items:
        ...     print(f"Source: {payment.source}")
        ...     if payment.subscription_uuid:
        ...         print(f"Subscription: {payment.subscription_uuid}")
    """
    
    source: str = Field(..., description="Payment source")
    subscription_uuid: Optional[str] = Field(default=None, description="Subscription UUID if applicable")
