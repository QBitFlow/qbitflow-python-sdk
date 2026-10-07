"""
Payment-related data models.

This module contains data models for one-time payments.
"""

from typing import Optional

from pydantic import Field

from qbitflow.dto.base_model import GO_ZERO_TIME, Bool, Float, Int, ResponseModel, Str, Timestamp

from .currency import Currency
from .metadata import PaymentMetadata


class Payment(ResponseModel):
    """
    Represents a completed payment transaction.

    Attributes:
        uuid: Unique identifier for the payment (``pay@``-prefixed).
        reference: Your own reference for the payment, or ``None`` when none was set.
        created_at: Timestamp when the payment was created.
        from_: Sender's cryptocurrency address (JSON key ``from``).
        to: Recipient's cryptocurrency address.
        name: Product or service name.
        description: Payment description.
        amount: Payment amount in USD.
        amount_min_units: Amount in smallest token units (decimal string).
        currency_id: ID of the cryptocurrency used.
        currency: The cryptocurrency used.
        test: Whether this is a test mode payment.
        product_id: Product the payment was for (``0`` when none).
        transaction_hash: Blockchain transaction hash.
        customer_uuid: UUID of the paying customer, or ``None`` when no customer is linked.
        organization_id: Organization that received the payment.
        user_id: User that received the payment (``0`` for organization-level payments).
        metadata: Typed payment metadata (fee breakdown, on-chain details, amounts).

    Example:
        >>> payment = client.one_time_payments.get("pay@...")
        >>> print(f"{payment.amount} USD in {payment.currency.symbol}")
        >>> print(f"Tx Hash: {payment.transaction_hash}")
    """

    uuid: Str = ""
    reference: Optional[Str] = None
    created_at: Timestamp = GO_ZERO_TIME
    from_: Str = Field(default="", alias="from")
    to: Str = ""
    name: Str = ""
    description: Str = ""
    amount: Float = 0.0
    amount_min_units: Str = ""
    currency_id: Int = 0
    currency: Currency = Field(default_factory=Currency)
    test: Bool = False
    product_id: Int = 0
    transaction_hash: Str = ""
    customer_uuid: Optional[Str] = None
    organization_id: Int = 0
    user_id: Int = 0
    metadata: PaymentMetadata = Field(default_factory=PaymentMetadata)


class CombinedPaymentItem(ResponseModel):
    """
    A single item in a combined payment list (one-time payment or subscription cycle).

    Attributes:
        source: Origin of the payment: "payment" or "subscription_history".
        uuid: Payment UUID (prefixed).
        created_at: Creation timestamp.
        from_: Sender's cryptocurrency address (JSON key ``from``).
        to: Recipient's cryptocurrency address.
        name: Product or service name.
        description: Payment description.
        amount: Amount in USD.
        amount_min_units: Amount in smallest token units (decimal string).
        currency_id: Currency ID.
        currency: The cryptocurrency used.
        product_id: Product ID, or ``None``.
        transaction_hash: Blockchain transaction hash.
        customer_uuid: Customer UUID (the zero UUID when no customer is linked).
        subscription_uuid: Parent subscription for a subscription cycle, else ``None``.
        test: Test mode flag.
        metadata: Typed payment metadata, or ``None``.

    Example:
        >>> page = client.one_time_payments.get_all_combined(limit=10)
        >>> for item in page.items:
        ...     print(f"{item.source}: {item.uuid}")
        ...     if item.subscription_uuid:
        ...         print(f"  Subscription: {item.subscription_uuid}")
    """

    source: Str = ""
    uuid: Str = ""
    created_at: Timestamp = GO_ZERO_TIME
    from_: Str = Field(default="", alias="from")
    to: Str = ""
    name: Str = ""
    description: Str = ""
    amount: Float = 0.0
    amount_min_units: Str = ""
    currency_id: Int = 0
    currency: Currency = Field(default_factory=Currency)
    product_id: Optional[Int] = None
    transaction_hash: Str = ""
    customer_uuid: Str = ""
    subscription_uuid: Optional[Str] = None
    test: Bool = False
    metadata: Optional[PaymentMetadata] = None
