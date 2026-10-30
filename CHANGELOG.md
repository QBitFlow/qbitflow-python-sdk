# Changelog

All notable changes to the QBitFlow Python SDK are documented in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.1.1] - 2026-10-30

A cancelled subscription's `cancel` and `test_bill` now raise a conflict, not a not-found, and
deleting a webhook endpoint deletes its delivery history. No signature changes: the SDK maps errors
by HTTP status, so these are the API's answers; the SDK's documentation and tests follow them.

### Changed

-   **⚠️ `subscriptions.cancel` and `subscriptions.test_bill` on a cancelled subscription raise a
    `ConflictError`** (`409 subscription_already_stopped_or_inactive`), where the API answered
    `404 not_found` (a `NotFoundError`). `get` returns a cancelled subscription (`status`
    `cancelled`), so the actions now say it is cancelled already instead of saying it doesn't
    exist. Another space's subscription (another organization's, or the other mode's) is still a
    `NotFoundError`, whatever its status. **Migration:** code that treated a `NotFoundError` from
    `cancel` as "already cancelled" catches a `ConflictError` with `code ==
    "subscription_already_stopped_or_inactive"` (or reads the subscription first); a 404 now only
    means it isn't yours or doesn't exist. This is the API's behavior, whatever the SDK version.
-   **Docs: deleting a webhook endpoint deletes its delivery history.**
    `webhooks.endpoints.delete` removes its deliveries from the event log, successful ones
    included: `webhooks.events.get` no longer lists them. `EndpointDelivery.pending` and the README
    said a deleted endpoint's deliveries stayed listed as not delivered. To keep an endpoint's
    history, disable it (`update(uuid, enabled=False)`) rather than delete it.

## [3.1.0] - 2026-10-29

Subscriptions tell when access ends (`access_until`), and the event log which deliveries are
still in progress. No signature changes.

### Added

-   **`Subscription.access_until`** (`accessUntil` on the wire): when access ends.
    `current_period_end` (the paid-through date), plus 1 hour for an `active` subscription:
    QBitFlow bills a renewal within minutes of its due date, so the rule "grant access while now <
    `current_period_end`" cut every subscriber off for those minutes at each renewal. **The access
    rule is now "grant access while now < `access_until`, whatever the status".** On every read and
    every `subscription.*` event; `None` on a subscription stored before the API sent it.
-   **`EndpointDelivery.pending`, `next_attempt_at` and `waiting_for`**
    (`webhooks.events.get`). `pending` is true while QBitFlow still attempts the event on its own;
    `next_attempt_at` is set while it is retried after a failed attempt, and `waiting_for` (an
    `evt_…`) while it is queued behind an earlier event of the same publication. A delivery that
    is queued, or about to start, is now listed with **no `attempts`** instead of not being listed
    at all: code that reads `attempts[-1]` must check the list first. A response without `pending`
    (an older server) decodes as `pending=False`.

### Changed

-   **`Subscription.has_access()` reads `access_until`**, and `current_period_end` only when
    `access_until` is `None` (a subscription stored before it existed). An `active` subscription
    now has access for the hour after `current_period_end`, while its renewal is billed; keep
    `current_period_end` for display ("paid through").
-   **`members.trust` can raise a `ConflictError` `member_has_no_wallet`** (409) when the member's
    own wallets accept none of your currencies: nothing changes (they stay held, their checkouts
    keep working). Trust is one-way and narrows the member's currencies to their own wallets';
    trust them once they've added a wallet.
-   **README: integration notes.** `subscription.upcomingBill` follows the dashboard's
    `subscriptions.upcomingBillDays` (3 days by default, 0 = never), is checked daily, and isn't
    sent for a subscription whose period (a trial: the trial) is no longer than that. A
    development server lowers the live frequency minimum to 1 minute. A member's deliveries to
    your endpoints show from the organization (`include_members=True`, then `get`).
    `allowance.remaining_periods` counts bills before network fees, so it is usually higher than
    the checkout's "N payments". The organization fee is `(amount − QBitFlow's fee) ×
    organization_fee_percent / 100`, rounded down. Money strings come back canonical (`"12.50"` →
    `"12.5"`): compare them as decimals. A subscription checkout's inline product creates a hidden
    product, reused by checkouts with the same name, description and price; a payment checkout of
    a subscription product sells it once; a subscription checkout of a one-time product needs
    `frequency`. A second `expire` answers without `expires_at`. `held_funds_pending` is released
    from the dashboard. The link QBitFlow emails with an invitation has its own token: it differs
    from `CreatedInvitation.link`.
-   **README: webhook order is per publication, never per subscription.** The events published
    together (a `subscription.created` and its first `subscription.billed`) reach an endpoint in
    order; nothing waits across publications.
-   **README: a checkout's `customer_reference` without a QBitFlow customer means no receipt**
    and no other customer email. Create the customer with that reference and their email first
    (even after the checkout was created, before the payment is recorded) to have them.

## [3.0.0] - 2026-10-28

The SDK for **QBitFlow API v2**. A major release, written for the API's new REST routes: the
client, the services, the models, the errors and the webhooks change, and almost every 2.x call
needs an edit. This entry lists the changes since 2.1.0;
[MIGRATION-v3.md](https://github.com/QBitFlow/qbitflow-python-sdk/blob/main/MIGRATION-v3.md) maps
every 2.x method and type to its replacement, with before/after code. Requires Python 3.10 or
later.

### Added

-   **Checkout sessions** (`client.checkout_sessions`): `create_payment` and
    `create_subscription` (with `expires_in_minutes`, `metadata`, and the `{{UUID}}` /
    `{{TRANSACTION_TYPE}}` redirect placeholders, `qbitflow.PLACEHOLDER_UUID` and
    `PLACEHOLDER_TRANSACTION_TYPE`), `get`, `expire`, and `wait_for_completion(uuid, *,
    timeout=600, interval=3)` for scripts.
-   **Checkout fees**: `fees=CheckoutFees(items=[FeeItem(label, amount_usd, description=None)],
    processing_fee=None)` on both session creates: up to 10 lines of your own (a tax, shipping)
    and QBitFlow's processing fee, which the customer pays on top of the price (a subscription:
    with every bill). Recorded as `fees` (`FeeLine`, `FeeLineType`) next to `price_usd` on
    payments, subscriptions, transactions and the `checkout.expired` session.
-   **Your own metadata** (`metadata=`, a `dict[str, str]`) on products, customers, checkouts
    and subscriptions (`subscriptions.update`), copied from a checkout onto its payment or
    subscription and into their webhooks; merged on updates (a key set to `""` deletes it).
-   **Marketplaces**: `members` (`list`, `iterate`, `get`, `update`, `remove`, `trust`,
    `list_held_funds`, `get_held_funds`, `get_own_held_funds`) and `invitations` (`create`,
    `list`, `iterate`, `revoke`; `create(send_email=False)` to share the link yourself), with
    `Member`, `Invitation`, `CreatedInvitation`, `HeldFunds`, `LedgerEntry`, `MemberHeldFunds`.
-   **Acting for a member**: `client.on_behalf_of(user_uuid)` returns a client whose requests
    act in that member's space (`On-Behalf-Of`); `RequestOptions(on_behalf_of=…)` for one call.
-   `client.me()`: what the API key is (its role, its space, test or live mode, the member it
    acts for), the recommended start-up check (`Me`, `MeSpace`, `MeMember`).
-   `transactions.list` / `iterate`: one feed of payments and subscription bills
    (`Transaction`, `TransactionKind`); `failures.list` / `iterate`: the failed payment attempts
    (`Failure`, `FailureKind`, `FailureCategory`).
-   `payments.list` / `iterate` with filters (customer, product, dates, `reference`,
    `refunded`, `include_members` / `user_uuid`).
-   `subscriptions.list` / `iterate`, `update` (metadata), `list_bills` / `iterate_bills`,
    `get_bill`; `Subscription.current_period_end`, `action_required`, `price_usd`,
    `cancellation_reason`, `dunning`, `metadata`, `management_page_link`, the `Allowance`
    object, and `Subscription.has_access(at=None)` (grant access while now is before
    `current_period_end`).
-   `refunds.list` / `iterate` (filters `status`, `tx_uuid`, `held`, `include_members`,
    `user_uuid`) and `refunds.get`, read only: refunds are answered and sent from the dashboard.
-   `products.list` / `iterate` (paginated, `include_hidden`, `subscription`, `reference`),
    subscription products (`SubscriptionTermsParams`), `Product.payment_link`;
    `customers.list` / `iterate` (`email`, `reference`).
-   `wallets.list(with_balances=…)`, `wallets.list_for_member`,
    `wallets.list_accepted_currencies`; `currencies.get(id)`.
-   `accounting.export_json` / `export_csv`, and `export_json_range` / `export_csv_range`, which
    split any range into windows of at most 92 days and join the results.
-   **Webhook endpoints and the event log**: `webhooks.endpoints` (`list`, `iterate`, `create`
    with the secret shown once, `get`, `update`, `delete`) and `webhooks.events` (`list`,
    `iterate`, `get` with its deliveries: `EventDetail`, `EndpointDelivery`, `DeliveryAttempt`).
-   **Typed webhook events**: one class per event type (15, from `PaymentCompletedEvent` to
    `WebhookTestEvent`) in the `qbitflow.Event` discriminated union, `UnknownEvent` for a type
    added later, and the `EventType` constants.
-   **`WebhookRouter`** (`webhooks.WebhookRouter(secret)` or `client.webhooks.router(secret)`):
    register a handler per event type, then mount it with `router.flask_view()`,
    `router.django_view()`, `router.fastapi_endpoint()` or `await router.handle_asgi(request)`,
    or call `router.handle(raw_body, signature_header)`. It verifies, parses, dispatches and
    answers the status QBitFlow expects. Optional extras `qbitflow[flask]`, `[django]`,
    `[fastapi]` and `[starlette]` pin a supported framework; none is a dependency.
-   `webhooks.sign(raw_body, secret, timestamp=None)`, to test your endpoint.
-   **Iterators** for every paginated list: lazy, one request per page, filters kept.
-   **Retries with idempotency**: reads and the 6 creates are retried on network errors,
    timeouts, 5xx, 429 (honouring `Retry-After`, up to 60 seconds) and 409
    `idempotency_key_in_use`, with a 1 s, 2 s, 4 s back-off; every create sends an
    `Idempotency-Key`, reused on its retries (`RequestOptions(idempotency_key=…)` for your own).
    `qbitflow.is_retryable(error)`.
-   **Client-side validation** of every input, mirroring the API's rules, before anything is
    sent: a `ValidationError` naming each field by its wire name.
-   `QBitFlow.from_env(**overrides)` (`QBITFLOW_API_KEY`, `QBITFLOW_BASE_URL`,
    `QBITFLOW_ON_BEHALF_OF`); `RequestOptions(request_id=…)` (sent as `X-Request-Id`).
-   `qbitflow.format_amount(min_units, decimals)`, `parse_amount(amount, decimals)` and
    `Currency.format_amount(min_units)`: exact conversions, never through a float.
-   `TokenAmount`, `Settlement`, `Split`, `SettlementTransaction`, `TransferSettlement`: how a
    payment was paid and split; `MerchantNotReadyReason` for a 409 `merchant_not_ready`.
-   `NOT_GIVEN`, the default of the clearable update fields (`""` or `None` clears them).
-   `qbitflow.__version__` and `User-Agent: qbitflow-python/3.0.0`.

### Changed

-   **Breaking: API v2.** The default base URL is `https://api.qbitflow.app/v2`, with REST
    routes (updates as `PATCH`, every `DELETE` answering `204`). The constructor no longer reads
    `QBITFLOW_BASE_URL` and `qbitflow.config.set_base_url` is gone: pass `base_url=`, or use
    `QBitFlow.from_env()`.
-   **Breaking: the client.** `QBitFlow(api_key, *, base_url=None, timeout=None,
    max_retries=None, on_behalf_of=None, http_client=None)`: keyword-only options, `timeout` in
    seconds per attempt (a float), `max_retries=0` disables retries, an injectable
    `httpx.Client`, `close()` and context-manager support. The key is checked when the client is
    built (non-blank, starting with `sk_`, printable ASCII without spaces): a `ValidationError`,
    nothing sent. API v2 keys are `sk_<test|live>_<uuid>_<secret>`; keys of an earlier format
    are refused by the API (401): create a new one in the dashboard.
-   **Breaking: keyword arguments.** Every method takes keyword-only arguments (path ids are
    positional) and `options=RequestOptions(...)` last; the `Create…Dto` / `Update…Dto` request
    classes are gone (`products.create(name=…, price_usd=…)`).
-   **Breaking: services renamed.** `one_time_payments.create_session` and
    `subscriptions.create_session` → `checkout_sessions.create_payment` / `create_subscription`;
    `transaction_status.get(uuid, type)` → `checkout_sessions.get(uuid)`;
    `one_time_payments.get` / `get_by_reference` / `get_all` → `payments.get` /
    `get_by_reference` / `list`; `one_time_payments.get_all_combined` → `transactions.list`;
    `subscriptions.get_payment_history` → `list_bills`; `subscriptions.force_cancel` →
    `cancel(uuid, immediate=True)` (returns a `SubscriptionCancellation`; `immediate=False`
    cancels at the end of the paid period); `subscriptions.execute_test_billing_cycle` →
    `test_bill` (returns a `TestBill`); `refunds.get_all` / `get_all_inactive` →
    `refunds.list(status=[…])`; `products.get_all` and `customers.get_all` → `list` (paginated);
    `currencies.get_all_available` / `get_all_main` → `currencies.list(test=…, main=…)`;
    `accounting.export(from, to, format)` → `export_json` / `export_csv`; per-service
    `on_behalf_of(user_id)` → `client.on_behalf_of(user_uuid)`; `users.*` → `invitations.*` and
    `members.*`; `claim.*` → `members.trust` and the held-funds reads.
-   **Breaking: ids are strings.** Products are named by `uuid` (was the numeric `id`;
    `product_id` → `product_uuid` everywhere), people by their user UUID (`user_id` →
    `user_uuid`); `organization_id` and the `currency_id` fields are gone (each model carries its
    `currency`). Transaction ids are prefixed (`pay@`, `sub@`, `sub-hist@`, `refund@`,
    `transfer@`, `release@`); every route also takes the bare UUID. Currencies keep numeric ids.
-   **Breaking: money is a decimal string, never a float**, in requests and responses: USD
    amounts (`price_usd`, `amount_usd`), token amounts (`amount`, next to `amount_min_units`)
    and fee rates in percent (`fee_percent`, `organization_fee_percent`, `refund_percent`; the
    `…_bps` integers are gone). Money inputs take a `str` or a `decimal.Decimal`; a `float` is
    a `ValidationError`.
-   **Breaking: amounts are token amounts.** `Payment.amount` and `Bill.amount` are in the
    currency's units (`"10"` for 10 USDC); the USD value is `amount_usd`.
-   **Breaking: models renamed and reshaped.** `LinkResponse` → `CreatedCheckoutSession`
    (`expires_at` a `datetime`); `TransactionStatus` → `CheckoutSessionStatus`;
    `TransactionStatusValue` → `CheckoutSessionStatusValue` (`created`, `waitingConfirmation`,
    `completed`, `expired`: a failed attempt is `created` with `last_attempt` set, never final);
    `SubscriptionHistory` → `Bill`; `RefundEntry` → `Refund` (`tx_id` → `tx_uuid`);
    `CombinedPaymentItem` → `Transaction` (`source` → `type`); `User` → `Member`; `UserRole` →
    `Role` (`ADMIN`, `USER`); `PaymentMetadata` and its parts → `Settlement` (on `settlement`;
    `metadata` is now your own data). `transaction_hash` → `tx_hash`; `name` → `first_name` on
    customers; a payment's and a bill's `name` / `description` → `product_name` /
    `product_description`; `Product.price` → `price_usd`.
-   **Breaking: subscriptions.** `subscription_status` → `status` (`trial`, `trialExpired`,
    `active`, `pastDue`, `paused`, `stopped`, `cancelled`); `low_on_funds` and `pending` became
    `action_required` values (`topUpAllowance`, `raiseMaximum`, `confirmTrial`), the `stopped`
    bool the `stopped` status. `frequency` is a `Duration` (was seconds); `last_billing_date` →
    `last_billed_at`, `next_billing_date` → `next_billing_at`, `minimum_cancellation_date` →
    `cancellable_at`; `allowance` is an `Allowance` object.
-   **Breaking: enum values** follow the API's lowerCamelCase (`pastDue`, `trialExpired`);
    `RefundStatus.REFUSED` → `REJECTED`; `TransactionType.ONE_TIME_PAYMENT` → `PAYMENT`.
    Enums are open: a value the SDK does not know yet is kept as the raw string.
-   **Breaking: the currency object** gains `code` (`BASE:USDC`) and `chain`; `address` is
    `None` on a native coin; the nested `main_currency` is gone (`main_currency_id` stays).
-   **Breaking: accounting rows** (`AccountingEvent`) follow the API v2 export: amounts in the
    currency's units as decimal strings with their `…_min_units` twins, USD amounts and rates
    as decimal strings, `token_symbol` → `currency`, `payment_id` / `related_payment_id` →
    `tx_uuid` / `related_tx_uuid`, `payment_reference` / `related_payment_reference` →
    `reference` / `related_reference`, `product_id` → `product_uuid`, the network fees apart
    from the net (`network_fees_paid_by`). One export covers at most 92 days, both ends included.
-   **Breaking: pagination.** `get_all(limit, cursor)` → `list(limit=…, cursor=…, filters…)`
    returning a `Page[T]` (`items`, `has_more`, `next_cursor`), plus an `iterate` twin. The
    short lists (currencies, wallets, held funds, the JSON export) return a plain `list`.
-   **Breaking: lookups by reference** (`products`, `customers`, `payments`, `subscriptions`
    `get_by_reference`) run the list's `?reference=` filter and raise `NotFoundError` when no
    item has exactly that reference.
-   **Breaking: deletes return `None`** (every `DELETE` answers `204`).
-   **Breaking: errors.** One class per condition, imported from `qbitflow`, all deriving from
    `QBitFlowError` and `ApiError` (`status`, `code`, `message`, `details`, `request_id`,
    `field_errors`, `raw_body`): `ValidationError`, `BadRequestError`, `AuthenticationError`,
    `PermissionDeniedError`, `NotFoundError` (was `NotFoundException`), `ConflictError`,
    `GoneError`, `IdempotencyError`, `RateLimitError` (`retry_after`, `limit`,
    `period_seconds`), `ServerError`, `NetworkError`, `WebhookSignatureError`. `APIError` →
    `ApiError`. A 403 `policy_disabled` carries `details["policy"]`, and `details["field"]`
    when the policy governs a request field (a member's checkout `success_url` / `cancel_url`
    while the organization's `members.checkoutRedirects` policy is off).
-   **Breaking: webhooks** use API v2's scheme: the `QBitFlow-Signature: t=…,v1=…` header, an
    HMAC-SHA256 of `t + "." + raw_body` over the raw body (no canonical JSON), and the event
    envelope (`id`, `type`, `created_at`, `test`, `user_uuid`, `data`). `verify_webhook_signature`,
    `compute_webhook_signature` and `client.webhooks.verify(payload, signature, timestamp)` →
    `qbitflow.webhooks.verify` / `construct_event` / `parse_event` (raising
    `WebhookSignatureError` with a `reason`) and `client.webhooks.verify_remote`. Every `v1=`
    signature is checked, so a secret rotation needs nothing on the receiving side.
-   **Breaking: retries** are limited to reads and the 6 idempotent creates; other writes are
    never retried automatically. Redirects are never followed (a 3xx is a `ServerError`).
-   A member's own key may send a checkout's `success_url` / `cancel_url` while the
    organization's `members.checkoutRedirects` policy allows it (403 `policy_disabled`
    otherwise); the organization acting for the member (`on_behalf_of`) always may.
-   Dependencies: `pydantic>=2.5` (was 2.0); `email-validator` is no longer needed.

### Removed

-   `users`, `api_keys` and `claim` (members and invitations replace them; keys are managed in
    the dashboard, `client.me()` describes the current one).
-   `transaction_status` and its WebSocket URL helper (`checkout_sessions.get`,
    `wait_for_completion` and webhooks replace them).
-   `one_time_payments.get_session` / `subscriptions.get_session`, and
    `one_time_payments.get_customer_for_transaction` (read `payment.customer_uuid`, then
    `customers.get`).
-   `refunds.get_by_transaction` (`refunds.list(tx_uuid=…)`, or `payment.refund`).
-   `customers.get_by_email`: an email may match several customers (`customers.list(email=…)`).
-   Pay-as-you-go subscriptions (`PayAsYouGoSubscription`, `PaygSubscriptionSession`): the API
    has none.
-   The refund status `failed` (`RefundStatus.FAILED`) and the checkout statuses `pending`,
    `failed` and `cancelled`: the API never sends them.
-   Every `TransactionType` value but `PAYMENT` and `CREATE_SUBSCRIPTION`, and
    `TransactionShortType`.
-   `Role.OWNER` (an API key is at most `admin`; an `"owner"` the API may send decodes as the
    plain string).
-   Canonical-JSON webhook verification (`canonical_json`, `extract_webhook_headers`, the
    `X-Webhook-*` header helpers, `TEST_WEBHOOK_ID`) and the v1 webhook payload models
    (`SessionWebhookResponse`, `SubscriptionStatusTransitionWebhook`, the session models).
-   `qbitflow.config`, `qbitflow.dto`, `qbitflow.requests`, `qbitflow.utils` and
    `qbitflow.exceptions` (import everything from `qbitflow`); `InvalidRequestError`;
    `ApiKey`, `Organization`, `ClaimRequest`, `ClaimFund`, `CreateClaimRequestResponse`,
    `StatusLinkResponse`, `StatusResponse`, `SuccessResponse`; `PaymentMetadata`,
    `TxMetadata`, `BlockData`, `NetworkFees`, `TxAmountsFull`, `TxAmountsUSD`,
    `TxAmountsMinUnits` (→ `Settlement` and its parts).

### Fixed

-   Field validation errors are read from the API's `details.errors`: `field_errors` names each
    failing input by its wire name, dotted when nested (`frequency.unit`). 2.x read another key
    and always returned them empty.
-   Path segments and query values are percent-encoded: an id containing `/`, `?`, `#`, `%` or
    `&` can no longer change the request, and a `.` or `..` segment is escaped.
-   A reference (`reference`, `product_reference`, `customer_reference`, the `reference=`
    filters, `get_by_reference`) equal to `.` or `..` is refused before sending, as the API
    does: such a reference could never be named in a URL.
-   Lengths are counted in characters (code points), as the API does.
-   A 400 that is not a validation failure is a `BadRequestError`, and a 422 an
    `IdempotencyError`, instead of a `ValidationError`.
-   A deeply nested JSON answer or webhook body is a `ServerError` or a `ValidationError`, never
    a raw `RecursionError`.

### Security

-   `timeout` bounds each attempt as a whole, the response body included, so a server sending
    its answer slowly can no longer hold a call indefinitely.
-   The API key is validated when the client is built, and the error never quotes it: a key
    with a line break used to fail every request with an error whose message carried the key.
-   `base_url` must be an `http`/`https` URL with a host and without credentials, query or
    fragment; the error never quotes the URL.
-   `repr()` never shows a secret: the client shows its base URL only, `WebhookEndpointCreated`
    leaves out its `secret`, and the webhook router never shows its secret.
-   Redirects are never followed, so the `X-API-Key` header is never sent to another origin; TLS
    verification stays httpx's default.
-   Webhook signatures are compared in constant time against every `v1` signature, within a
    5-minute tolerance either way.

## [2.1.0] - 2026-09-21

Aligns the SDK with docs revision `c3c8831`. Fixes a bug that made subscription-session
retrieval raise, and one that silently reset a user's organization fee.

> **Note:** this release carries breaking changes (listed below) despite the minor version
> bump.


### Added — local webhook verification

- **Verify webhooks without a network call.** Local verification needs your webhook secret
  (available from the QBitFlow dashboard) but no round-trip, so it is faster and keeps
  working when the API is unreachable. The existing API-side `verify` is unchanged and
  still available for callers who would rather not hold the secret.

  It performs the same three checks the server does: the timestamp is within a replay
  window (5 minutes by default, configurable to match your deployment), the HMAC-SHA256 of
  `<timestamp>.<canonical-json>` matches, and the comparison is constant-time so a timing
  side channel cannot be used to guess the signature.

  The signature covers a **canonical** rendering — object keys sorted at every level, no
  insignificant whitespace — rather than the bytes as they arrived, because proxies and
  frameworks routinely re-serialize a body and reorder keys. Signing raw bytes would reject
  payloads that are in fact untouched.

  New: `qbitflow.verify_webhook_signature`, `compute_webhook_signature`, `canonical_json`
  and `extract_webhook_headers`, all exported from the package root.
  `extract_webhook_headers` accepts any mapping, so Flask, Django, FastAPI/Starlette and a
  plain dict all work.

- **Header extraction helpers.** Reading the QBitFlow headers is framework-dependent, so
  the SDK accepts anything header-shaped and does a case-insensitive lookup, returning the
  signature, timestamp, transaction id, and whether this is the dashboard's connectivity
  test (which you can acknowledge immediately without processing).

- **`transaction_status.get_websocket_url()`** — builds the `ws(s)://` URL for the status
  WebSocket (deriving the scheme from the configured base URL) so Python has parity with
  the Go SDK. The SDK deliberately does not open the socket: that would add a WebSocket
  dependency every user pays for, and the right client differs between asyncio, threads and
  a WSGI worker.

### Fixed — validation parity with the API

- **An empty optional field now counts as "not provided"**, matching the API. Session
  checkout's `productName`, `description`, `successUrl` and `cancelUrl` are all
  `binding:"omitempty,..."` on the server, which skips validation for an empty value. The
  SDK previously rejected an explicit empty string, so the common
  `successUrl: <env var> || ""` pattern failed locally on a request the API would have
  accepted. Non-empty values are validated exactly as before.

### Changed — examples

- The FastAPI example (`examples/server.py`) now uses `extract_webhook_headers` and
  `verify_webhook_signature`, verifying locally when `QBITFLOW_WEBHOOK_SECRET` is set and falling
  back to the API otherwise.

### Added — client-side request validation

- Session checkout now mirrors the API's `producttext` rule (markup characters rejected,
  2-100 for an inline product name and 2-500 for its description) and requires redirect
  URLs to be absolute `http(s)`. Invalid input fails immediately instead of after a
  round-trip, and a `javascript:` redirect target is refused outright — the API's own `uri`
  rule is more permissive than this.

### Fixed

- **`CreatePaymentSessionDto` now validates `product_name` and `description`** against the
  API's `producttext` rule. Whole-number floats are also normalised when canonicalising
  webhook payloads (`1.0` renders as `1`), matching how Go re-encodes JSON numbers — without
  this, Python would compute a different signature for an identical payload.

### ⚠️ Breaking changes

- **`UpdateProductDto` fields are now all optional** (`name`, `description`, `price`).
  Updates are partial: unset fields are excluded from the request and keep their stored
  value. Previously all three were required, which made partial updates impossible.
- **`UpdateCustomerDto.reference` has been removed**, and `name`/`last_name`/`email` are
  now genuinely optional. They were declared `Optional[...] = Field(...)` — the Ellipsis
  made them **required** despite the docstring promising otherwise. A customer reference
  is immutable and the API ignores it on update.
- **`UpdateUserDto` fields are now all optional and `password` has been removed.** Changing
  a password is a JWT-only, self-service operation that cannot be performed with an API
  key; the API silently ignores it and still returns `200`, so the field was misleading.
  A non-admin caller sending `organization_fee_bps` is now rejected with `403`.
- **`CreateProductDto.price` now requires a value greater than 0** (was `ge=0`), matching
  the API, which rejects a price of 0. `name` and `description` now enforce the API's
  2-100 and 2-500 character bounds.

### Fixed

- **Subscription sessions no longer raise on retrieval.** `SubscriptionSession.tx_type` was
  typed `TransactionShortType`, but the API returns the long form `createSubscription`.
  Pydantic validates enums strictly, so `get_session()` raised a `ValidationError` for every
  subscription session. It is now `TransactionType`.
- **A user update no longer silently resets `organization_fee_bps` to 0.** `users.update()`
  serialized with a plain `model_dump()`, so the field's `default=0` was transmitted on
  every call even when the caller never set it. Updates now use `exclude_none=True`, and
  the field defaults to `None`.
- **`products.update()` no longer sends `null` for unset fields**, for the same reason.
- **`on_behalf_of(0)` no longer sends an invalid header.** `On-Behalf-Of` is now omitted for
  `0` (and any non-positive value), which is what "act at the organization level" means.
  Previously it sent `On-Behalf-Of: 0`, which the API rejects with `400`.

### Added

- **`Product.test`, `Product.organization_id`, `Product.user_id`** and **`Customer.test`** —
  returned by the API but previously absent from the models.
- Integration coverage for partial customer updates and for an empty update body being a
  no-op.

### Changed

- Fixed two test fixtures that hardcoded values the API requires to be unique
  (`reference="TEST-001"` and `email="updated@example.com"`), so they collided with the
  previous run and failed with `400` on every rerun after the first.

## [2.0.0] - 2026-09-13

Major release aligning the SDK with the current QBitFlow API. The API base URL is
unchanged (`/v1`); only the SDK version changes.

### ⚠️ Breaking changes

- **Typed payment metadata.** `PaymentMetadata` is now a structured model
  (`fee_bps`, `organization_fee`, `referral_fee`, `tx_metadata`, `tx_amounts`) instead of
  an opaque dict. `Payment.metadata`, `CombinedPaymentItem.metadata`, and
  `SubscriptionHistory.metadata` are now `Optional[PaymentMetadata]`; `RefundEntry.metadata`
  is now `Optional[TxMetadata]`.
- **`SessionCheckout.available_currencies` is now `list[int]`** (currency IDs) instead of
  a list of `Currency`. Resolve details via the new `client.currencies` service.
- **`Subscription.allowance` is now a `str`** (decimal) instead of `float`, to preserve
  precision.
- **`ApiKey.expires_at` is nullable** (`None` when the key never expires).
- **Removed `api_keys.create` / `api_keys.delete`** (and the `CreateApiKeyDto` /
  `CreatedKeyResponse` models). API-key management is a JWT-only API operation and cannot
  be performed with an API key; manage keys from the dashboard. Read access
  (`get_all`, `get_for_user`) is unchanged.
- **Removed `pay_as_you_go.create_session`** — PAYG session creation is disabled on the API.
  Existing PAYG subscriptions can still be retrieved and managed (`get`, `get_session`,
  `get_by_reference`, `get_payment_history`, `force_cancel`, `execute_test_billing_cycle`).

### Added

- **`client.currencies` service** — `get_all_available(test=False)` and
  `get_all_main(test=False)` (public `/utils/all-*-currencies` endpoints) to resolve
  currency IDs.
- **Authenticated-only fields** now modeled where the API returns them under
  authentication: `organization_id` / `user_id` on `Customer`, `Payment`, and
  `SubscriptionHistory`; `settlement_details` on `TransactionStatus`; `user_name` and
  `tx_type` on session checkouts.
- **`User.claimed_at`** — set once an invited user has claimed their account.
- **`UpdateCustomerDto.reference`** — update a customer's reference.
- Expanded enums: `TransactionType` (`transfer`, `tokenTransfer`,
  `refund`, `faucet`, `claimFunds`), new `TransactionShortType`, and the `years`
  duration unit.

### Changed

- User `organization_fee_bps` validation range widened to `0–5000` bps, matching the API.

## [1.3.1] - 2026-08-25

### Added

- **Act for user**: `BaseRequest.on_behalf_of(userID: string)` temporarily act as a different user
  for the duration of a request. This is useful for admin-level operations that need to be performed
  on behalf of another user.
- **`users.get_by_email(email)`** — retrieve a user by their email address 

## [1.3.0] - 2026-08-17

### Added

- **Reference-based lookups** — resolve resources by the reference you assigned instead of storing
  QBitFlow's internal UUIDs:
  - `one_time_payments.get_by_reference(reference)` — `GET
    /transaction/payment/reference/:paymentReference`
  - `subscriptions.get_by_reference(reference)` — `GET
    /transaction/subscription/reference/subscription/:subscriptionReference`
  - `customers.get_by_reference(reference)` — `GET /customer/reference/:reference`
- **Your own references on session creation** — `one_time_payments.create_session()` and
  `subscriptions.create_session()` now accept:
  - `reference` — your own transaction reference (e.g. order/invoice ID), echoed back on the
    resulting object and in webhooks
  - `product_reference` — select a product by your own reference (alternative to `product_id`)
  - `customer_reference` — select an existing customer by your own reference (alternative to
    `customer_uuid`); a new customer is created during checkout if none matches

### Changed

- **`subscriptions.create_session()` no longer requires `product_id`** — provide either `product_id`
  or `product_reference` (relaxes the 1.2.0 requirement).
- **`Payment.reference`** and **`Subscription.reference`** — added; the reference you set when
  creating the session.
- **`OneTimePaymentSession` / `SubscriptionSession` / `PaygSubscriptionSession`** — added
  `reference`, `product_reference`, and `customer_reference`, so session responses and transaction
  webhook payloads expose the references you provided.
- **`SubscriptionStatusTransitionWebhook.subscription_reference`** — added; the subscription's
  reference is now included on status-transition webhooks.

## [1.2.1] - 2026-07-18

- Removed `webhook_url` from `one_time_payments.create_session()` and
  `subscriptions.create_session()`. Webhook URLs are now set at the settings level in the QBitFlow
  dashboard, and cannot be overridden per session. This change simplifies session creation and
  ensures consistent webhook handling across all transactions.
- Added webhooks for subscription status transitions. The new webhook payload includes
  `subscription_uuid`, `previous_status`, `current_status`, and `updated_at` fields, allowing
  clients to track subscription lifecycle events more effectively.
- Also added a test webhook ID for webhook endpoint reachability checks from the frontend "Test
  webhook" action. This test sends a fake payload to the configured URL, which some SDKs may not
  parse like a real webhook. If the incoming webhook ID matches `TEST_WEBHOOK_ID`, handlers should
  return HTTP `200` immediately and skip normal payload processing.

## [1.2.0] - 2026-05-04

### Breaking Changes

-   **Session checkout split**: `one_time_payments.create_session()` now calls
    `POST /transaction/session-checkout/new/payment` and
    `subscriptions.create_session()` calls `POST /transaction/session-checkout/new/subscription`.
    The old unified `POST /transaction/session-checkout/` endpoint is no longer used.
-   **`subscription.create_session()` now requires `product_id`**: subscriptions must
    reference an existing product; inline `product_name`/`description`/`price` are not
    supported for subscriptions.
-   **`CombinedPayment` renamed to `CombinedPaymentItem`**: the model was rebuilt to match
    the updated API response shape. Import path: `qbitflow.dto.transaction.payment`.
-   **`pay_as_you_go` client property removed**: PAYG support is temporarily disabled on the
    API side and will be re-enabled in a future release.
-   **Transaction status query params renamed**: the underlying API now uses `txUUID` and
    `txType` (was `transactionUUID` and `transactionStatusType`). The Python method
    signature `transaction_status.get(transaction_uuid, transaction_type)` is unchanged.
-   **`Session` and `SubscriptionOptions` removed**: replaced by three concrete types —
    `OneTimePaymentSession`, `SubscriptionSession`, and `PaygSubscriptionSession`, all
    extending the new `BaseSession`. `get_session()` on each handler now returns the
    specific type for that handler. `SessionWebhookResponse.session` is typed as
    `AnySession` and resolved automatically from the response payload. `BaseSession` also
    exposes the previously missing server-set fields: `organization_id`, `fee_bps`,
    `organization_fee_bps`, `user_id`, `test`, `webhook_url`.

### Added

-   `client.refunds` (`RefundRequests`) — retrieve active and inactive refunds:
    -   `get_all() -> List[RefundEntry]`
    -   `get_all_inactive(limit, cursor) -> CursorData[RefundEntry, str]`
    -   `get_by_transaction(transaction_uuid) -> RefundEntry` (public endpoint)
-   `client.accounting` (`AccountingRequests`) — export transaction data:
    -   `export(from_date, to_date, format) -> List[AccountingEvent] | str`
    -   Supports `format="json"` (parsed objects) and `format="csv"` (raw string)
-   `client.claim` (`ClaimRequests`) — account claim and fund management:
    -   `create_request(user_id) -> CreateClaimRequestResponse` (admin)
    -   `get_request(user_id) -> CreateClaimRequestResponse` (admin)
    -   `get_funds() -> List[ClaimFund]`
    -   `trigger_test_claim_funds(user_id) -> SuccessResponse` (test mode only)
-   `one_time_payments.get_customer_for_transaction(transaction_uuid) -> Customer`
-   `session.get_session(..., close_to_expire_error)` — optional parameter now exposed
-   New DTOs: `RefundEntry`, `RefundStatus`, `AccountingEvent`, `ClaimRequest`,
    `Organization`, `ClaimRequestInfo`, `CreateClaimRequestResponse`, `ClaimFund`,
    `CreatePaymentSessionDto`, `CreateSubscriptionSessionDto`
-   `BaseRequest._make_raw_request()` — internal method for non-JSON responses (CSV export)

### Fixed

-   `Payment` and `SubscriptionHistory` now include `amount_min_units` (decimal string)
    and `metadata` fields from the API response.
-   `CombinedPaymentItem` correctly models the combined payments endpoint response,
    including `source`, `amount_min_units`, and optional `subscription_uuid`.

## [1.1.0] - 2026-03-08

### Added

-   HMAC signature verification for webhook requests
-   New `verify` method in `WebhookRequests` class
-   Updated documentation with webhook verification examples

### Security

-   Improved HMAC signature verification process
-   Enhanced input validation for webhook requests

## [1.0.0] - 2025-10-23

### Added

-   Initial release of QBitFlow Python SDK
-   One-time cryptocurrency payment processing
-   Recurring subscription management
-   Pay-as-you-go subscription support
-   Customer management (create, read, update, delete)
-   Product management (create, read, update, delete)
-   Transaction status tracking
-   Webhook support for payment notifications
-   Redirect URL handling (success/cancel)
-   Comprehensive error handling with custom exceptions
-   Full type hints for better IDE support
-   Detailed docstrings with examples
-   Input validation throughout
-   Pagination support for list operations
-   Configurable timeout and retry settings
-   Integration tests
-   Complete documentation and examples

### Security

-   Secure API key-based authentication
-   Input validation to prevent malformed requests
-   HTTPS-only API communication
