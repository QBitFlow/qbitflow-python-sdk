"""
Subscription-related data models.

This module contains data models for subscription management.
"""

from datetime import datetime
import enum
from typing import Any, Dict, Optional
from pydantic import Field

from qbitflow.dto.base_model import BaseModel
from .currency import Currency


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
        default=None, description="Your own reference for the subscription, set when the session was created"
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
    customer_uuid: str = Field(..., description="Customer UUID")
    frequency: int = Field(..., gt=0, description="Billing frequency in seconds")
    allowance: float = Field(..., ge=0, description="Allowed charge amount in USD")
    subscription_status: SubscriptionStatus = Field(..., description="Subscription status")
    stopped: bool = Field(..., description="Whether subscription is stopped")
    last_billing_date: Optional[datetime] = Field(default=None, description="Last billing date")
    next_billing_date: datetime = Field(..., description="Next billing date")
    minimum_cancellation_date: Optional[datetime] = Field(default=None, description="Minimum cancellation date")


class PayAsYouGoSubscription(Subscription):
    """
    Represents a pay-as-you-go subscription.
    
    Pay-as-you-go subscriptions charge based on usage rather than a fixed amount.
    
    Attributes:
        units_current_period: Usage units in current billing period.
        max_spending_per_period: Maximum spending allowed per period.
        free_credits: Free credits available to the customer.
    
    Example:
        >>> payg = client.pay_as_you_go.get("payg-uuid")
        >>> print(f"Usage: {payg.units_current_period} units")
        >>> print(f"Max spending: ${payg.max_spending_per_period}")
        >>> print(f"Free credits: ${payg.free_credits}")
    """
    
    units_current_period: float = Field(..., ge=0, description="Usage units in current period")
    max_spending_per_period: float = Field(..., ge=0, description="Max spending per period")
    free_credits: float = Field(..., ge=0, description="Free credits available")



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
    amount_min_units: Optional[str] = Field(default=None, description="Amount in smallest token units")  # noqa: E501
    subscription_uuid: str = Field(..., description="Subscription UUID")
    transaction_hash: str = Field(..., description="Blockchain transaction hash")
    customer_uuid: str = Field(..., description="Customer UUID")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")


class SubscriptionStatusTransitionWebhook(BaseModel):
    """
    Represents a subscription status transition webhook event.
    
    This model contains information about a subscription status change,
    including the previous and current status along with the update timestamp.
    
    Attributes:
        subscription_uuid: UUID of the subscription that changed status.
        previous_status: The previous subscription status.
        current_status: The current subscription status.
        updated_at: Timestamp when the status transition occurred.
    
    Example:
        >>> webhook = SubscriptionStatusTransitionWebhook(**payload)
        >>> print(f"Subscription: {webhook.subscription_uuid}")
        >>> print(f"Status change: {webhook.previous_status} -> {webhook.current_status}")
        >>> print(f"Updated at: {webhook.updated_at}")
    """
    
    subscription_uuid: str = Field(..., alias="subscriptionUUID", description="Subscription UUID")
    subscription_reference: Optional[str] = Field(
        default=None,
        alias="subscriptionReference",
        description="Your own reference for the subscription, if one was set at creation",
    )
    previous_status: SubscriptionStatus = Field(..., alias="previousStatus", description="Previous subscription status")
    current_status: SubscriptionStatus = Field(..., alias="currentStatus", description="Current subscription status")
    updated_at: datetime = Field(..., alias="updatedAt", description="Status transition timestamp")

