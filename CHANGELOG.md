# Changelog

All notable changes to the QBitFlow Python SDK will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [2.5.0] - 2026-09-23

Aligns the SDK with docs revision `5e7d5a5` and with the behavioural contract shared by the Go,
JavaScript, Python and PHP SDKs: one retry policy, one error taxonomy, one client-side
validation rule set and one response-typing contract.

> **⚠️ Breaking changes in a minor release.** They are listed under **Removed** and
> **Changed (breaking)** below. Semver-aware resolvers treat `2.5.0` as a safe upgrade
> from any `2.x`, so `^2` / `~2.1` constraints will pick it up automatically — review
> before updating, or pin.

**Headline:** response models are now typed exactly as the Go API serializes them, and they
never raise on a response the API legitimately sends. Several 2.1.0 methods could not succeed
against the real API — `subscriptions.execute_test_billing_cycle()` expected a `statusLink` the
API never sends, `refunds.get_by_transaction()`, `api_keys.get_all()` (organization-level keys)
and `transaction_status.get()` (before a transaction is broadcast) raised on valid responses,
and `one_time_payments.on_behalf_of(...)` raised `TypeError` before sending anything. All of
them work now.

### Removed

-   **Pay-as-you-go** — `PayAsYouGoSubscriptionRequests`, `PayAsYouGoSubscription`,
    `PaygSubscriptionSession`, and the PAYG arm of the session discriminator. The API has no
    PAYG routes. The PAYG members of `TransactionType` and `TransactionShortType` are **kept** —
    a transaction record can still carry them.
-   **`LinkResponse.expires_at`** — the API's `LinkResponse` is exactly `{link, uuid}`.
-   **`ClaimRequest`**, **`StatusLinkResponse`**, **`StatusResponse`** and
    **`SubscriptionStatusTransitionWebhook`** — types no route returns (the subscription webhook
    is now `SubscriptionWebhook`, see below).
-   **The `email-validator` dependency.** Request DTOs no longer use pydantic's `EmailStr`
    (see *Client-side validation*).
-   **WebSocket status URL helper removed** — `transaction_status.get_websocket_url()` (added
    in 2.1.0). `/transaction/status/ws` is an internal endpoint for the QBitFlow checkout page
    (it rejects non-frontend origins). Use webhooks, or poll `transaction_status.get()`. The
    unused `StatusResponseError` model, which described no REST response, is removed with it.
-   **The local three-month limit on `accounting.export()`.** The API decides how long a window
    it accepts (the documented three-month rule does not match the server); a refused window is
    the API's `400`, raised as `ValidationError`.

### Changed (breaking)

-   **Response typing follows the Go server types.** Every response model derives from the new
    `qbitflow.dto.ResponseModel` and decodes the way Go's `encoding/json` does:
    -   a non-pointer field that is absent or `null` decodes to its zero value (`0`, `""`,
        `False`, `[]`, a zero-valued nested object, or `GO_ZERO_TIME` = `0001-01-01T00:00:00Z`)
        instead of raising or being `None`;
    -   only pointer fields are `Optional`;
    -   a field present with the wrong JSON type raises `ServerError` carrying the HTTP status;
        numeric widening (an integer into a float field, an integral float into an int field)
        is accepted; unknown keys are ignored;
    -   response-side range constraints (`ge`/`gt`) are gone — values are reported as sent.

    Field changes against 2.1.0:
    -   now **non-null with a zero default** (were `Optional`): `Payment.amount_min_units`,
        `.product_id` (`0` for an inline product), `.organization_id`, `.user_id`, `.metadata`;
        `CombinedPaymentItem.amount_min_units`; `Subscription.last_billing_date` (`GO_ZERO_TIME`
        before the first billing), `.organization_id`, `.user_id`;
        `SubscriptionHistory.amount_min_units`, `.product_id`, `.organization_id`, `.user_id`,
        `.metadata`; `RefundEntry.merchant_message` and `.tx_hash` (`""` until set),
        `.amount_min_units`; `TransactionStatus.message`; `TxMetadata.main_currency_price_usd`;
        `TxAmountsUSD.organization` / `.referral`; `Customer.phone_number`, `.address`,
        `.reference` (`""`), `.organization_id`, `.user_id` (`0` for organization-level
        customers); `Product.reference`; the session fields `reference`, `product_id`,
        `product_reference`, `success_url`, `cancel_url`, `organization_id`, `fee_bps`,
        `organization_fee_bps`, `user_id`, `user_name`, `customer_reference`, and
        `SubscriptionSession.trial_period` / `.min_periods`.
    -   now **`Optional`** (pointers in the API; were required): `Payment.customer_uuid`,
        `Subscription.customer_uuid`, `SubscriptionHistory.customer_uuid`,
        `SessionWebhookResponse.status`.
    -   **`currency` is a `Currency` object** on `Payment`, `CombinedPaymentItem` (was
        `Optional`), `Subscription` and `SubscriptionHistory`; `Currency.main_currency` stays
        `Optional`.
    -   **defaults instead of raising when absent:** `ApiKey.user_id` (`0` for an
        organization-level key), `TransactionStatus.tx_hash` (`""` until broadcast),
        `SessionWebhookResponse.management_page_link` and
        `SubscriptionWebhook.subscription_reference` (`""`), the session's product fields.
    -   **unknown enum values are preserved:** `TransactionStatus.status`,
        `Subscription.subscription_status`, `User.role`, `ApiKey.role`, `RefundEntry.status`,
        session/webhook `tx_type`, `SubscriptionWebhook.type` and the transition statuses are
        `Union[<Enum>, str]` — a value this SDK does not know yet stays a plain `str`.
    -   response `email` fields are plain `str`.
-   **HTTP status mapping.** `400`/`422` raise `ValidationError` — the same type as client-side
    validation; `401` `AuthenticationError`; `403` `ForbiddenException`; `404`
    `NotFoundException`; `409` the new `ConflictError`; `429` `RateLimitError` with
    `retry_after`; other 4xx `InvalidRequestError`; `5xx`, a `3xx`, an empty or non-JSON `2xx`
    body (a `204` is not an error) and a response of the wrong shape raise the new
    `ServerError` (a subclass of `APIError`). Every exception carries `status_code` (whenever a
    response was involved) and `fields`. A CSV export's JSON error body is parsed the same way.
-   **Retry policy.** Only `GET` is retried — on any transport failure (connection,
    read/write, timeout, and protocol errors such as "server disconnected") and on `5xx` —
    with exponential backoff (1s, 2s, 4s). `POST`/`PUT`/`DELETE` are never retried; the action
    `GET`s `force_cancel()`, `execute_test_billing_cycle()` and `trigger_test_claim_funds()`
    are non-retriable; `4xx`, `429`, `3xx` and configuration errors (a `base_url` without a
    scheme) are never retried. 2.1.0 retried every verb on timeouts and never retried `5xx`.
    Redirects are never followed.
-   **Client settings.** `max_retries=0` and `timeout=0` are honoured (2.1.0 replaced them with
    the defaults); a negative or non-numeric value raises `ValidationError`, validated before
    the connection pool is opened. A blank or whitespace-only API key raises `ValueError`.
    `config.set_base_url("")` raises `ValidationError`.
-   **Client-side validation mirrors the API's `binding` rules, and always raises the SDK's
    `ValidationError`** (with `fields`) — including when a request DTO is constructed; 2.1.0
    raised `pydantic.ValidationError` from DTOs. DTOs are validated again when handed to a
    request method, and request methods also accept a plain mapping of the DTO's fields.
    -   names (`CreateCustomerDto` / `UpdateCustomerDto` / `CreateUserDto` / `UpdateUserDto`)
        follow `alphanumspace`: Unicode letters, decimal digits only (`²`, `Ⅻ` are rejected),
        spaces and `- _ ' .`, 2–100 characters (2.1.0: minimum 1, anything allowed);
        a whitespace-only name is accepted, as the API accepts it;
    -   product name/description follow `producttext` (not blank, no markup or control
        characters, 2–100 / 2–500 code points); a price must be a finite number greater than 0;
        an empty `name` or `description` on update is rejected;
    -   email addresses use one structural rule everywhere and are sent exactly as given (2.1.0's
        `EmailStr` lower-cased the domain and rejected valid addresses such as `a@shop.test`);
    -   session creation: an inline `price` must be greater than 0; `customer_uuid` must be a
        bare UUID; redirect URLs must be absolute `http(s)` URLs (scheme case-insensitive, host
        required); an empty optional string means "not provided" and is omitted;
    -   subscriptions: `frequency.value` is an integer from 1 to 4294967295 with a known unit;
        `trial_period.value` may be 0; `min_periods` is an integer from 0 to 4294967295 (0 is
        omitted). `Duration` itself now accepts a value of 0 (for trial periods);
    -   `CreateUserDto.role` accepts only `admin` or `user`; `organization_fee_bps` is an
        integer from 0 to 5000;
    -   `""` for `name` / `last_name` / `email` on the update DTOs means "not provided";
    -   `accounting.export()` checks real `YYYY-MM-DD` dates, `from <= to` and the format;
    -   identifiers must be non-empty strings / positive integers; a cursor `limit` must be a
        positive integer; an empty `cursor` is omitted.
-   **`subscriptions.execute_test_billing_cycle()` returns `SuccessResponse`** (the API's
    `{message}`), like `force_cancel()`. A subscription that is not yet due raises
    `ConflictError`.
-   **Session getters.** `get_session(...)` no longer sends `closeToExpireError=false` by
    default (pass the argument to opt in either way). `one_time_payments.get_session()` raises
    `ValidationError` for a subscription session and `subscriptions.get_session()` for a
    one-time session, instead of returning the other type under the wrong annotation.
-   **Subscription webhooks use the documented envelope.** `SubscriptionWebhook` carries
    `subscription_uuid`, `subscription_reference`, a `type`, and the payload in `data` — a
    `SubscriptionStatusTransition`, a `SubscriptionHistory`, or the raw `dict` for an unknown
    `type`.
-   **`on_behalf_of()`** accepts only a non-negative integer (a negative id, `True`, a float or
    a string raises `ValidationError`); `0` means "act at the organization level" (no header).
-   **`webhooks.verify()`** accepts the raw body (`bytes`/`str`) or an already-decoded JSON
    value; invalid JSON and `NaN`/`Infinity` raise `ValidationError`; it returns `False` only
    for the API's `400` and lets every other failure propagate as its own type.
-   **Local webhook verification** parses the timestamp like Go's `strconv.ParseInt` (ASCII
    digits with an optional sign, no whitespace, within int64); a replay window of `0` or less
    means the default 300 seconds; lone surrogates in the payload become U+FFFD, as the Go
    server decodes them.
-   **`pydantic>=2.2`** is required (2.2 is the first release with `Field(union_mode=...)`,
    which keeps unknown enum values).

### Deprecated

-   `client.claim` → **`client.claims`** and `claims.get_request()` →
    **`claims.get_request_by_user()`**. The old names are aliases (the same object / the same
    behaviour) that emit a `DeprecationWarning`.

### Added

-   **Client-level On-Behalf-Of:** `client.on_behalf_of(user_id)` returns a client whose every
    service sends `On-Behalf-Of`, sharing the root client's connection pool and settings (close
    only the root client). The per-service `on_behalf_of()` remains.
-   **`base_url` on the client**: `QBitFlow(api_key, base_url=...)`, threaded to every
    handler, the nested session handlers and scoped copies; a trailing slash is stripped.
    `client.base_url` exposes the effective value.
-   **One shared `httpx.Client`** per `QBitFlow` instance (was: a new client per request),
    with `close()` and context-manager support.
-   **`User-Agent: qbitflow-python/<version>`** on every request.
-   **`ConflictError`**, **`ServerError`**, **`ForbiddenException`**, **`FieldError`** and
    `error.fields` on every error type; **`RateLimitError.retry_after`** in seconds, from either
    a delta-seconds or an HTTP-date `Retry-After` (`None` when absent).
-   **Webhook payload parsing:** `parse_session_webhook(body)` and
    `parse_subscription_webhook(body)` decode a verified delivery with the response policy and
    raise `ValidationError` for a malformed body. `extract_webhook_headers()` now returns a
    `WebhookHeaders` `TypedDict`.
-   **Typing:** `on_behalf_of()` returns the handler's own type; `accounting.export()` is
    overloaded (`List[AccountingEvent]` for `"json"`, `str` for `"csv"`); `model_dump()` /
    `model_dump_json()` are typed and emit camelCase keys by default.
-   `GO_ZERO_TIME`, `qbitflow.dto.RequestModel` / `ResponseModel`,
    `qbitflow.dto.accounting.ACCOUNTING_EVENT_TYPES` (both spellings of the subscription-billing
    event type: `subscriptionHistory` and `subHistory`), and `WebhookRequests` in
    `qbitflow.requests`.
-   **`UserRole.HANDLE`**, **`RefundEntry.user_id`**, **`SubscriptionSession.upgrading_from_trial`**.
-   **Inline ghost products on subscription sessions:** `subscriptions.create_session()` accepts
    `product_name` / `description` / `price`.
-   `HEADER_SIGNATURE`, `HEADER_TIMESTAMP`, `HEADER_WEBHOOK_ID`, `TEST_WEBHOOK_ID` and
    `DEFAULT_MAX_TIMESTAMP_AGE_SECONDS` are exported from the package root.

### Fixed

-   **`on_behalf_of()` raised `TypeError` on payments and subscriptions**; the scoped header
    now also reaches the nested session handler, so `get_session` is impersonated too.
-   **`validate_url` rejected URLs the API accepts** (a TLD longer than 6 characters, an
    internal host without a dot). It now mirrors the API's `http_url` rule.
-   **Only the first validation failure was reported**; every field now appears in the message
    and in `error.fields`.
-   **`webhooks.verify()` flattened error types** into `APIError`; a non-JSON payload raised a
    bare `json.JSONDecodeError`.
-   **User-supplied path segments were not escaped** — uuids, references and emails are now
    percent-encoded, so `?`, `#` or `%` in a reference no longer change the request. The API
    currently cannot route a reference containing `/` even when it is escaped (404).
-   **Request bodies that cannot be encoded** (`NaN`, a lone surrogate) raise `ValidationError`
    instead of an untyped exception; unset optional fields are omitted instead of sent as
    `null`.
-   **Error-message extraction** prefers `error`, then the joined `errors[]`, then `message`,
    then the raw non-JSON body, then the HTTP status text.

### Documentation

-   README: response-typing section, client-level `on_behalf_of`, retry list including the
    claim-funds test trigger, base-URL precedence, validation rules, webhook examples that
    verify the signature before short-circuiting the dashboard probe and parse with the new
    helpers, error table, live-test environment rules.
-   Examples read the API key (and an optional customer UUID) from the environment, use a
    one-month accounting window, and the example server never echoes query input.

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
