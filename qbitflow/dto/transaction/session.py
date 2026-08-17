"""Session-related data models."""

from typing import Any, Dict, List, Optional, Union
from pydantic import AliasChoices, Field, field_validator, model_validator

from qbitflow.dto.base_model import BaseModel
from qbitflow.utils.duration import Duration
from qbitflow.utils.helpers import validate_url
from .currency import Currency
from .status import TransactionStatus, TransactionType


class BaseSession(BaseModel):
    """
    Common fields shared by all session types (maps to TransactionData).

    Attributes:
        uuid: Session UUID.
        product_id: Optional product ID.
        product_name: Product or service name.
        description: Session description.
        price: Price in USD.
        success_url: URL to redirect on success.
        cancel_url: URL to redirect on cancellation.
        organization_id: Organization ID.
        organization_name: Organization name.
        fee_bps: Platform fee in basis points.
        organization_fee_bps: Optional organization fee in basis points.
        user_id: User ID of the session creator.
        test: Whether this is a test session.
        customer_uuid: Customer UUID.
        available_currencies: Accepted currencies.
    """

    uuid: str = Field(..., description="Session UUID")
    reference: Optional[str] = Field(
        default=None,
        description="Your own reference for the transaction, set when the session was created",
    )
    product_id: Optional[int] = Field(default=None, description="Product ID")
    product_reference: Optional[str] = Field(
        default=None, description="Your own product reference, if the product was selected by reference"
    )
    product_name: str = Field(..., description="Product name")
    description: str = Field(..., description="Description")
    price: float = Field(..., ge=0, description="Price in USD")
    success_url: Optional[str] = Field(default=None, description="Success redirect URL")
    cancel_url: Optional[str] = Field(default=None, description="Cancel redirect URL")
    organization_id: int = Field(..., description="Organization ID")
    organization_name: str = Field(..., description="Organization name")
    fee_bps: int = Field(..., description="Platform fee in basis points")
    organization_fee_bps: Optional[int] = Field(default=None, description="Organization fee in basis points")  # noqa: E501
    user_id: Optional[int] = Field(default=None, description="User ID")
    test: bool = Field(..., description="Test mode flag")
    customer_uuid: str = Field(
        ...,
        validation_alias=AliasChoices('customerUUID', 'customerUuid', 'customer_uuid'),
        description="Customer UUID",
    )
    customer_reference: Optional[str] = Field(
        default=None, description="Your own customer reference, if the customer was pre-filled by reference"
    )
    available_currencies: List[Currency] = Field(
        default_factory=list, description="Available currencies"
    )


class OneTimePaymentSession(BaseSession):
    """Session for a one-time payment (maps to TransactionData)."""


class SubscriptionSession(BaseSession):
    """
    Session for a recurring subscription (maps to SubscriptionData).

    Attributes:
        frequency: Billing frequency in seconds.
        trial_period: Optional trial period in seconds.
        min_periods: Optional minimum number of billing periods.
    """

    frequency: int = Field(..., gt=0, description="Billing frequency in seconds")
    trial_period: Optional[int] = Field(default=None, ge=0, description="Trial period in seconds")
    min_periods: Optional[int] = Field(default=None, gt=0, description="Minimum billing periods")


class PaygSubscriptionSession(BaseSession):
    """
    Session for a pay-as-you-go subscription (maps to CreatePaygSubscriptionData).

    Attributes:
        frequency: Billing frequency as a Duration object.
        free_credits: Free credits in USD granted to the customer.
    """

    frequency: Duration = Field(..., description="Billing frequency")
    free_credits: float = Field(default=0.0, ge=0, description="Free credits in USD")


AnySession = Union[PaygSubscriptionSession, SubscriptionSession, OneTimePaymentSession]


def _discriminate_session(data: Dict[str, Any]) -> AnySession:
    """Construct the correct session type from raw API response data.

    Discriminates by inspecting the ``frequency`` field:
    - dict  → PaygSubscriptionSession (Duration object)
    - int   → SubscriptionSession
    - absent → OneTimePaymentSession
    """
    freq = data.get("frequency")
    if freq is not None:
        if isinstance(freq, dict):
            return PaygSubscriptionSession.model_validate(data)
        return SubscriptionSession.model_validate(data)
    
    return OneTimePaymentSession.model_validate(data)


class CreatePaymentSessionDto(BaseModel):
    """
    DTO for creating a one-time payment session.

    Provide either product_id OR all of (product_name, description, price).
    """

    reference: Optional[str] = Field(
        default=None,
        description="Your own reference for the transaction (e.g. an order or invoice ID)",
    )
    product_id: Optional[int] = Field(default=None, description="Product ID")
    product_reference: Optional[str] = Field(
        default=None, description="Select an existing product by your own reference (alternative to product_id)"
    )
    product_name: Optional[str] = Field(default=None, description="Product name")
    description: Optional[str] = Field(default=None, description="Description")
    price: Optional[float] = Field(default=None, ge=0, description="Price in USD")
    success_url: Optional[str] = Field(default=None, description="Success redirect URL")
    cancel_url: Optional[str] = Field(default=None, description="Cancel redirect URL")
    customer_uuid: Optional[str] = Field(default=None, description="Customer UUID")
    customer_reference: Optional[str] = Field(
        default=None,
        description="Select an existing customer by your own reference (alternative to customer_uuid)",
    )

    @field_validator('success_url', 'cancel_url')
    @classmethod
    def validate_urls(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not validate_url(v):
            raise ValueError(f"Invalid URL format: {v}")
        return v

    def check(self) -> None:
        """Validate that required product fields are present."""
        if (
            self.product_id is None
            and self.product_reference is None
            and (
                self.product_name is None or
                self.description is None or
                self.price is None
            )
        ):
            raise ValueError(
                "Either product_id, product_reference, or "
                "(product_name, description, price) must be provided"
            )


class CreateSubscriptionSessionDto(CreatePaymentSessionDto):
    """
    DTO for creating a subscription session.

    Subscriptions must reference an existing product: provide either product_id
    or product_reference.
    """

    product_id: Optional[int] = Field(default=None, description="Product ID")
    frequency: Duration = Field(..., description="Billing frequency")
    trial_period: Optional[Duration] = Field(default=None, description="Trial period")
    min_periods: Optional[int] = Field(default=None, gt=0, description="Minimum billing periods")

    def check(self) -> None:
        """Validate that an existing product is referenced."""
        if self.product_id is None and self.product_reference is None:
            raise ValueError("Either product_id or product_reference must be provided")


class LinkResponse(BaseModel):
    """Response containing a payment/subscription link."""

    uuid: str = Field(..., description="Session UUID")
    link: str = Field(..., description="Payment/subscription link")
    expires_at: Optional[int] = Field(default=None, description="Expiration timestamp")


class StatusLinkResponse(BaseModel):
    """Response containing a status link."""

    message: str = Field(..., description="Status message")
    status_link: str = Field(..., description="Status check link (websocket)")


class SessionWebhookResponse(BaseModel):
    """
    Webhook payload sent when a session status changes.

    The ``session`` field is one of :class:`OneTimePaymentSession`,
    :class:`SubscriptionSession`, or :class:`PaygSubscriptionSession`,
    resolved automatically from the response payload.

    Example:
        >>> from fastapi import FastAPI
        >>> app = FastAPI()
        >>>
        >>> @app.post("/webhook")
        >>> def handle_webhook(event: SessionWebhookResponse):
        ...     if event.status.status == TransactionStatusValue.COMPLETED:
        ...         print(f"Payment completed: {event.session.uuid}")
        ...     return {"received": True}
    """

    uuid: str = Field(..., description="Session UUID")
    status: TransactionStatus = Field(..., description="Transaction status")
    session: AnySession = Field(..., description="Session details")
    tx_type: TransactionType = Field(..., description="Transaction type")
    management_page_link: str = Field(..., description="Link to the QBitFlow management page for this transaction")

    @model_validator(mode='before')
    @classmethod
    def _parse_session_type(cls, data: Any) -> Any:
        if isinstance(data, dict) and isinstance(data.get('session'), dict):
            data = dict(data)
            data['session'] = _discriminate_session(data['session'])
        return data
