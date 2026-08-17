"""Payment transaction request handlers."""

from typing import Optional

from qbitflow.requests.base_request import BaseRequest
from qbitflow.dto.transaction.session import (
    CreatePaymentSessionDto, LinkResponse, OneTimePaymentSession,
)
from qbitflow.dto.transaction import payment as dto
from qbitflow.dto.customer import Customer
from qbitflow.requests.transaction.session import SessionRequests
from qbitflow.utils.cursor_data import CursorData, cursor_query_builder
from qbitflow.exceptions import ValidationError


class PaymentRequests(BaseRequest):
    """
    Handler for one-time payment requests.

    This class provides methods to create and manage one-time cryptocurrency payments.
    """

    BASE_ROUTE = "/transaction"
    SESSION_ROUTE = "/transaction/session-checkout"

    def __init__(self, api_key: str, timeout: int | None = None, max_retries: int | None = None):
        """Initialize the payment request handler."""
        super().__init__(api_key, timeout=timeout, max_retries=max_retries)
        self._session = SessionRequests(api_key, timeout=timeout, max_retries=max_retries)

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
            customer_uuid: UUID of the customer.
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

        Example:
            >>> # Using a product ID
            >>> response = client.one_time_payments.create_session(
            ...     product_id=1,
            ...     customer_uuid="customer-uuid"
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
        session = CreatePaymentSessionDto(
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
        session.check()

        res = self._make_request(
            f"{self.SESSION_ROUTE}/new/payment",
            "POST",
            session.model_dump(),
        )
        return LinkResponse(**res)

    def get_session(
        self, session_uuid: str, close_to_expire_error: Optional[bool] = False
    ) -> OneTimePaymentSession:
        """
        Get a payment session by UUID.

        Args:
            session_uuid: UUID of the session.
            close_to_expire_error: Return an error if the session is close to expiry.

        Returns:
            One-time payment session details.

        Example:
            >>> session = client.one_time_payments.get_session("session-uuid")
            >>> print(f"Product: {session.product_name}")
            >>> print(f"Price: ${session.price}")
        """
        from typing import cast
        return cast(OneTimePaymentSession, self._session.get(session_uuid, close_to_expire_error))

    def get(self, payment_uuid: str) -> dto.Payment:
        """
        Get a completed payment by UUID.

        Args:
            payment_uuid: UUID of the payment.

        Returns:
            Payment details.

        Example:
            >>> payment = client.one_time_payments.get("payment-uuid")
            >>> print(f"Amount: ${payment.amount}")
            >>> print(f"Tx Hash: {payment.transaction_hash}")
        """
        if not payment_uuid:
            raise ValidationError("Payment UUID cannot be empty")

        res = self._make_request(f"{self.BASE_ROUTE}/payment/{payment_uuid}", "GET")
        return dto.Payment(**res)

    def get_by_reference(self, reference: str) -> dto.Payment:
        """
        Get a completed payment by the reference you assigned when creating it.

        Lets you resolve a payment from your own order/invoice ID without storing
        QBitFlow's UUID.

        Args:
            reference: Your own payment reference.

        Returns:
            Payment details.

        Example:
            >>> payment = client.one_time_payments.get_by_reference("order-1234")
            >>> print(payment.uuid, payment.amount)
        """
        if not reference:
            raise ValidationError("Payment reference cannot be empty")

        res = self._make_request(f"{self.BASE_ROUTE}/payment/reference/{reference}", "GET")
        return dto.Payment(**res)

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
        res = self._make_request(f"{self.BASE_ROUTE}/payments", "GET", params=params)
        return CursorData[dto.Payment, str](**res)

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
        res = self._make_request(f"{self.BASE_ROUTE}/payments/combined", "GET", params=params)
        return CursorData[dto.CombinedPaymentItem, str](**res)

    def get_customer_for_transaction(self, transaction_uuid: str) -> Customer:
        """
        Get the customer associated with a transaction.

        Args:
            transaction_uuid: UUID of the transaction.

        Returns:
            Customer information.

        Example:
            >>> customer = client.one_time_payments.get_customer_for_transaction("tx-uuid")
            >>> print(f"Customer: {customer.name} ({customer.email})")
        """
        if not transaction_uuid:
            raise ValidationError("Transaction UUID cannot be empty")

        res = self._make_request(f"{self.BASE_ROUTE}/customer/{transaction_uuid}", "GET")
        return Customer(**res)
