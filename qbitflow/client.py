"""
QBitFlow SDK main client.

This module provides the main QBitFlow client class for interacting with the API.
"""

from typing import Optional

from qbitflow.requests.webhook import WebhookRequests

from .exceptions.exceptions import APIError, InvalidRequestError


from .requests.customer import CustomerRequests
from .requests.product import ProductRequests
from .requests.user import UserRequests
from .requests.api_key import ApiKeyRequests
from .requests.transaction.payment import PaymentRequests
from .requests.transaction.subscription import SubscriptionRequests
from .requests.transaction.payg import PayAsYouGoSubscriptionRequests
from .requests.transaction.status import TransactionStatusRequests
from .requests.base_request import BaseRequest

class QBitFlow:
    """
    Main client for interacting with the QBitFlow API.
    
    This class provides access to all QBitFlow API functionality through
    organized request handlers for different resource types.
    
    Attributes:
        api_key: API key used for authentication.
        customers: Handler for customer-related operations.
        products: Handler for product-related operations.
        users: Handler for user-related operations.
        api_keys: Handler for API key management.
        transaction_status: Handler for checking transaction statuses.
        one_time_payments: Handler for one-time payment operations.
        subscriptions: Handler for recurring subscription operations.
        pay_as_you_go: Handler for pay-as-you-go subscription operations.
    
    Example:
        >>> from qbitflow import QBitFlow
        >>> 
        >>> # Initialize the client
        >>> client = QBitFlow(api_key="your_api_key_here")
        >>> 
        >>> # Create a one-time payment
        >>> response = client.one_time_payments.create_session(
        ...     product_id=1,
        ...     customer_uuid="customer-uuid",
        ...     webhook_url="https://example.com/webhook"
        ... )
        >>> print(f"Payment link: {response.link}")
        >>> 
        >>> # Create a subscription
        >>> from qbitflow import Duration
        >>> response = client.subscriptions.create_session(
        ...     product_id=1,
        ...     frequency=Duration(value=1, unit="months"),
        ...     customer_uuid="customer-uuid"
        ... )
        >>> print(f"Subscription link: {response.link}")
        >>> 
        >>> # Check transaction status
        >>> from qbitflow.dto.transaction.status import TransactionType
        >>> status = client.transaction_status.get(
        ...     "transaction-uuid",
        ...     TransactionType.ONE_TIME_PAYMENT
        ... )
        >>> print(f"Status: {status.status.value}")
    """
    
    def __init__(
        self,
        api_key: str,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None
    ):
        """
        Initialize the QBitFlow client.
        
        Args:
            api_key: Your QBitFlow API key. Get this from your dashboard.
            timeout: Optional request timeout in seconds (default: 30).
            max_retries: Optional maximum retry attempts (default: 3).
        
        Raises:
            ValueError: If api_key is empty or None.
        
        Example:
            >>> # Basic initialization
            >>> client = QBitFlow(api_key="your_api_key_here")
            >>> 
            >>> # With custom timeout and retries
            >>> client = QBitFlow(
            ...     api_key="your_api_key_here",
            ...     timeout=60,
            ...     max_retries=5
            ... )
        """
        if not api_key:
            raise ValueError("API key is required")
        
        self.api_key = api_key
        self._timeout = timeout
        self._max_retries = max_retries
        
        # Initialize request handlers
        self.customers = CustomerRequests(api_key, timeout, max_retries)
        self.products = ProductRequests(api_key, timeout, max_retries)
        self.users = UserRequests(api_key, timeout, max_retries)
        self.api_keys = ApiKeyRequests(api_key, timeout, max_retries)
        
        # Transaction-related handlers
        self.transaction_status = TransactionStatusRequests(api_key, timeout, max_retries)
        self.one_time_payments = PaymentRequests(api_key, timeout, max_retries)
        self.subscriptions = SubscriptionRequests(api_key, timeout, max_retries)
        self.pay_as_you_go = PayAsYouGoSubscriptionRequests(api_key, timeout, max_retries)

        self.webhooks = WebhookRequests(api_key, timeout, max_retries)
    
    def __repr__(self) -> str:
        """Return a string representation of the client."""
        return f"QBitFlow(api_key='***{self.api_key[-4:]}')"
    
