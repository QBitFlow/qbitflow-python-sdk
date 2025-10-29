"""
Session-related data models.

This module contains data models for payment and subscription sessions.
"""

from typing import List, Literal, Optional
from pydantic import Field, field_validator

from qbitflow.dto.base_model import BaseModel
from qbitflow.utils.duration import Duration
from qbitflow.utils.helpers import validate_url
from .currency import Currency
from .status import TransactionStatus


class SubscriptionOptions(BaseModel):
    """
    Options for a subscription session.
    
    Attributes:
        frequency: Billing frequency in seconds.
        trial_period: Trial period duration in seconds.
        free_credits: Free credits amount in USD.
        min_periods: Minimum number of billing periods.
    """
    
    frequency: int = Field(..., gt=0, description="Billing frequency in seconds")
    trial_period: Optional[int] = Field(default=None, ge=0, description="Trial period in seconds")
    free_credits: Optional[float] = Field(default=None, ge=0, description="Free credits in USD")
    subscription_type: Literal["subscription", "payAsYouGo"] = Field(
        ..., description="Subscription type"
    )
    min_periods: Optional[int] = Field(default=None, gt=0, description="Minimum billing periods")


class Session(BaseModel):
    """
    Represents a payment or subscription session.
    
    Sessions are created when customers initiate a payment or subscription.
    They contain all the information needed to complete the transaction.
    
    Attributes:
        uuid: Unique identifier for the session.
        product_id: Optional product ID.
        product_name: Product or service name.
        description: Session description.
        price: Price in USD.
        organization_name: Name of your organization.
        success_url: URL to redirect on success.
        cancel_url: URL to redirect on cancellation.
        customer_uuid: UUID of the customer.
        options: Optional subscription options.
        available_currencies: List of currencies customer can use.
    
    Example:
        >>> session = client.one_time_payments.get_session("session-uuid")
        >>> print(f"Product: {session.product_name}")
        >>> print(f"Price: ${session.price}")
        >>> print(f"Available currencies: {len(session.available_currencies)}")
    """
    
    uuid: str = Field(..., description="Session UUID")
    product_id: Optional[int] = Field(default=None, description="Product ID")
    product_name: str = Field(..., description="Product name")
    description: str = Field(..., description="Description")
    price: float = Field(..., ge=0, description="Price in USD")
    organization_name: str = Field(..., description="Organization name")
    success_url: Optional[str] = Field(default=None, description="Success redirect URL")
    cancel_url: Optional[str] = Field(default=None, description="Cancel redirect URL")
    customer_uuid: str = Field(..., description="Customer UUID")
    options: Optional[SubscriptionOptions] = Field(default=None, description="Subscription options")
    available_currencies: List[Currency] = Field(default_factory=list, description="Available currencies")


class CreateSubscriptionOptions(BaseModel):
    """
    Options for creating a subscription session.
    
    Attributes:
        subscription_type: Type of subscription ("subscription" or "payAsYouGo").
        frequency: Billing frequency.
        trial_period: Optional trial period.
        free_credits: Optional free credits amount.
        min_periods: Optional minimum billing periods.
    """
    
    subscription_type: Literal["subscription", "payAsYouGo"] = Field(
        ..., description="Subscription type"
    )
    frequency: Duration = Field(..., description="Billing frequency")
    trial_period: Optional[Duration] = Field(default=None, description="Trial period")
    free_credits: Optional[float] = Field(default=None, ge=0, description="Free credits in USD")
    min_periods: Optional[int] = Field(default=None, gt=0, description="Minimum billing periods")


class CreateSessionDto(BaseModel):
    """
    Data transfer object for creating a payment or subscription session.
    
    You must provide either a product_id OR all of (product_name, description, price).
    
    Attributes:
        product_id: Optional product ID.
        product_name: Optional product name (required if no product_id).
        description: Optional description (required if no product_id).
        price: Optional price in USD (required if no product_id).
        success_url: Optional success redirect URL.
        cancel_url: Optional cancel redirect URL.
        webhook_url: Optional webhook URL for status updates.
        customer_uuid: Optional customer UUID.
        options: Optional subscription options.
    
    Example:
        >>> # Using product ID
        >>> session_dto = CreateSessionDto(
        ...     product_id=1,
        ...     customer_uuid="customer-uuid",
        ...     webhook_url="https://example.com/webhook"
        ... )
        >>> 
        >>> # Using product details
        >>> session_dto = CreateSessionDto(
        ...     product_name="Premium Plan",
        ...     description="Monthly premium subscription",
        ...     price=29.99,
        ...     customer_uuid="customer-uuid"
        ... )
    """
    
    product_id: Optional[int] = Field(default=None, description="Product ID")
    product_name: Optional[str] = Field(default=None, description="Product name")
    description: Optional[str] = Field(default=None, description="Description")
    price: Optional[float] = Field(default=None, ge=0, description="Price in USD")
    success_url: Optional[str] = Field(default=None, description="Success redirect URL")
    cancel_url: Optional[str] = Field(default=None, description="Cancel redirect URL")
    webhook_url: Optional[str] = Field(default=None, description="Webhook URL")
    customer_uuid: Optional[str] = Field(default=None, description="Customer UUID")
    options: Optional[CreateSubscriptionOptions] = Field(default=None, description="Subscription options")
    
    @field_validator('price')
    @classmethod
    def validate_price(cls, v: Optional[float]) -> Optional[float]:
        """Validate that price is non-negative if provided."""
        if v is not None and v < 0:
            raise ValueError("Price must be non-negative")
        return v
    
    @field_validator('success_url', 'cancel_url', 'webhook_url')
    @classmethod
    def validate_urls(cls, v: Optional[str]) -> Optional[str]:
        """Validate URL format if provided."""
        if v is not None and not validate_url(v):
            raise ValueError(f"Invalid URL format: {v}")
        return v
    
    def check(self) -> None:
        """
        Validate that required fields are provided.
        
        Raises:
            ValueError: If validation fails.
        """
        if self.product_id is None and (
            self.product_name is None or 
            self.description is None or 
            self.price is None
        ):
            raise ValueError(
                "Either product_id or (product_name, description, price) must be provided"
            )
        
        if self.price is not None and self.price < 0:
            raise ValueError("Price must be non-negative")


class LinkResponse(BaseModel):
    """
    Response containing a payment/subscription link.
    
    This is returned when creating a new session. Send the link to your
    customer to complete the payment or subscription.
    
    Attributes:
        uuid: Session UUID.
        link: Payment/subscription link for the customer.
        expires_at: Optional expiration timestamp.
    
    Example:
        >>> response = client.one_time_payments.create_session(product_id=1)
        >>> print(f"Send this link to customer: {response.link}")
        >>> print(f"Session ID: {response.uuid}")
    """
    
    uuid: str = Field(..., description="Session UUID")
    link: str = Field(..., description="Payment/subscription link")
    expires_at: Optional[int] = Field(default=None, description="Expiration timestamp")


class StatusResponse(BaseModel):
    """
    Response containing a status link.
    
    Attributes:
        message: Status message.
        status_link: Link to check transaction status.
    """
    
    message: str = Field(..., description="Status message")
    status_link: str = Field(..., description="Status check link")


class SessionWebhookResponse(BaseModel):
    """
    Webhook payload sent when a session status changes.
    
    This is the data structure you'll receive at your webhook URL
    when a transaction completes, fails, or changes status.
    
    Attributes:
        uuid: Session UUID.
        status: Current transaction status.
        session: Complete session details.
    
    Example:
        >>> from fastapi import FastAPI
        >>> app = FastAPI()
        >>> 
        >>> @app.post("/webhook")
        >>> def handle_webhook(event: SessionWebhookResponse):
        ...     if event.status.status == TransactionStatusValue.COMPLETED:
        ...         print(f"Payment completed: {event.session.uuid}")
        ...         # Process successful payment
        ...     return {"received": True}
    """
    
    uuid: str = Field(..., description="Session UUID")
    status: TransactionStatus = Field(..., description="Transaction status")
    session: Session = Field(..., description="Session details")
