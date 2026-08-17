"""Subscription transaction request handlers."""

from typing import List, Optional

from qbitflow.requests.base_request import BaseRequest, SuccessResponse
from qbitflow.dto.transaction.session import (
    CreateSubscriptionSessionDto, LinkResponse, SubscriptionSession, StatusLinkResponse,
)
from qbitflow.dto.transaction.subscription import Subscription, SubscriptionHistory
from qbitflow.requests.transaction.session import SessionRequests
from qbitflow.utils.duration import Duration
from qbitflow.exceptions import ValidationError


class SubscriptionRequests(BaseRequest):
    """Handler for recurring subscription requests."""

    BASE_ROUTE = "/transaction/subscription"
    SESSION_ROUTE = "/transaction/session-checkout"

    def __init__(self, api_key: str, timeout: int | None = None, max_retries: int | None = None):
        """Initialize the subscription request handler."""
        super().__init__(api_key, timeout=timeout, max_retries=max_retries)
        self._session = SessionRequests(api_key, timeout=timeout, max_retries=max_retries)

    def create_session(
        self,
        product_id: Optional[int] = None,
        frequency: Optional[Duration] = None,
        trial_period: Optional[Duration] = None,
        min_periods: Optional[int] = None,
        success_url: Optional[str] = None,
        cancel_url: Optional[str] = None,
        customer_uuid: Optional[str] = None,
        reference: Optional[str] = None,
        product_reference: Optional[str] = None,
        customer_reference: Optional[str] = None,
    ) -> LinkResponse:
        """
        Create a subscription session.

        Subscriptions must reference an existing product: provide either
        product_id or product_reference.

        Args:
            product_id: ID of the product to subscribe to.
            frequency: Billing frequency (e.g. Duration(value=1, unit="months")).
            trial_period: Optional trial period before the first charge.
            min_periods: Optional minimum number of billing periods.
            success_url: URL to redirect on success.
            cancel_url: URL to redirect on cancellation.
            customer_uuid: UUID of the customer.
            reference: Your own reference for the subscription (e.g. an order/invoice ID).
                Echoed back on the resulting subscription and in webhooks, and usable with
                ``get_by_reference``.
            product_reference: Select the product by your own reference (alternative to product_id).
            customer_reference: Select an existing customer by your own reference
                (alternative to customer_uuid). A new customer is created during checkout
                if none matches.

        Returns:
            Link response with the subscription URL.

        Example:
            >>> from qbitflow import Duration
            >>> response = client.subscriptions.create_session(
            ...     product_id=1,
            ...     frequency=Duration(value=1, unit="months"),
            ...     trial_period=Duration(value=7, unit="days"),
            ...     customer_uuid="customer-uuid"
            ... )
            >>> print(f"Subscription link: {response.link}")
        """
        if frequency is None:
            raise ValidationError("Frequency is required")

        if product_id is not None and product_id <= 0:
            raise ValidationError("Product ID must be positive")

        if min_periods is not None and min_periods <= 0:
            raise ValidationError("Minimum periods must be positive")

        if product_id is None and product_reference is None:
            raise ValidationError("Either product_id or product_reference must be provided")

        session = CreateSubscriptionSessionDto(
            product_id=product_id,
            frequency=frequency,
            trial_period=trial_period,
            min_periods=min_periods,
            success_url=success_url,
            cancel_url=cancel_url,
            customer_uuid=customer_uuid,
            reference=reference,
            product_reference=product_reference,
            customer_reference=customer_reference,
        )
        session.check()

        res = self._make_request(
            f"{self.SESSION_ROUTE}/new/subscription",
            "POST",
            session.model_dump(),
        )
        return LinkResponse(**res)

    def get_session(
        self, session_uuid: str, close_to_expire_error: Optional[bool] = False
    ) -> SubscriptionSession:
        """
        Get a subscription session by UUID.

        Args:
            session_uuid: UUID of the session.
            close_to_expire_error: Return an error if the session is close to expiry.

        Returns:
            Subscription session details.
        """
        from typing import cast
        return cast(SubscriptionSession, self._session.get(session_uuid, close_to_expire_error))

    def get(self, subscription_uuid: str) -> Subscription:
        """
        Get a subscription by UUID.

        Args:
            subscription_uuid: UUID of the subscription.

        Returns:
            Subscription details.

        Example:
            >>> sub = client.subscriptions.get("sub-uuid")
            >>> print(f"Status: {sub.subscription_status.value}")
            >>> print(f"Next billing: {sub.next_billing_date}")
        """
        if not subscription_uuid:
            raise ValidationError("Subscription UUID cannot be empty")

        res = self._make_request(f"{self.BASE_ROUTE}/{subscription_uuid}", "GET")
        return Subscription(**res)

    def get_by_reference(self, reference: str) -> Subscription:
        """
        Get a subscription by the reference you assigned when creating it.

        Lets you resolve a subscription from your own order/invoice ID without storing
        QBitFlow's UUID.

        Args:
            reference: Your own subscription reference.

        Returns:
            Subscription details.

        Example:
            >>> sub = client.subscriptions.get_by_reference("sub-1234")
            >>> print(sub.uuid, sub.subscription_status.value)
        """
        if not reference:
            raise ValidationError("Subscription reference cannot be empty")

        res = self._make_request(
            f"{self.BASE_ROUTE}/reference/subscription/{reference}", "GET"
        )
        return Subscription(**res)

    def get_payment_history(self, subscription_uuid: str) -> List[SubscriptionHistory]:
        """
        Get payment history for a subscription.

        Args:
            subscription_uuid: UUID of the subscription.

        Returns:
            List of historical billing records.

        Example:
            >>> history = client.subscriptions.get_payment_history("sub-uuid")
            >>> for record in history:
            ...     print(f"{record.created_at}: ${record.amount}")
        """
        if not subscription_uuid:
            raise ValidationError("Subscription UUID cannot be empty")

        res = self._make_request(f"{self.BASE_ROUTE}/history/{subscription_uuid}", "GET")
        return [SubscriptionHistory(**item) for item in res]

    def force_cancel(self, subscription_uuid: str) -> SuccessResponse:
        """
        Force cancel a subscription immediately.

        Bypasses the normal user-signed cancellation flow. Use only when
        absolutely necessary (e.g. suspicious activity, immediate refund request).

        Args:
            subscription_uuid: UUID of the subscription.

        Returns:
            Confirmation message.
        """
        if not subscription_uuid:
            raise ValidationError("Subscription UUID cannot be empty")

        res = self._make_request(
            f"{self.BASE_ROUTE}/processing/force-cancel/{subscription_uuid}",
            "GET",
        )
        return SuccessResponse(**res)

    def execute_test_billing_cycle(self, subscription_uuid: str) -> StatusLinkResponse:
        """
        Manually trigger a billing cycle (test mode only).

        In production, billing is executed automatically. Use this in test mode
        to simulate a billing cycle and verify webhook behaviour.

        Args:
            subscription_uuid: UUID of the subscription.

        Returns:
            Status link response.
        """
        if not subscription_uuid:
            raise ValidationError("Subscription UUID cannot be empty")

        res = self._make_request(
            f"{self.BASE_ROUTE}/processing/execute-billing/{subscription_uuid}",
            "GET",
        )
        return StatusLinkResponse(**res)
