"""
Subscription-related data models.

This module contains data models for subscription management.
"""

import enum
from typing import Any, Dict, Optional, Union

from pydantic import Field, model_validator

from qbitflow.dto.base_model import GO_ZERO_TIME, Bool, Float, Int, ResponseModel, Str, Timestamp

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


class Subscription(ResponseModel):
    """
    Represents a recurring subscription.

    Subscriptions allow customers to pay automatically at regular intervals.

    Attributes:
        uuid: Unique identifier for the subscription (``sub@``-prefixed).
        reference: Your own reference for the subscription, or ``None`` when none was set.
        created_at: Timestamp when subscription was created.
        updated_at: Timestamp when subscription was last updated.
        from_: Subscriber's cryptocurrency address (JSON key ``from``).
        to: Recipient's cryptocurrency address.
        product_id: ID of the subscribed product.
        subscription_hash: Blockchain subscription hash.
        currency_id: ID of the cryptocurrency used.
        currency: The cryptocurrency used.
        frequency: Billing frequency in seconds.
        allowance: Allowed charge amount in USD (decimal string).
        subscription_status: Current subscription status. A status this SDK does not know
            yet is kept as a plain string rather than rejected.
        stopped: Whether the subscription has been stopped.
        last_billing_date: Last billing date (:data:`~qbitflow.dto.base_model.GO_ZERO_TIME`
            when the subscription has never been billed).
        next_billing_date: Next scheduled billing date.
        minimum_cancellation_date: Earliest date the subscription can be cancelled, or
            ``None``.
        test: Whether this is a test mode subscription.
        organization_id: Organization that owns the subscription.
        user_id: User that owns the subscription (``0`` for organization-level ones).
        customer_uuid: UUID of the subscribing customer, or ``None``.

    Example:
        >>> sub = client.subscriptions.get("sub@...")
        >>> print(f"Status: {sub.subscription_status}")
        >>> print(f"Next billing: {sub.next_billing_date}")
        >>> print(f"Allowance: ${sub.allowance} in {sub.currency.symbol}")
    """

    uuid: Str = ""
    reference: Optional[Str] = None
    created_at: Timestamp = GO_ZERO_TIME
    updated_at: Timestamp = GO_ZERO_TIME
    from_: Str = Field(default="", alias="from")
    to: Str = ""
    product_id: Int = 0
    subscription_hash: Str = ""
    currency_id: Int = 0
    currency: Currency = Field(default_factory=Currency)
    frequency: Int = 0
    allowance: Str = ""
    subscription_status: Union[SubscriptionStatus, str] = Field(
        default="", union_mode="left_to_right"
    )
    stopped: Bool = False
    last_billing_date: Timestamp = GO_ZERO_TIME
    next_billing_date: Timestamp = GO_ZERO_TIME
    minimum_cancellation_date: Optional[Timestamp] = None
    test: Bool = False
    organization_id: Int = 0
    user_id: Int = 0
    customer_uuid: Optional[Str] = None


class SubscriptionHistory(ResponseModel):
    """
    Represents a historical record of a subscription payment (one billing).

    Attributes:
        uuid: Unique identifier for the billing record (``sub-hist@``-prefixed).
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
        product_id: Product the billing was for.
        subscription_uuid: Parent subscription (``sub@``-prefixed).
        transaction_hash: Blockchain transaction hash.
        customer_uuid: UUID of the paying customer, or ``None``.
        organization_id: Organization that received the payment.
        user_id: User that received the payment (``0`` for organization-level ones).
        metadata: Typed payment metadata (fee breakdown, on-chain details, amounts).

    Example:
        >>> history = client.subscriptions.get_payment_history("sub@...")
        >>> for record in history:
        ...     print(f"{record.created_at}: ${record.amount} ({record.transaction_hash})")
    """

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
    test: Bool = False
    product_id: Int = 0
    subscription_uuid: Str = Field(default="", alias="subscriptionUUID")
    transaction_hash: Str = ""
    customer_uuid: Optional[Str] = None
    organization_id: Int = 0
    user_id: Int = 0
    metadata: PaymentMetadata = Field(default_factory=PaymentMetadata)


class SubscriptionWebhookType(str, enum.Enum):
    """Which payload a subscription webhook carries."""

    STATUS_TRANSITION = "status_transition"
    BILLING = "billing"


class SubscriptionStatusTransition(ResponseModel):
    """
    The ``data`` payload of a subscription webhook whose ``type`` is ``status_transition``.

    Attributes:
        previous_status: The previous subscription status.
        current_status: The current subscription status.
        updated_at: Timestamp when the status transition occurred.

    Unknown status values are kept as plain strings rather than rejected, so a status the
    API adds later still reaches your handler.
    """

    previous_status: Union[SubscriptionStatus, str] = Field(default="", union_mode="left_to_right")
    current_status: Union[SubscriptionStatus, str] = Field(default="", union_mode="left_to_right")
    updated_at: Timestamp = GO_ZERO_TIME


class SubscriptionWebhook(ResponseModel):
    """
    The envelope QBitFlow POSTs to your subscription webhook URL.

    The subscription identity lives on the envelope and the event-specific payload in
    ``data``, discriminated by ``type``. Parse a delivery with
    :func:`qbitflow.parse_subscription_webhook` (after verifying its signature).

    Attributes:
        subscription_uuid: UUID of the subscription this delivery is about.
        subscription_reference: Your own reference (``""`` when none was set at creation).
        type: Which payload ``data`` carries. A type this SDK does not know yet is kept as
            a plain string, and ``data`` is then the raw dictionary.
        data: A :class:`SubscriptionStatusTransition` or a :class:`SubscriptionHistory`,
            resolved from ``type``; the raw ``dict`` for an unknown ``type``.

    Example:
        >>> event = parse_subscription_webhook(body)
        >>> if event.type == SubscriptionWebhookType.STATUS_TRANSITION:
        ...     print(event.data.previous_status, "->", event.data.current_status)
        ... elif event.type == SubscriptionWebhookType.BILLING:
        ...     print("billed", event.data.amount, "for", event.subscription_uuid)
    """

    subscription_uuid: Str = Field(default="", alias="subscriptionUUID")
    subscription_reference: Str = ""
    type: Union[SubscriptionWebhookType, str] = Field(default="", union_mode="left_to_right")
    # left_to_right with the raw dict first: the validator below has already turned a known
    # ``type``'s payload into its model instance (which the dict arm does not accept), so only
    # an unknown ``type`` keeps its raw dictionary.
    data: Union[Dict[str, Any], SubscriptionStatusTransition, SubscriptionHistory] = Field(
        default_factory=dict, union_mode="left_to_right"
    )

    @model_validator(mode="before")
    @classmethod
    def _resolve_data_type(cls, values: Any) -> Any:
        """Build ``data`` as the class named by ``type`` rather than by union guessing.

        A plain Union would try SubscriptionStatusTransition first and could mis-resolve a
        billing payload, so the discriminator is honoured explicitly. An unknown ``type``
        leaves ``data`` as the raw dictionary instead of failing the whole delivery.
        """
        if not isinstance(values, dict):
            return values

        data = values.get("data")
        if data is None:
            data = {}
        if not isinstance(data, dict):
            return values

        values = dict(values)
        if values.get("type") == SubscriptionWebhookType.BILLING.value:
            values["data"] = SubscriptionHistory.model_validate(data)
        elif values.get("type") == SubscriptionWebhookType.STATUS_TRANSITION.value:
            values["data"] = SubscriptionStatusTransition.model_validate(data)

        return values
