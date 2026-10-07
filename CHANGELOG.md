# Changelog

All notable changes to the QBitFlow Python SDK will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.0.0] - 2026-10-08

The SDK for **QBitFlow API v2**, aligned with the API docs `v2` @ `58460e9` and with the
behaviour contract the Go, JavaScript, Python and PHP SDKs 3.0.0 share (same services, methods,
errors, retries and webhook verification; checked against the shared conformance vectors). A
major release: the client, the services and most names change. [MIGRATION-v3.md](MIGRATION-v3.md)
maps every 2.x method and type to its replacement.

This entry describes the changes since 2.1.0, the last published release (2.5.0 was prepared but
never published; its changes are part of 3.0.0).

### ⚠️ Breaking

-   **API v2**: the default base URL is `https://api.qbitflow.app/v2`. API v1 runs next to it,
    against the same data, for a transition period.
-   **The client.** `QBitFlow(api_key, *, base_url=None, timeout=None, max_retries=None,
    on_behalf_of=None, http_client=None)`: keyword-only options, `timeout` per attempt in seconds,
    an injectable `httpx.Client`, context-manager support and `close()`. The key must be
    non-blank and start with `sk_` (a `ValidationError` otherwise, instead of `ValueError`;
    nothing is sent). `client.me()` describes the key. `client.on_behalf_of(user_uuid)` returns
    a client acting in a member's space (it replaces the per-service `on_behalf_of`).
-   **Services and methods** follow the shared surface: `checkout_sessions`, `payments`,
    `failures`, `subscriptions`, `refunds`, `products`, `customers`, `members`, `invitations`,
    `wallets`, `accounting`, `webhooks` (+ `.endpoints`, `.events`), `currencies`. Every method
    takes **keyword-only arguments** (path ids positional) and `options=RequestOptions(...)`
    last (`on_behalf_of`, `idempotency_key`, `request_id`). The `Create…Dto` / `Update…Dto`
    request classes are gone.
-   **Checkout sessions have their own service.** `one_time_payments.create_session` and
    `subscriptions.create_session` → `checkout_sessions.create_payment` / `create_subscription`
    (returning a `CheckoutSession`: `uuid`, `link`, `expires_at`). `transaction_status.get` →
    `checkout_sessions.get_status(uuid)` with four statuses (`created`, `waitingConfirmation`,
    `completed`, `expired`): a failed attempt is `created` with `last_attempt` set, never final.
    `checkout_sessions.expire` is new. The session getters (`get_session`) are removed.
-   **Ids are UUID strings.** Products are named by `uuid` (was the numeric `id`), and
    `product_id` is `product_uuid` everywhere; people are named by their user UUID.
    `organization_id` is gone from every model. Currencies keep numeric ids.
-   **Users and claims become invitations, members and the trust layer**: `users.*` →
    `invitations.*` and `members.*`; `claim.*` → `members.trust` and the held-funds reads.
    `api_keys.*` is removed (keys are managed in the dashboard; `client.me()` describes the
    current key).
-   **Subscriptions.** `status` takes `trial`, `trialExpired`, `active`, `pastDue`, `paused`,
    `stopped`, `cancelled`; `low_on_funds` and `pending` became `action_required` values. The
    frequency is a `Duration`. `force_cancel` → `cancel(uuid, immediate=…)` (a POST, returning a
    `SubscriptionCancellation` with `pending` for an HTTP 202); `execute_test_billing_cycle` →
    `execute_test_billing` (returns the bill's `BillingState`); `get_payment_history` →
    `list_bills` / `iterate_bills`, or `get_public_history`; `get` returns cancelled
    subscriptions too.
-   **Refunds.** `get_all` → `list`, `get_all_inactive` → `list_inactive` / `iterate_inactive`;
    `get_by_transaction` is removed; `initiate` is new (a pending refund signed in the dashboard).
-   **Payments.** `one_time_payments.get_all` → `payments.list` / `iterate` (with filters),
    `get_all_combined` → `list_combined` / `iterate_combined`; `get_customer_for_transaction`
    is removed (payments carry their `customer`). `failures.list` is new.
-   **Accounting.** `export(from_date, to_date, format)` → `export_json(from_date, to_date)` and
    `export_csv(from_date, to_date)` (dates as `YYYY-MM-DD` strings or `datetime.date`s).
-   **Currencies.** `get_all_available` / `get_all_main` → `list_available` / `list_main`;
    `get(id)` is new.
-   **Models** are pydantic v2 models with **explicit per-field wire aliases** (the 2.x alias
    generator, which produced `customerUUID`, is gone) and snake_case attributes:
    `LinkResponse` → `CheckoutSession`, `TransactionStatus` → `CheckoutSessionStatus`,
    `SubscriptionHistory` → `Bill`, `RefundEntry` → `Refund`, `CombinedPaymentItem` →
    `CombinedPayment`, `User` → `Member`, `UserRole` → `Role`, `CursorData` → `Page`
    (`has_more` is a property), `TxAmountsFull` → `TxAmounts`, `TxAmountsUSD` → `TxAmountsUsd`;
    `transaction_hash` → `tx_hash`; the wire's `from` is `from_`. Fee rates are percents
    (`fee_bps` → `fee_percent`). Everything is importable from `qbitflow`; the `qbitflow.dto`
    package is gone.
-   **Decoding policy**: an absent or `null` value of a non-optional field decodes to its zero
    value (`ZERO_TIME` for a timestamp); a value of the wrong JSON type is a `ServerError`;
    unknown enum values are kept as raw strings; timestamps are aware `datetime`s with any offset.
-   **Errors.** One class per condition, all deriving from `QBitFlowError` and `ApiError`
    (`status`, `code`, `message`, `details`, `request_id`, `field_errors`, `raw_body`):
    `ValidationError` (400 `validation_failed` and client-side checks), `BadRequestError`,
    `AuthenticationError`, `PermissionDeniedError` (was `ForbiddenException` in 2.5.0),
    `NotFoundError` (was `NotFoundException`), `ConflictError`, `GoneError`, `IdempotencyError`,
    `RateLimitError` (`retry_after`, `limit`, `period_seconds`), `ServerError`, `NetworkError`,
    `WebhookSignatureError`. `APIError` → `ApiError`; `InvalidRequestError` is removed. The
    `qbitflow.exceptions` package is gone: import the errors from `qbitflow`.
-   **Webhooks** use API v2's scheme: the `QBitFlow-Signature: t=…,v1=…` header, an
    HMAC-SHA256 of `t + "." + raw_body` over the raw body (no canonical JSON), and the event
    envelope (`id`, `type`, `version`, `created_at`, `test`, `user_uuid`, `data`).
    `verify_webhook_signature`, `compute_webhook_signature`, `canonical_json`,
    `extract_webhook_headers`, the `X-Webhook-*` header constants, `TEST_WEBHOOK_ID` and
    `client.webhooks.verify(payload, signature, timestamp)` are replaced by
    `qbitflow.webhooks.verify` / `construct_event` / `parse_event` (raising
    `WebhookSignatureError` with a `reason`) and `client.webhooks.verify_remote`. v1 webhook
    payloads are not parsed (a `ValidationError`: move the endpoint to v2).

### Added

-   `client.me()`; `client.on_behalf_of(user_uuid)`; `RequestOptions`.
-   **Services**: `checkout_sessions` (`create_payment`, `create_subscription`, `get_status`,
    `expire`), `failures.list` / `iterate`, `members` (`list`, `iterate`, `get`, `update`,
    `remove`, `trust`, `list_held_funds`, `get_held_funds`, `get_own_held_funds`), `invitations`
    (`create`, `list`, `iterate`, `revoke`), `wallets` (`list`, `list_for_member`,
    `list_supported_currencies`), `webhooks.endpoints` (`list`, `create`, `get`, `update`,
    `delete`) and `webhooks.events` (`list`, `iterate`, `get`), `refunds.initiate`,
    `subscriptions.get_bill`, `currencies.get`.
-   **Iterators** for every paginated list (`iterate`, `iterate_combined`, `iterate_bills`,
    `iterate_inactive`): lazy, one request per page, filters kept.
-   **Typed webhook events**: one class per event type (`PaymentCompletedEvent`, …,
    `WebhookTestEvent`) in the `Event` discriminated union, `UnknownEvent` for new types.
-   **Retries for the 7 creates** with an `Idempotency-Key` generated per call and reused on
    every retry (`RequestOptions(idempotency_key=…)` to set your own), on network errors, 5xx,
    429 (honouring `Retry-After`, up to 60 s) and 409 `idempotency_key_in_use`. `is_retryable`.
-   **Client-side validation** of every input (the API's rules: names, texts, references,
    emails, phones, URLs, prices, percents, durations, ids, dates, exclusive filters, argument
    types), raising `ValidationError` with wire field names before anything is sent.
-   `X-Request-Id` (`RequestOptions(request_id=…)`), echoed as `request_id` on errors.
-   `NOT_GIVEN`: the default of the clearable update fields (`""` or `None` clears them).
-   `qbitflow.__version__` single-sourced in `qbitflow/_version.py`; `User-Agent:
    qbitflow-python/3.0.0`.

### Changed

-   Requires `pydantic>=2.5` (callable discriminators for the event union).
-   Redirects are never followed (a 3xx is a `ServerError`).
-   Error bodies are parsed on every route (the CSV export included), and field errors come from
    `details.errors` (2.x read a top-level `errors` and lost them).
-   Request bodies that JSON cannot represent (NaN, infinities, unpaired surrogates) are refused
    with a `ValidationError` naming the field.

### Removed

-   `users`, `api_keys`, `claim`, `transaction_status`, `one_time_payments` (and its
    `get_session` / `get_customer_for_transaction`), `subscriptions.get_session`,
    `refunds.get_by_transaction`, pay-as-you-go, the WebSocket status URL, canonical-JSON webhook
    verification and the v1 webhook payload models, `qbitflow.config`, `qbitflow.dto`,
    `qbitflow.requests`, `qbitflow.utils`, `qbitflow.exceptions`.

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

- The FastAPI example (`examples/server.py`) now uses `extract_webhook_headers` and `verify_webhook_signature`, verifying locally when `QBITFLOW_WEBHOOK_SECRET` is set and falling back to the API otherwise.

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

- **Act for user**: `BaseRequest.on_behalf_of(userID: string)` temporarily act as a different user for the duration of a request. This is useful for admin-level operations that need to be performed on behalf of another user. 
- **`users.get_by_email(email)`** — retrieve a user by their email address 

## [1.3.0] - 2026-08-17

### Added

- **Reference-based lookups** — resolve resources by the reference you assigned instead of storing QBitFlow's internal UUIDs:
  - `one_time_payments.get_by_reference(reference)` — `GET /transaction/payment/reference/:paymentReference`
  - `subscriptions.get_by_reference(reference)` — `GET /transaction/subscription/reference/subscription/:subscriptionReference`
  - `customers.get_by_reference(reference)` — `GET /customer/reference/:reference`
- **Your own references on session creation** — `one_time_payments.create_session()` and `subscriptions.create_session()` now accept:
  - `reference` — your own transaction reference (e.g. order/invoice ID), echoed back on the resulting object and in webhooks
  - `product_reference` — select a product by your own reference (alternative to `product_id`)
  - `customer_reference` — select an existing customer by your own reference (alternative to `customer_uuid`); a new customer is created during checkout if none matches

### Changed

- **`subscriptions.create_session()` no longer requires `product_id`** — provide either `product_id` or `product_reference` (relaxes the 1.2.0 requirement).
- **`Payment.reference`** and **`Subscription.reference`** — added; the reference you set when creating the session.
- **`OneTimePaymentSession` / `SubscriptionSession` / `PaygSubscriptionSession`** — added `reference`, `product_reference`, and `customer_reference`, so session responses and transaction webhook payloads expose the references you provided.
- **`SubscriptionStatusTransitionWebhook.subscription_reference`** — added; the subscription's reference is now included on status-transition webhooks.

## [1.2.1] - 2026-07-18

- Removed `webhook_url` from `one_time_payments.create_session()` and `subscriptions.create_session()`. Webhook URLs are now set at the settings level in the QBitFlow dashboard, and cannot be overridden per session. This change simplifies session creation and ensures consistent webhook handling across all transactions.
- Added webhooks for subscription status transitions. The new webhook payload includes `subscription_uuid`, `previous_status`, `current_status`, and `updated_at` fields, allowing clients to track subscription lifecycle events more effectively.
- Also added a test webhook ID for webhook endpoint reachability checks from the frontend "Test webhook" action. This test sends a fake payload to the configured URL, which some SDKs may not parse like a real webhook. If the incoming webhook ID matches `TEST_WEBHOOK_ID`, handlers should return HTTP `200` immediately and skip normal payload processing.

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
