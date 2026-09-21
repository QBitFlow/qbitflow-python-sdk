"""Pay-as-you-go subscription request handlers."""

from typing import List

from qbitflow.dto.transaction.session import PaygSubscriptionSession, StatusLinkResponse
from qbitflow.dto.transaction.subscription import PayAsYouGoSubscription, SubscriptionHistory
from qbitflow.exceptions import ValidationError
from qbitflow.requests.base_request import BaseRequest, SuccessResponse
from qbitflow.requests.transaction.session import SessionRequests


class PayAsYouGoSubscriptionRequests(BaseRequest):
    """Handler for pay-as-you-go subscription requests.

    NOTE: creating PAYG sessions is currently disabled on the API; existing PAYG
    subscriptions can still be retrieved and managed via the methods below.
    """

    BASE_ROUTE = "/transaction/subscription"

    def __init__(self, api_key: str, timeout: int | None = None, max_retries: int | None = None):
        """Initialize the PAYG subscription request handler."""
        super().__init__(api_key, timeout=timeout, max_retries=max_retries)
        self.session_requests = SessionRequests(api_key, timeout=timeout, max_retries=max_retries)

    def get_session(self, session_uuid: str) -> PaygSubscriptionSession:
        """Get a PAYG subscription session by UUID."""
        from typing import cast

        return cast(PaygSubscriptionSession, self.session_requests.get(session_uuid))

    def get(self, subscription_uuid: str) -> PayAsYouGoSubscription:
        """Get a PAYG subscription by UUID."""
        if not subscription_uuid:
            raise ValidationError("Subscription UUID cannot be empty")

        res = self._make_request(f"{self.BASE_ROUTE}/{subscription_uuid}", "GET")
        return PayAsYouGoSubscription(**res)

    def get_by_reference(self, reference: str) -> PayAsYouGoSubscription:
        """
        Get a pay-as-you-go subscription by the reference you assigned when creating it.

        Args:
            reference: Your own subscription reference.

        Returns:
            PAYG subscription details.
        """
        if not reference:
            raise ValidationError("Subscription reference cannot be empty")

        res = self._make_request(f"{self.BASE_ROUTE}/reference/payAsYouGo/{reference}", "GET")
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
            f"{self.BASE_ROUTE}/processing/force-cancel/{subscription_uuid}", "GET"
        )
        return SuccessResponse(**res)

    def execute_test_billing_cycle(self, subscription_uuid: str) -> StatusLinkResponse:
        """Execute a test billing cycle (test mode only)."""
        if not subscription_uuid:
            raise ValidationError("Subscription UUID cannot be empty")

        res = self._make_request(
            f"{self.BASE_ROUTE}/processing/execute-billing/{subscription_uuid}", "GET"
        )
        return StatusLinkResponse(**res)

    def increase_units_current_period(
        self, subscription_uuid: str, increase_amount: float
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
            data={"subscriptionUUID": subscription_uuid, "increaseByAmount": increase_amount},
        )
        return PayAsYouGoSubscription(**res)
