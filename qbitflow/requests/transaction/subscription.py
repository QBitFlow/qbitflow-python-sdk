"""Subscription transaction request handlers."""

from typing import List, Optional

from qbitflow.requests.base_request import BaseRequest, SuccessResponse
from qbitflow.dto.transaction.session import (
    CreateSessionDto, LinkResponse, CreateSubscriptionOptions, Session, StatusResponse
)
from qbitflow.dto.transaction.subscription import Subscription
from qbitflow.requests.transaction.session import SessionRequests
from qbitflow.utils.duration import Duration
from qbitflow.exceptions import ValidationError


class SubscriptionRequests(BaseRequest):
    """Handler for recurring subscription requests."""
    
    BASE_ROUTE = "/transaction/subscription"
    
    def __init__(self, api_key: str, timeout: int | None = None, max_retries: int | None = None):
        """Initialize the subscription request handler."""
        super().__init__(api_key, timeout=timeout, max_retries=max_retries)
        self.session_requests = SessionRequests(api_key, timeout=timeout, max_retries=max_retries)
    
    def create_session(
        self,
        product_id: int,
        frequency: Duration,
        trial_period: Optional[Duration] = None,
        min_periods: Optional[int] = None,
        success_url: Optional[str] = None,
        cancel_url: Optional[str] = None,
        webhook_url: Optional[str] = None,
        customer_uuid: Optional[str] = None,
    ) -> LinkResponse:
        """
        Create a subscription session.
        
        Args:
            product_id: ID of the product to subscribe to.
            frequency: Billing frequency (e.g., Duration(value=1, unit="months")).
            trial_period: Optional trial period duration.
            min_periods: Optional minimum billing periods.
            success_url: URL to redirect on success.
            cancel_url: URL to redirect on cancellation.
            webhook_url: Webhook URL for subscription events.
            customer_uuid: UUID of the customer.
        
        Returns:
            Link response with subscription URL.
        
        Example:
            >>> from qbitflow import Duration
            >>> response = client.subscriptions.create_session(
            ...     product_id=1,
            ...     frequency=Duration(value=1, unit="months"),
            ...     trial_period=Duration(value=7, unit="days"),
            ...     customer_uuid="customer-uuid"
            ... )
        """
        if product_id <= 0:
            raise ValidationError("Product ID must be positive")
        
        if min_periods is not None and min_periods <= 0:
            raise ValidationError("Minimum periods must be positive")
        
        options = CreateSubscriptionOptions(
            subscription_type="subscription",
            frequency=frequency,
            trial_period=trial_period,
            min_periods=min_periods
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
        """Get a subscription session by UUID."""
        return self.session_requests.get(session_uuid)
    
    def get(self, subscription_uuid: str) -> Subscription:
        """Get a subscription by UUID."""
        if not subscription_uuid:
            raise ValidationError("Subscription UUID cannot be empty")
        
        res = self._make_request(f"{self.BASE_ROUTE}/{subscription_uuid}", "GET")
        return Subscription(**res)
    
    def get_payment_history(self, subscription_uuid: str) -> List[Subscription]:
        """Get payment history for a subscription."""
        if not subscription_uuid:
            raise ValidationError("Subscription UUID cannot be empty")
        
        res = self._make_request(f"{self.BASE_ROUTE}/history/{subscription_uuid}", "GET")
        return [Subscription(**item) for item in res]
    
    def force_cancel(self, subscription_uuid: str) -> SuccessResponse:
        """
        Force cancel a subscription immediately.
        
        Warning: Use only when absolutely necessary.
        """
        if not subscription_uuid:
            raise ValidationError("Subscription UUID cannot be empty")
        
        res = self._make_request(
            f"{self.BASE_ROUTE}/processing/force-cancel/{subscription_uuid}",
            "GET"
        )
        return SuccessResponse(**res)
    
    def execute_test_billing_cycle(self, subscription_uuid: str) -> StatusResponse:
        """
        Execute a test billing cycle (test mode only).
        
        This simulates a billing cycle for testing purposes.
        Only works in test mode.
        """
        if not subscription_uuid:
            raise ValidationError("Subscription UUID cannot be empty")
        
        res = self._make_request(
            f"{self.BASE_ROUTE}/processing/execute-billing/{subscription_uuid}",
            "GET"
        )
        return StatusResponse(**res)
