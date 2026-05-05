"""
QBitFlow SDK main client.

This module provides the main QBitFlow client class for interacting with the API.
"""

from typing import Optional

from qbitflow.requests.webhook import WebhookRequests

from .requests.customer import CustomerRequests
from .requests.product import ProductRequests
from .requests.user import UserRequests
from .requests.api_key import ApiKeyRequests
from .requests.refund import RefundRequests
from .requests.accounting import AccountingRequests
from .requests.claim import ClaimRequests
from .requests.transaction.payment import PaymentRequests
from .requests.transaction.subscription import SubscriptionRequests
# from .requests.transaction.payg import PayAsYouGoSubscriptionRequests  # PAYG disabled
from .requests.transaction.status import TransactionStatusRequests


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
        refunds: Handler for refund retrieval.
        accounting: Handler for accounting data export.
        claim: Handler for account claim and fund transfer operations.
        webhooks: Handler for webhook verification.

    Example:
        >>> from qbitflow import QBitFlow
        >>>
        >>> client = QBitFlow(api_key="your_api_key_here")
        >>>
        >>> # Create a one-time payment session
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
        >>> # Export accounting data
        >>> events = client.accounting.export("2025-01-01", "2025-12-31", "json")
        >>> print(f"Total transactions: {len(events)}")
    """

    def __init__(
        self,
        api_key: str,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
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
            >>> client = QBitFlow(api_key="your_api_key_here")
            >>>
            >>> # With custom timeout and retries
            >>> client = QBitFlow(api_key="your_api_key_here", timeout=60, max_retries=5)
        """
        if not api_key:
            raise ValueError("API key is required")

        self.api_key = api_key
        self._timeout = timeout
        self._max_retries = max_retries

        # Core resource handlers
        self.customers = CustomerRequests(api_key, timeout, max_retries)
        self.products = ProductRequests(api_key, timeout, max_retries)
        self.users = UserRequests(api_key, timeout, max_retries)
        self.api_keys = ApiKeyRequests(api_key, timeout, max_retries)

        # Transaction handlers
        self.transaction_status = TransactionStatusRequests(api_key, timeout, max_retries)
        self.one_time_payments = PaymentRequests(api_key, timeout, max_retries)
        self.subscriptions = SubscriptionRequests(api_key, timeout, max_retries)
        # self.pay_as_you_go = PayAsYouGoSubscriptionRequests(...)  # PAYG disabled

        # New handlers
        self.refunds = RefundRequests(api_key, timeout, max_retries)
        self.accounting = AccountingRequests(api_key, timeout, max_retries)
        self.claim = ClaimRequests(api_key, timeout, max_retries)

        self.webhooks = WebhookRequests(api_key, timeout, max_retries)

    def __repr__(self) -> str:
        """Return a string representation of the client."""
        return f"QBitFlow(api_key='***{self.api_key[-4:]}')"
