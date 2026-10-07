"""
QBitFlow SDK main client.

This module provides the main QBitFlow client class for interacting with the API.
"""

import warnings
from typing import Any, Dict, Optional, Type, TypeVar

import httpx

from qbitflow import config

from .requests.accounting import AccountingRequests
from .requests.api_key import ApiKeyRequests
from .requests.base_request import (
    BaseRequest,
    on_behalf_of_headers,
    validate_api_key,
    validate_max_retries,
    validate_timeout,
)
from .requests.claim import ClaimRequests
from .requests.currencies import CurrencyRequests
from .requests.customer import CustomerRequests
from .requests.product import ProductRequests
from .requests.refund import RefundRequests
from .requests.transaction.payment import PaymentRequests
from .requests.transaction.status import TransactionStatusRequests
from .requests.transaction.subscription import SubscriptionRequests
from .requests.user import UserRequests
from .requests.webhook import WebhookRequests

_HandlerT = TypeVar("_HandlerT", bound=BaseRequest)


class QBitFlow:
    """
    Main client for interacting with the QBitFlow API.

    This class provides access to all QBitFlow API functionality through
    organized request handlers for different resource types. All handlers share one
    HTTP connection pool; call :meth:`close` (or use the client as a context manager)
    when you are done with it.

    Attributes:
        api_key: API key used for authentication.
        base_url: Base URL requests are sent to.
        customers: Handler for customer-related operations.
        products: Handler for product-related operations.
        users: Handler for user-related operations.
        api_keys: Handler for read-only API key access.
        currencies: Handler for supported-currency lookups.
        transaction_status: Handler for checking transaction statuses.
        one_time_payments: Handler for one-time payment operations.
        subscriptions: Handler for recurring subscription operations.
        refunds: Handler for refund retrieval.
        accounting: Handler for accounting data export.
        claims: Handler for account claim and fund transfer operations.
        webhooks: Handler for webhook verification.

    Example:
        >>> from qbitflow import QBitFlow
        >>>
        >>> client = QBitFlow(api_key="your_api_key_here")
        >>>
        >>> # Create a one-time payment session
        >>> response = client.one_time_payments.create_session(product_id=1)
        >>> print(f"Payment link: {response.link}")
        >>>
        >>> # Create a subscription
        >>> from qbitflow import Duration
        >>> response = client.subscriptions.create_session(
        ...     product_id=1,
        ...     frequency=Duration(value=1, unit="months"),
        ... )
        >>> print(f"Subscription link: {response.link}")
        >>>
        >>> # Act for one of your organization's users on every service
        >>> as_user = client.on_behalf_of(42)
        >>> products = as_user.products.get_all()
        >>>
        >>> # Export accounting data
        >>> events = client.accounting.export("2025-01-01", "2025-01-31", "json")
        >>> print(f"Total transactions: {len(events)}")
    """

    customers: CustomerRequests
    products: ProductRequests
    users: UserRequests
    api_keys: ApiKeyRequests
    currencies: CurrencyRequests
    transaction_status: TransactionStatusRequests
    one_time_payments: PaymentRequests
    subscriptions: SubscriptionRequests
    refunds: RefundRequests
    accounting: AccountingRequests
    claims: ClaimRequests
    webhooks: WebhookRequests

    def __init__(
        self,
        api_key: str,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
        base_url: Optional[str] = None,
    ):
        """
        Initialize the QBitFlow client.

        Args:
            api_key: Your QBitFlow API key. Get this from your dashboard.
            timeout: Optional request timeout in seconds (default: 30). ``0`` disables the
                timeout.
            max_retries: Optional maximum retry attempts for idempotent (GET) requests
                (default: 3). ``0`` disables retries.
            base_url: Optional API base URL (default: the module setting — see
                :func:`qbitflow.config.set_base_url` / the ``QBITFLOW_BASE_URL`` environment
                variable read at import — else ``https://api.qbitflow.app/v1``). A trailing
                slash is stripped.

        Raises:
            ValueError: If api_key is empty, blank or not a string.
            ValidationError: If ``timeout`` or ``max_retries`` is negative or not a number,
                or ``base_url`` is blank.

        Example:
            >>> client = QBitFlow(api_key="your_api_key_here")
            >>>
            >>> # With custom timeout, retries and base URL
            >>> client = QBitFlow(
            ...     api_key="your_api_key_here",
            ...     timeout=60,
            ...     max_retries=5,
            ...     base_url="https://staging.example.com/v1",
            ... )
        """
        # Validate everything before opening the connection pool, so a rejected argument never
        # leaks one.
        validate_api_key(api_key)
        timeout = validate_timeout(timeout)
        max_retries = validate_max_retries(max_retries)
        normalised_base_url = BaseRequest._normalise_base_url(base_url)

        effective_timeout = config.DEFAULT_TIMEOUT if timeout is None else timeout
        # ``timeout=0`` means "no timeout" to httpx, which is what an explicit zero asks for.
        http = httpx.Client(timeout=effective_timeout or None)

        self._setup(
            api_key,
            timeout=timeout,
            max_retries=max_retries,
            base_url=normalised_base_url,
            http=http,
            headers={},
            owns_http=True,
        )

    def _setup(
        self,
        api_key: str,
        *,
        timeout: Optional[float],
        max_retries: Optional[int],
        base_url: Optional[str],
        http: httpx.Client,
        headers: Dict[str, str],
        owns_http: bool,
    ) -> None:
        self.api_key = api_key
        self._timeout = timeout
        self._max_retries = max_retries
        self._base_url = base_url
        self._http = http
        self._owns_http = owns_http
        self._scope_headers = dict(headers)

        def make(handler: Type[_HandlerT]) -> _HandlerT:
            return handler(
                api_key,
                timeout=timeout,
                max_retries=max_retries,
                headers=dict(headers) or None,
                base_url=base_url,
                http_client=http,
            )

        # Core resource handlers
        self.customers = make(CustomerRequests)
        self.products = make(ProductRequests)
        self.users = make(UserRequests)
        self.api_keys = make(ApiKeyRequests)
        self.currencies = make(CurrencyRequests)

        # Transaction handlers
        self.transaction_status = make(TransactionStatusRequests)
        self.one_time_payments = make(PaymentRequests)
        self.subscriptions = make(SubscriptionRequests)

        self.refunds = make(RefundRequests)
        self.accounting = make(AccountingRequests)
        self.claims = make(ClaimRequests)

        self.webhooks = make(WebhookRequests)

    @property
    def claim(self) -> ClaimRequests:
        """
        Deprecated alias of :attr:`claims` (the same object).

        .. deprecated:: 2.5.0
            Use ``client.claims``.
        """
        warnings.warn(
            "QBitFlow.claim is deprecated; use QBitFlow.claims instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.claims

    def on_behalf_of(self, user_id: int) -> "QBitFlow":
        """
        Return a client whose every service acts on behalf of one of your organization's users.

        Every request made through the returned client carries ``On-Behalf-Of: <user_id>``, so
        it reads and writes that user's resources with that user's role. It requires an
        organization-level admin/owner API key. ``0`` means "act at the organization level"
        (no header). The per-service ``client.<service>.on_behalf_of(user_id)`` remains
        available.

        The returned client shares this client's connection pool and configuration. Close only
        the root client: closing a scoped copy is a no-op.

        Args:
            user_id: ID of the user to act for, or 0 to act at the organization level.

        Returns:
            A scoped :class:`QBitFlow` client.

        Raises:
            ValidationError: If ``user_id`` is not a non-negative integer.

        Example:
            >>> as_user = client.on_behalf_of(42)
            >>> as_user.products.get_all()        # user 42's products
            >>> as_user.one_time_payments.get_all()
        """
        headers = on_behalf_of_headers(user_id)
        scoped = QBitFlow.__new__(QBitFlow)
        scoped._setup(
            self.api_key,
            timeout=self._timeout,
            max_retries=self._max_retries,
            base_url=self._base_url,
            http=self._http,
            headers=headers,
            owns_http=False,
        )
        return scoped

    @property
    def base_url(self) -> str:
        """The base URL requests are sent to (per-client value, else the module setting)."""
        if self._base_url is not None:
            return self._base_url
        return config.get_base_url().strip().rstrip("/")

    def close(self) -> None:
        """
        Close the shared HTTP connection pool. The client (and every scoped copy made with
        :meth:`on_behalf_of`) must not be used afterwards. On a scoped copy this is a no-op.
        """
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> "QBitFlow":
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()

    def __repr__(self) -> str:
        """Return a string representation of the client."""
        scope = self._scope_headers.get("On-Behalf-Of")
        suffix = f", on_behalf_of={scope}" if scope else ""
        return f"QBitFlow(api_key='***{self.api_key[-4:]}', base_url='{self.base_url}'{suffix})"
