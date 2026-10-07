"""The QBitFlow client."""

from __future__ import annotations

from types import TracebackType
from typing import Optional, Type

import httpx

from ._services._base import Service
from ._services.catalog import CheckoutSessionsService, CustomersService, ProductsService
from ._services.organization import (
    AccountingService,
    CurrenciesService,
    InvitationsService,
    MembersService,
    WalletsService,
)
from ._services.transactions import (
    FailuresService,
    PaymentsService,
    RefundsService,
    SubscriptionsService,
)
from ._services.webhooks import WebhooksService
from ._transport import (
    DEFAULT_BASE_URL,
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT,
    Endpoint,
    RequestOptions,
    Response,
    Transport,
    split_options,
)
from ._validation import (
    check_idempotency_key,
    check_on_behalf_of,
    check_request_id,
    is_http_url,
    trim_space,
)
from .errors import field_error
from .models.resources import Me

__all__ = ["QBitFlow"]


class QBitFlow:
    """The QBitFlow API client (API v2). Create one per API key and share it.

    Example::

        from qbitflow import QBitFlow

        with QBitFlow(os.environ["QBITFLOW_API_KEY"]) as client:
            me = client.me()  # the recommended start-up check
            session = client.checkout_sessions.create_payment(
                product_name="Premium access", price=4.99, reference="order-1042"
            )
            print(session.link)

    Args:
        api_key: Your API key (sent as ``X-API-Key``): non-blank, starting with ``sk_``.
        base_url: The API root (default ``https://api.qbitflow.app/v2``); an absolute http(s)
            URL, a trailing ``/`` is stripped.
        timeout: Bounds each HTTP attempt, in seconds (default 30); a retried call may take
            longer in total.
        max_retries: How many times a retryable call (a read, or one of the 7 idempotent
            creates) is re-sent after a transient failure (default 3; 0 disables retries).
        on_behalf_of: Act in this member's space on every request (a member's ``userUuid``;
            organization key only).
        http_client: An ``httpx.Client`` to send the requests with (proxies, transports,
            instrumentation). The SDK never follows redirects and sets its own timeout per
            attempt. It is not closed by :meth:`close`.

    Raises:
        ValidationError: a missing or malformed key, or an invalid option (nothing is sent:
            call :meth:`me` to check the key online).
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
        on_behalf_of: Optional[str] = None,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        if not isinstance(api_key, str) or trim_space(api_key) == "":
            raise field_error("apiKey", "is required")
        api_key = trim_space(api_key)
        if not api_key.startswith("sk_"):
            raise field_error("apiKey", "must be a QBitFlow API key (sk_…)")

        if base_url is None:
            url = DEFAULT_BASE_URL
        else:
            url = trim_space(base_url).rstrip("/") if isinstance(base_url, str) else ""
            if not is_http_url(url):
                raise field_error("baseUrl", "must be an absolute http or https URL")

        if timeout is None:
            seconds = DEFAULT_TIMEOUT
        elif isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0:
            raise field_error("timeout", "must be a positive number of seconds")
        else:
            seconds = float(timeout)

        if max_retries is None:
            retries = DEFAULT_MAX_RETRIES
        elif isinstance(max_retries, bool) or not isinstance(max_retries, int) or max_retries < 0:
            raise field_error("maxRetries", "must not be negative")
        else:
            retries = max_retries

        check_on_behalf_of(on_behalf_of)
        if http_client is not None and not isinstance(http_client, httpx.Client):
            raise field_error("httpClient", "must be an httpx.Client")

        self._init(Transport(api_key, url, seconds, retries, http_client), on_behalf_of or "")

    def _init(self, transport: Transport, on_behalf_of: str) -> None:
        self._transport = transport
        self._on_behalf_of = on_behalf_of
        #: Products (``/product…``).
        self.products = ProductsService(self)
        #: Customers (``/customer…``).
        self.customers = CustomersService(self)
        #: Checkout sessions: create, read the status, expire.
        self.checkout_sessions = CheckoutSessionsService(self)
        #: One-time payments and the combined feed.
        self.payments = PaymentsService(self)
        #: The failed payment attempts.
        self.failures = FailuresService(self)
        #: Subscriptions and their bills.
        self.subscriptions = SubscriptionsService(self)
        #: Refunds.
        self.refunds = RefundsService(self)
        #: The organization's members and their held funds (organization key).
        self.members = MembersService(self)
        #: Invitations to join as a member (organization key).
        self.invitations = InvitationsService(self)
        #: Wallets and the currencies a space accepts.
        self.wallets = WalletsService(self)
        #: The accounting export.
        self.accounting = AccountingService(self)
        #: Webhook verification, endpoints (``.endpoints``) and the event log (``.events``).
        self.webhooks = WebhooksService(self)
        #: The currency catalog.
        self.currencies = CurrenciesService(self)

    def on_behalf_of(self, user_uuid: Optional[str]) -> "QBitFlow":
        """A client acting in a member's space: every request sends
        ``On-Behalf-Of: <user_uuid>`` (a member's ``userUuid``; organization key only). It shares
        this client's connections and configuration; ``""`` (or ``None``) returns one at the
        organization level.

        Raises:
            ValidationError: ``user_uuid`` is not a UUID, or is the nil UUID.
        """
        check_on_behalf_of(user_uuid)
        derived = object.__new__(QBitFlow)
        derived._init(self._transport, user_uuid or "")
        return derived

    def me(self, *, options: Optional[RequestOptions] = None) -> Me:
        """What the API key is (``GET /me``): its role, its space (organization or member, test
        or live mode) and the member it acts for. The recommended start-up check, e.g. assert
        ``me.space.test`` in a test environment."""
        return Service(self)._call(Me, Endpoint("GET", "/me"), options)

    def close(self) -> None:
        """Close the HTTP connections (when the SDK created the ``httpx.Client``). Clients
        derived with :meth:`on_behalf_of` share them."""
        self._transport.close()

    def __enter__(self) -> "QBitFlow":
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        self.close()

    def __repr__(self) -> str:
        scope = f", on_behalf_of={self._on_behalf_of!r}" if self._on_behalf_of else ""
        return f"QBitFlow(base_url={self._transport.base_url!r}{scope})"

    # ── Internal ──

    def _send(self, endpoint: Endpoint, options: Optional[RequestOptions]) -> Response:
        """Apply the request options (validated after the params), then send."""
        opts = split_options(options)
        on_behalf_of = self._on_behalf_of
        if opts.on_behalf_of is not None:
            check_on_behalf_of(opts.on_behalf_of)
            on_behalf_of = opts.on_behalf_of
        if opts.request_id is not None and opts.request_id != "":
            check_request_id(opts.request_id)
        if endpoint.idempotent and opts.idempotency_key is not None and opts.idempotency_key != "":
            check_idempotency_key(opts.idempotency_key)
        return self._transport.send(endpoint, on_behalf_of, opts)
