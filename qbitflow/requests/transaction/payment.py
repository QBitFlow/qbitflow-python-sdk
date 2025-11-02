"""Payment transaction request handlers."""

from typing import Optional

from qbitflow.requests.base_request import BaseRequest
from qbitflow.dto.transaction.session import CreateSessionDto, LinkResponse, Session
from qbitflow.dto.transaction import payment as dto
from qbitflow.requests.transaction.session import SessionRequests
from qbitflow.utils.cursor_data import CursorData, cursor_query_builder
from qbitflow.exceptions import ValidationError


class PaymentRequests(BaseRequest):
    """
    Handler for one-time payment requests.
    
    This class provides methods to create and manage one-time cryptocurrency payments.
    """
    
    BASE_ROUTE = "/transaction"
    
    def __init__(self, api_key: str, timeout: int | None = None, max_retries: int | None = None):
        """Initialize the payment request handler."""
        super().__init__(api_key, timeout=timeout, max_retries=max_retries)
        self.session_requests = SessionRequests(api_key, timeout=timeout, max_retries=max_retries)
    
    def create_session(
        self,
        product_id: Optional[int] = None,
        product_name: Optional[str] = None,
        description: Optional[str] = None,
        price: Optional[float] = None,
        success_url: Optional[str] = None,
        cancel_url: Optional[str] = None,
        webhook_url: Optional[str] = None,
        customer_uuid: Optional[str] = None
    ) -> LinkResponse:
        """
        Create a new one-time payment session.
        
        You must provide either product_id OR all of (product_name, description, price).
        
        Args:
            product_id: ID of the product to purchase.
            product_name: Name of the product (if not using product_id).
            description: Product description (if not using product_id).
            price: Price in USD (if not using product_id).
            success_url: URL to redirect on success (supports {{UUID}}, {{TRANSACTION_TYPE}} placeholders).
            cancel_url: URL to redirect on cancellation.
            webhook_url: Webhook URL for status updates.
            customer_uuid: UUID of the customer making the payment.
        
        Returns:
            Link response with payment URL for the customer.
        
        Example:
            >>> # Using product ID
            >>> response = client.one_time_payments.create_session(
            ...     product_id=1,
            ...     customer_uuid="customer-uuid",
            ...     webhook_url="https://example.com/webhook"
            ... )
            >>> print(f"Payment link: {response.link}")
            >>> 
            >>> # Using product details
            >>> response = client.one_time_payments.create_session(
            ...     product_name="Premium Plan",
            ...     description="One-time access",
            ...     price=99.99,
            ...     customer_uuid="customer-uuid"
            ... )
        """
        session = CreateSessionDto(
            product_id=product_id,
            product_name=product_name,
            description=description,
            price=price,
            success_url=success_url,
            cancel_url=cancel_url,
            webhook_url=webhook_url,
            customer_uuid=customer_uuid
        )
        
        session.check()
        return self.session_requests.create(session)
    
    def get_session(self, session_uuid: str) -> Session:
        """
        Get a payment session by UUID.
        
        Args:
            session_uuid: UUID of the session.
        
        Returns:
            Session details.
        
        Example:
            >>> session = client.one_time_payments.get_session("session-uuid")
            >>> print(f"Product: {session.product_name}")
            >>> print(f"Price: ${session.price}")
        """
        return self.session_requests.get(session_uuid)
    
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
        
        endpoint = f"{self.BASE_ROUTE}/payment/{payment_uuid}"
        res = self._make_request(endpoint, "GET")
        return dto.Payment(**res)
    
    def get_all(
        self,
        limit: Optional[int] = None,
        cursor: Optional[str] = None
    ) -> CursorData[dto.Payment, str]:
        """
        Get all one-time payments with pagination.
        
        Args:
            limit: Maximum number of results per page.
            cursor: Pagination cursor from previous response.
        
        Returns:
            Paginated payment data.
        
        Example:
            >>> # Get first page
            >>> page = client.one_time_payments.get_all(limit=10)
            >>> for payment in page.items:
            ...     print(f"Payment: {payment.uuid}")
            >>> 
            >>> # Get next page
            >>> if page.has_more():
            ...     next_page = client.one_time_payments.get_all(
            ...         limit=10,
            ...         cursor=page.next_cursor
            ...     )
        """
        params = cursor_query_builder(limit=limit, cursor=cursor)
        
        res = self._make_request(f"{self.BASE_ROUTE}/payments", "GET", params=params)
        return CursorData[dto.Payment, str](**res)
    
    def get_all_combined(
        self,
        limit: Optional[int] = None,
        cursor: Optional[str] = None
    ) -> CursorData[dto.CombinedPayment, str]:
        """
        Get all payments from both one-time and subscription sources.
        
        Args:
            limit: Maximum number of results per page.
            cursor: Pagination cursor from previous response.
        
        Returns:
            Paginated combined payment data.
        
        Example:
            >>> page = client.one_time_payments.get_all_combined(limit=10)
            >>> for payment in page.items:
            ...     print(f"Payment: {payment.uuid} (source: {payment.source})")
        """
        params = cursor_query_builder(limit=limit, cursor=cursor)
        
        res = self._make_request(f"{self.BASE_ROUTE}/payments/combined", "GET", params=params)
        return CursorData[dto.CombinedPayment, str](**res)
