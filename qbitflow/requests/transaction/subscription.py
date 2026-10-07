"""Subscription transaction request handlers."""

from typing import List, Optional

import httpx

from qbitflow.dto.transaction.session import (
    CreateSubscriptionSessionDto,
    LinkResponse,
    SubscriptionSession,
)
from qbitflow.dto.transaction.subscription import Subscription, SubscriptionHistory
from qbitflow.exceptions import ValidationError
from qbitflow.requests.base_request import BaseRequest, SuccessResponse
from qbitflow.requests.transaction.session import SessionRequests, build_session_dto
from qbitflow.utils.duration import Duration


class SubscriptionRequests(BaseRequest):
    """Handler for recurring subscription requests."""

    BASE_ROUTE = "/transaction/subscription"
    SESSION_ROUTE = "/transaction/session-checkout"

    def __init__(
        self,
        api_key: str,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
        headers: Optional[dict[str, str]] = None,
        base_url: Optional[str] = None,
        http_client: Optional[httpx.Client] = None,
    ):
        """Initialize the subscription request handler (see :class:`BaseRequest`)."""
        super().__init__(
            api_key,
            timeout=timeout,
            max_retries=max_retries,
            headers=headers,
            base_url=base_url,
            http_client=http_client,
        )
        # The nested handler shares this handler's scope (On-Behalf-Of), base URL and
        # connection pool, so a scoped copy impersonates on session retrieval too.
        self._session = SessionRequests(
            api_key,
            timeout=timeout,
            max_retries=max_retries,
            headers=headers,
            base_url=base_url,
            http_client=self._client,
        )

    def create_session(
        self,
        product_id: Optional[int] = None,
        frequency: Optional[Duration] = None,
        trial_period: Optional[Duration] = None,
        min_periods: Optional[int] = None,
        product_name: Optional[str] = None,
        description: Optional[str] = None,
        price: Optional[float] = None,
        success_url: Optional[str] = None,
        cancel_url: Optional[str] = None,
        customer_uuid: Optional[str] = None,
        reference: Optional[str] = None,
        product_reference: Optional[str] = None,
        customer_reference: Optional[str] = None,
    ) -> LinkResponse:
        """
        Create a subscription session.

        Provide either an existing product (``product_id`` or ``product_reference``) or an
        inline ghost product (``product_name`` + ``description`` + ``price``), exactly as
        for a one-time payment.

        Args:
            product_id: ID of the product to subscribe to.
            frequency: Billing frequency (e.g. Duration(value=1, unit="months")). Required;
                its value must be at least 1.
            trial_period: Optional trial period before the first charge (a value of 0 is
                accepted).
            min_periods: Optional minimum number of billing periods (0-4294967295; 0 means
                no minimum and is omitted).
            product_name: Name of an inline ghost product, when not referencing a stored one.
            description: Description of the inline ghost product.
            price: Price in USD of the inline ghost product.
            success_url: URL to redirect on success.
            cancel_url: URL to redirect on cancellation.
            customer_uuid: Bare UUID of an existing customer (``""`` = not provided).
            reference: Your own reference for the subscription (e.g. an order/invoice ID).
                Echoed back on the resulting subscription and in webhooks, and usable with
                ``get_by_reference``.
            product_reference: Select the product by your own reference (alternative to
                product_id).
            customer_reference: Select an existing customer by your own reference
                (alternative to customer_uuid). A new customer is created during checkout
                if none matches.

        Returns:
            Link response with the subscription URL.

        Raises:
            ValidationError: If ``frequency`` is missing, no product is selected, or any
                value breaks the API's rules; or if the API rejects the request (400).
                Never retried: a session is only ever created once.

        Example:
            >>> from qbitflow import Duration
            >>> response = client.subscriptions.create_session(
            ...     product_id=1,
            ...     frequency=Duration(value=1, unit="months"),
            ...     trial_period=Duration(value=7, unit="days"),
            ... )
            >>> print(f"Subscription link: {response.link}")

            >>> # Or with an inline ghost product, no stored product needed
            >>> response = client.subscriptions.create_session(
            ...     product_name="Pro plan",
            ...     description="Monthly Pro subscription",
            ...     price=29.0,
            ...     frequency=Duration(value=1, unit="months"),
            ... )
        """
        session = build_session_dto(
            CreateSubscriptionSessionDto,
            product_id=product_id,
            frequency=frequency,
            trial_period=trial_period,
            min_periods=min_periods,
            product_name=product_name,
            description=description,
            price=price,
            success_url=success_url,
            cancel_url=cancel_url,
            customer_uuid=customer_uuid,
            reference=reference,
            product_reference=product_reference,
            customer_reference=customer_reference,
        )

        return self._request_model(
            LinkResponse, f"{self.SESSION_ROUTE}/new/subscription", "POST", session.to_body()
        )

    def get_session(
        self, session_uuid: str, close_to_expire_error: Optional[bool] = None
    ) -> SubscriptionSession:
        """
        Get a subscription session by UUID.

        Args:
            session_uuid: UUID of the session.
            close_to_expire_error: Return an error if the session is close to expiry.
                ``None`` (default) leaves the API default (true) in place.

        Returns:
            Subscription session details.

        Raises:
            ValidationError: If ``session_uuid`` is empty, or the session is a one-time payment
                session (use ``client.one_time_payments.get_session`` for those).
        """
        session = self._session.get(session_uuid, close_to_expire_error)
        if not isinstance(session, SubscriptionSession):
            raise ValidationError(
                f"session {session_uuid} is not a subscription session (txType "
                f"{session.tx_type!s}); use client.one_time_payments.get_session() for it"
            )
        return session

    def get(self, subscription_uuid: str) -> Subscription:
        """
        Get a subscription by UUID.

        Args:
            subscription_uuid: UUID of the subscription (``sub@…``).

        Returns:
            Subscription details.

        Raises:
            ValidationError: If ``subscription_uuid`` is empty.
            NotFoundException: If the subscription is unknown.

        Example:
            >>> sub = client.subscriptions.get("sub-uuid")
            >>> print(f"Status: {sub.subscription_status}")
            >>> print(f"Next billing: {sub.next_billing_date}")
        """
        self._require_identifier(subscription_uuid, "subscription_uuid")

        return self._request_model(
            Subscription, f"{self.BASE_ROUTE}/{self._escape_path(subscription_uuid)}"
        )

    def get_by_reference(self, reference: str) -> Subscription:
        """
        Get a subscription by the reference you assigned when creating it.

        Lets you resolve a subscription from your own order/invoice ID without storing
        QBitFlow's UUID.

        Args:
            reference: Your own subscription reference.

        Returns:
            Subscription details.

        Raises:
            ValidationError: If ``reference`` is empty.
            NotFoundException: If no subscription with that reference is yours.

        Example:
            >>> sub = client.subscriptions.get_by_reference("sub-1234")
            >>> print(sub.uuid, sub.subscription_status)
        """
        self._require_identifier(reference, "reference")

        return self._request_model(
            Subscription,
            f"{self.BASE_ROUTE}/reference/subscription/{self._escape_path(reference)}",
        )

    def get_payment_history(self, subscription_uuid: str) -> List[SubscriptionHistory]:
        """
        Get the billing history for a subscription.

        The route is public, but the API honours the SDK's API key, so the entries carry the
        full record (``metadata`` included). An unknown subscription yields an empty list, not
        an error.

        Args:
            subscription_uuid: UUID of the subscription (``sub@…``).

        Returns:
            List of historical billing records.

        Raises:
            ValidationError: If ``subscription_uuid`` is empty.

        Example:
            >>> history = client.subscriptions.get_payment_history("sub-uuid")
            >>> for record in history:
            ...     print(f"{record.created_at}: ${record.amount}")
        """
        self._require_identifier(subscription_uuid, "subscription_uuid")

        return self._request_list(
            SubscriptionHistory, f"{self.BASE_ROUTE}/history/{self._escape_path(subscription_uuid)}"
        )

    def force_cancel(self, subscription_uuid: str) -> SuccessResponse:
        """
        Force cancel a subscription without the customer signing on-chain.

        Queues an on-chain cancellation; the subscription's status reflects it once the
        transaction settles. Never retried automatically (it is an action, not a read).

        Args:
            subscription_uuid: UUID of the subscription (``sub@…``).

        Returns:
            Confirmation message.

        Raises:
            ValidationError: If ``subscription_uuid`` is empty.
            NotFoundException: If the subscription is unknown or not yours.
        """
        self._require_identifier(subscription_uuid, "subscription_uuid")

        return self._request_model(
            SuccessResponse,
            f"{self.BASE_ROUTE}/processing/force-cancel/{self._escape_path(subscription_uuid)}",
            retriable=False,
        )

    def execute_test_billing_cycle(self, subscription_uuid: str) -> SuccessResponse:
        """
        Manually trigger a billing cycle (test subscriptions only).

        Live subscriptions are billed automatically; test subscriptions are not, so this
        runs one cycle on demand and records a new history entry. Never retried
        automatically (it is an action, not a read).

        Args:
            subscription_uuid: UUID of the subscription (``sub@…``).

        Returns:
            Confirmation message.

        Raises:
            ValidationError: If ``subscription_uuid`` is empty.
            ConflictError: If the subscription is not yet due for billing (409).
            NotFoundException: If the subscription is unknown or not yours.
        """
        self._require_identifier(subscription_uuid, "subscription_uuid")

        return self._request_model(
            SuccessResponse,
            f"{self.BASE_ROUTE}/processing/execute-billing/{self._escape_path(subscription_uuid)}",
            retriable=False,
        )
