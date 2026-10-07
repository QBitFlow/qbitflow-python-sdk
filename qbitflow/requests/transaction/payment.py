"""Payment transaction request handlers."""

from typing import Optional

import httpx

from qbitflow.dto.customer import Customer
from qbitflow.dto.transaction import payment as dto
from qbitflow.dto.transaction.session import (
    CreatePaymentSessionDto,
    LinkResponse,
    OneTimePaymentSession,
)
from qbitflow.exceptions import ValidationError
from qbitflow.requests.base_request import BaseRequest
from qbitflow.requests.transaction.session import SessionRequests, build_session_dto
from qbitflow.utils.cursor_data import CursorData, cursor_query_builder


class PaymentRequests(BaseRequest):
    """
    Handler for one-time payment requests.

    This class provides methods to create and manage one-time cryptocurrency payments.
    """

    BASE_ROUTE = "/transaction"
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
        """Initialize the payment request handler (see :class:`BaseRequest` for arguments)."""
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
        Create a new one-time payment session.

        Provide either product_id, product_reference, OR all of
        (product_name, description, price).

        Args:
            product_id: ID of an existing product.
            product_name: Product name (if not using product_id/product_reference).
            description: Product description (if not using product_id/product_reference).
            price: Price in USD (if not using product_id/product_reference).
            success_url: URL to redirect on success.
            cancel_url: URL to redirect on cancellation.
            customer_uuid: Bare UUID of an existing customer (``""`` = not provided).
            reference: Your own reference for the transaction (e.g. an order/invoice ID).
                Echoed back on the resulting payment and in webhooks, and usable with
                ``get_by_reference``.
            product_reference: Select an existing product by your own reference
                (alternative to product_id).
            customer_reference: Select an existing customer by your own reference
                (alternative to customer_uuid). A new customer is created during checkout
                if none matches.

        Returns:
            Link response with the payment URL to send to the customer.

        Raises:
            ValidationError: If the arguments break the API's rules (no product selected,
                a price that is not > 0, markup in the product text, a relative redirect URL,
                a customer_uuid that is not a bare UUID, …) or the API rejects the request
                (400). Never retried: a session is only ever created once.

        Example:
            >>> # Using a product ID
            >>> response = client.one_time_payments.create_session(
            ...     product_id=1,
            ...     customer_uuid="01997c89-d0e9-7c9a-9886-fe7709919695",
            ... )
            >>> print(f"Payment link: {response.link}")
            >>>
            >>> # Using your own references
            >>> response = client.one_time_payments.create_session(
            ...     reference="order-1234",
            ...     product_reference="PROD-PREMIUM",
            ...     customer_reference="user-42",
            ... )
        """
        session = build_session_dto(
            CreatePaymentSessionDto,
            product_id=product_id,
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
            LinkResponse, f"{self.SESSION_ROUTE}/new/payment", "POST", session.to_body()
        )

    def get_session(
        self, session_uuid: str, close_to_expire_error: Optional[bool] = None
    ) -> OneTimePaymentSession:
        """
        Get a payment session by UUID.

        Args:
            session_uuid: UUID of the session.
            close_to_expire_error: Return an error if the session is close to expiry.
                ``None`` (default) leaves the API default (true) in place.

        Returns:
            One-time payment session details.

        Raises:
            ValidationError: If ``session_uuid`` is empty, or the session is a subscription
                session (use ``client.subscriptions.get_session`` for those).

        Example:
            >>> session = client.one_time_payments.get_session("pay@...")
            >>> print(f"Product: {session.product_name}")
            >>> print(f"Price: ${session.price}")
        """
        session = self._session.get(session_uuid, close_to_expire_error)
        if not isinstance(session, OneTimePaymentSession):
            raise ValidationError(
                f"session {session_uuid} is a subscription session (txType "
                f"{session.tx_type!s}); use client.subscriptions.get_session() for it"
            )
        return session

    def get(self, payment_uuid: str) -> dto.Payment:
        """
        Get a completed payment by UUID.

        Args:
            payment_uuid: UUID of the payment (``pay@…`` prefixed or bare).

        Returns:
            Payment details.

        Raises:
            ValidationError: If ``payment_uuid`` is empty.
            NotFoundException: If the payment does not exist or is not yours.

        Example:
            >>> payment = client.one_time_payments.get("payment-uuid")
            >>> print(f"Amount: ${payment.amount}")
            >>> print(f"Tx Hash: {payment.transaction_hash}")
        """
        self._require_identifier(payment_uuid, "payment_uuid")

        return self._request_model(
            dto.Payment, f"{self.BASE_ROUTE}/payment/{self._escape_path(payment_uuid)}"
        )

    def get_by_reference(self, reference: str) -> dto.Payment:
        """
        Get a completed payment by the reference you assigned when creating it.

        Lets you resolve a payment from your own order/invoice ID without storing
        QBitFlow's UUID.

        Args:
            reference: Your own payment reference.

        Returns:
            Payment details.

        Raises:
            ValidationError: If ``reference`` is empty.
            NotFoundException: If no payment with that reference is yours.

        Example:
            >>> payment = client.one_time_payments.get_by_reference("order-1234")
            >>> print(payment.uuid, payment.amount)
        """
        self._require_identifier(reference, "reference")

        return self._request_model(
            dto.Payment, f"{self.BASE_ROUTE}/payment/reference/{self._escape_path(reference)}"
        )

    def get_all(
        self,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> CursorData[dto.Payment, str]:
        """
        Get all one-time payments with cursor pagination.

        Args:
            limit: Maximum number of results per page.
            cursor: Pagination cursor from a previous response.

        Returns:
            Paginated payment data.

        Example:
            >>> page = client.one_time_payments.get_all(limit=10)
            >>> for payment in page.items:
            ...     print(payment.uuid)
            >>> if page.has_more():
            ...     next_page = client.one_time_payments.get_all(
            ...         limit=10, cursor=page.next_cursor
            ...     )
        """
        params = cursor_query_builder(limit=limit, cursor=cursor)
        return self._request_model(
            CursorData[dto.Payment, str], f"{self.BASE_ROUTE}/payments", params=params
        )

    def get_all_combined(
        self,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> CursorData[dto.CombinedPaymentItem, str]:
        """
        Get all payments from both one-time and subscription sources.

        Args:
            limit: Maximum number of results per page.
            cursor: Pagination cursor from a previous response.

        Returns:
            Paginated combined payment data.

        Example:
            >>> page = client.one_time_payments.get_all_combined(limit=10)
            >>> for item in page.items:
            ...     print(f"{item.source}: {item.uuid}")
        """
        params = cursor_query_builder(limit=limit, cursor=cursor)
        return self._request_model(
            CursorData[dto.CombinedPaymentItem, str],
            f"{self.BASE_ROUTE}/payments/combined",
            params=params,
        )

    def get_customer_for_transaction(self, transaction_uuid: str) -> Customer:
        """
        Get the customer associated with a transaction (payment or subscription).

        Args:
            transaction_uuid: Prefixed id of the transaction (``pay@…`` or ``sub@…``).

        Returns:
            Customer information.

        Raises:
            ValidationError: If ``transaction_uuid`` is empty or malformed (400).
            NotFoundException: If the transaction is unknown or not yours.

        Example:
            >>> customer = client.one_time_payments.get_customer_for_transaction("pay@...")
            >>> print(f"Customer: {customer.name} ({customer.email})")
        """
        self._require_identifier(transaction_uuid, "transaction_uuid")

        return self._request_model(
            Customer, f"{self.BASE_ROUTE}/customer/{self._escape_path(transaction_uuid)}"
        )
