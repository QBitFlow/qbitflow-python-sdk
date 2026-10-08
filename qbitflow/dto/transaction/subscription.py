"""
Subscription-related data models.

This module contains data models for subscription management.
"""

import enum
from datetime import datetime
from typing import Any, Optional, Union

from pydantic import Field, model_validator

from qbitflow.dto.base_model import BaseModel

from .currency import Currency
from .metadata import PaymentMetadata


class SubscriptionStatus(str, enum.Enum):
    """
    Enumeration of subscription status values.

    Defines the possible states a subscription can be in.

    Attributes:
        ACTIVE: Subscription is active and billing normally.
        CANCELLED: Subscription has been cancelled.
        PAST_DUE: Last payment attempt failed.
        LOW_ON_FUNDS: Allowance amount is low, next billing may fail.
        PENDING: Max amount reached, likely due to price fluctuations.
        TRIAL: Currently in trial period.
        TRIAL_EXPIRED: Trial ended, 7 days to upgrade before cancellation.
    """

    ACTIVE = "active"
    CANCELLED = "cancelled"
    PAST_DUE = "past_due"
    LOW_ON_FUNDS = "low_on_funds"
    PENDING = "pending"
    TRIAL = "trial"
    TRIAL_EXPIRED = "trial_expired"


class Subscription(BaseModel):
    """
    Represents a recurring subscription.

    Subscriptions allow customers to pay automatically at regular intervals.

    Attributes:
        uuid: Unique identifier for the subscription.
        created_at: Timestamp when subscription was created.
        updated_at: Timestamp when subscription was last updated.
        from_: Subscriber's cryptocurrency address.
        to: Recipient's cryptocurrency address.
        product_id: ID of the subscribed product.
        subscription_hash: Blockchain subscription hash.
        currency_id: ID of the cryptocurrency used.
        currency: Cryptocurrency details.
        test: Whether this is a test mode subscription.
        customer_uuid: UUID of the subscribing customer.
        frequency: Billing frequency in seconds.
        allowance: Allowed charge amount (periods * price) in USD.
        subscription_status: Current subscription status.
        stopped: Whether the subscription has been stopped.
        last_billing_date: Last successful billing date.
        next_billing_date: Next scheduled billing date.
        minimum_cancellation_date: Earliest date subscription can be cancelled.

    Example:
        >>> sub = client.subscriptions.get("subscription-uuid")
        >>> print(f"Status: {sub.subscription_status.value}")
        >>> print(f"Next billing: {sub.next_billing_date}")
        >>> print(f"Allowance: ${sub.allowance} USD")
    """

    uuid: str = Field(..., description="Subscription UUID")
    reference: Optional[str] = Field(
        default=None,
        description="Your own reference for the subscription, set when the session was created",
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    from_: str = Field(..., alias="from", description="Subscriber's address")
    to: str = Field(..., description="Recipient's address")
    product_id: int = Field(..., description="Product ID")
    subscription_hash: str = Field(..., description="Blockchain subscription hash")
    currency_id: int = Field(..., description="Currency ID")
    currency: Currency = Field(..., description="Currency details")
    test: bool = Field(..., description="Test mode flag")
    customer_uuid: Optional[str] = Field(
        default=None,
        description="Customer UUID; omitted when no customer is linked",
    )
    frequency: int = Field(..., gt=0, description="Billing frequency in seconds")
    allowance: str = Field(..., description="Remaining allowance in USD (decimal string)")
    subscription_status: SubscriptionStatus = Field(..., description="Subscription status")
    stopped: bool = Field(..., description="Whether subscription is stopped")
    last_billing_date: Optional[datetime] = Field(default=None, description="Last billing date")
    next_billing_date: datetime = Field(..., description="Next billing date")
    minimum_cancellation_date: Optional[datetime] = Field(
        default=None, description="Minimum cancellation date"
    )
    organization_id: Optional[int] = Field(
        default=None, description="Organization ID (returned only when authenticated)"
    )
    user_id: Optional[int] = Field(
        default=None, description="User ID (returned only when authenticated)"
    )


class SubscriptionHistory(BaseModel):
    """
    Represents a historical record of a subscription payment.

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
    amount_min_units: Optional[str] = Field(
        default=None, description="Amount in smallest token units"
    )  # noqa: E501
    subscription_uuid: str = Field(..., description="Subscription UUID")
    transaction_hash: str = Field(..., description="Blockchain transaction hash")
    customer_uuid: Optional[str] = Field(
        default=None,
        description="Customer UUID; omitted on the public history route (whenAuth)",
    )
    organization_id: Optional[int] = Field(
        default=None, description="Organization ID (returned only when authenticated)"
    )
    user_id: Optional[int] = Field(
        default=None, description="User ID (returned only when authenticated)"
    )
    metadata: Optional[PaymentMetadata] = Field(
        default=None, description="Typed payment metadata (fee breakdown, on-chain details)"
    )


class SubscriptionWebhookType(str, enum.Enum):
    """Which payload a subscription webhook carries."""

    STATUS_TRANSITION = "status_transition"
    BILLING = "billing"


class SubscriptionStatusTransition(BaseModel):
    """
    The ``data`` payload of a subscription webhook whose ``type`` is ``status_transition``.

    Attributes:
        previous_status: The previous subscription status.
        current_status: The current subscription status.
        updated_at: Timestamp when the status transition occurred.
    """

    previous_status: SubscriptionStatus = Field(
        ..., alias="previousStatus", description="Previous subscription status"
    )
    current_status: SubscriptionStatus = Field(
        ..., alias="currentStatus", description="Current subscription status"
    )
    updated_at: datetime = Field(..., alias="updatedAt", description="Status transition timestamp")


class SubscriptionWebhook(BaseModel):
    """
    The envelope QBitFlow POSTs to your subscription webhook URL.

    The subscription identity lives on the envelope and the event-specific payload in
    ``data``, discriminated by ``type``.

    Attributes:
        subscription_uuid: UUID of the subscription this delivery is about.
        subscription_reference: Your own reference, when one was set at creation.
        type: Which payload ``data`` carries.
        data: A :class:`SubscriptionStatusTransition` or a :class:`SubscriptionHistory`,
            resolved from ``type``.

    Example:
        >>> event = SubscriptionWebhook.model_validate_json(body)
        >>> if event.type is SubscriptionWebhookType.STATUS_TRANSITION:
        ...     print(event.data.previous_status, "->", event.data.current_status)
        ... else:
        ...     print("billed", event.data.amount, "for", event.subscription_uuid)
    """

    subscription_uuid: str = Field(..., alias="subscriptionUUID", description="Subscription UUID")
    subscription_reference: Optional[str] = Field(
        default=None,
        alias="subscriptionReference",
        description="Your own reference for the subscription, if one was set at creation",
    )
    type: SubscriptionWebhookType = Field(..., description="Which payload data carries")
    data: Union[SubscriptionStatusTransition, SubscriptionHistory] = Field(
        ..., description="Event-specific payload, resolved from type"
    )

    @model_validator(mode="before")
    @classmethod
    def _resolve_data_type(cls, values: Any) -> Any:
        """Build ``data`` as the class named by ``type`` rather than by union guessing.

        A plain Union would try SubscriptionStatusTransition first and could mis-resolve a
        billing payload, so the discriminator is honoured explicitly.
        """
        if not isinstance(values, dict):
            return values

        data = values.get("data")
        if not isinstance(data, dict):
            return values

        values = dict(values)
        if values.get("type") == SubscriptionWebhookType.BILLING.value:
            values["data"] = SubscriptionHistory.model_validate(data)
        elif values.get("type") == SubscriptionWebhookType.STATUS_TRANSITION.value:
            values["data"] = SubscriptionStatusTransition.model_validate(data)

        return values
