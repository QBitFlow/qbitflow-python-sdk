"""Pay-as-you-go subscription request handlers."""

from typing import List, Optional

from qbitflow.requests.base_request import BaseRequest, SuccessResponse
from qbitflow.dto.transaction.session import (
    CreateSessionDto, CreateSubscriptionOptions, LinkResponse, Session, StatusLinkResponse
)
from qbitflow.dto.transaction.subscription import PayAsYouGoSubscription, SubscriptionHistory
from qbitflow.requests.transaction.session import SessionRequests
from qbitflow.utils.duration import Duration
from qbitflow.exceptions import ValidationError


class PayAsYouGoSubscriptionRequests(BaseRequest):
    """Handler for pay-as-you-go subscription requests."""
    
    BASE_ROUTE = "/transaction/subscription"
    
    def __init__(self, api_key: str, timeout: int | None = None, max_retries: int | None = None):
        """Initialize the PAYG subscription request handler."""
        super().__init__(api_key, timeout=timeout, max_retries=max_retries)
        self.session_requests = SessionRequests(api_key, timeout=timeout, max_retries=max_retries)

    def create_session(
        self,
        product_id: int,
        frequency: Duration,
        free_credits: Optional[float] = None,
        success_url: Optional[str] = None,
        cancel_url: Optional[str] = None,
        webhook_url: Optional[str] = None,
        customer_uuid: Optional[str] = None,
    ) -> LinkResponse:
        """
        Create a pay-as-you-go subscription session.
        
        PAYG subscriptions charge based on usage rather than a fixed amount.
        
        Args:
            product_id: ID of the product.
            frequency: Billing frequency.
            free_credits: Optional free credits to provide.
            success_url: URL to redirect on success.
            cancel_url: URL to redirect on cancellation.
            webhook_url: Webhook URL for events.
            customer_uuid: UUID of the customer.
        
        Returns:
            Link response with subscription URL.
        
        Example:
            >>> from qbitflow import Duration
            >>> response = client.pay_as_you_go.create_session(
            ...     product_id=1,
            ...     frequency=Duration(value=1, unit="months"),
            ...     free_credits=10.0,
            ...     customer_uuid="customer-uuid"
            ... )
        """
        if product_id <= 0:
            raise ValidationError("Product ID must be positive")
        
        if free_credits is not None and free_credits < 0:
            raise ValidationError("Free credits must be non-negative")
        
        
        options = CreateSubscriptionOptions(
            subscription_type="payAsYouGo",
            frequency=frequency,
            free_credits=free_credits,
        )
        
        session = CreateSessionDto(
            product_id=product_id,
            success_url=success_url,
            cancel_url=cancel_url,
            webhook_url=webhook_url,
            customer_uuid=customer_uuid,
            options=options
        )
        
        return self.session_requests.create(session)
    
    def get_session(self, session_uuid: str) -> Session:
        """Get a PAYG subscription session by UUID."""
        return self.session_requests.get(session_uuid)
    
    def get(self, subscription_uuid: str) -> PayAsYouGoSubscription:
        """Get a PAYG subscription by UUID."""
        if not subscription_uuid:
            raise ValidationError("Subscription UUID cannot be empty")
        
        res = self._make_request(f"{self.BASE_ROUTE}/{subscription_uuid}", "GET")
        return PayAsYouGoSubscription(**res)
    
    def get_payment_history(self, subscription_uuid: str) -> List[SubscriptionHistory]:
        """Get payment history for a PAYG subscription."""
        if not subscription_uuid:
            raise ValidationError("Subscription UUID cannot be empty")
        
        res = self._make_request(f"{self.BASE_ROUTE}/history/{subscription_uuid}", "GET")
        return [SubscriptionHistory(**item) for item in res]
    
    def force_cancel(self, subscription_uuid: str) -> SuccessResponse:
        """Force cancel a PAYG subscription immediately (use with caution)."""
        if not subscription_uuid:
            raise ValidationError("Subscription UUID cannot be empty")
        
        res = self._make_request(
            f"{self.BASE_ROUTE}/processing/force-cancel/{subscription_uuid}",
            "GET"
        )
        return SuccessResponse(**res)
    
    def execute_test_billing_cycle(self, subscription_uuid: str) -> StatusLinkResponse:
        """Execute a test billing cycle (test mode only)."""
        if not subscription_uuid:
            raise ValidationError("Subscription UUID cannot be empty")
        
        res = self._make_request(
            f"{self.BASE_ROUTE}/processing/execute-billing/{subscription_uuid}",
            "GET"
        )
        return StatusLinkResponse(**res)
    
    def increase_units_current_period(
        self,
        subscription_uuid: str,
        increase_amount: float
    ) -> PayAsYouGoSubscription:
        """
        Increase usage units for the current billing period.
        
        Args:
            subscription_uuid: UUID of the subscription.
            increase_amount: Amount to increase units by.
        
        Returns:
            Updated subscription details.
        """
        if not subscription_uuid:
            raise ValidationError("Subscription UUID cannot be empty")
        
        if increase_amount <= 0:
            raise ValidationError("Increase amount must be positive")
        
        res = self._make_request(
            f"{self.BASE_ROUTE}/payg/increase-units-current-period",
            "POST",
            data={
                "subscriptionUUID": subscription_uuid,
                "increaseByAmount": increase_amount
            }
        )
        return PayAsYouGoSubscription(**res)
