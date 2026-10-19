# Changelog

All notable changes to the QBitFlow Python SDK will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.0.0] - 2026-10-19

The SDK for **QBitFlow API v2**, aligned with the final API v2 contract (api-hub `docs/api` @
`fab875c`) and with the behaviour contract the Go, JavaScript, Python and PHP SDKs 3.0.0 share
(same services, methods, errors, retries, validation and webhook verification; checked against the
shared conformance vectors). A major release: the client, the routes, the services and most names
change. [MIGRATION-v3.md](MIGRATION-v3.md) maps every 2.x method and type to its replacement.

This entry describes the changes since 2.1.0, the last published release (2.5.0 was prepared but
never published; its changes are part of 3.0.0).

### ⚠️ Breaking

-   **API v2**: the default base URL is `https://api.qbitflow.app/v2`, with its REST routes:
    plural collections (`/products/:uuid`, `/customers`, `/payments`, `/subscriptions`,
    `/bills/:uuid`, `/refunds`, `/wallets`, `/currencies`, `/checkout-sessions/…`,
    `/payment-failures`, `/transactions`, `/held-funds`), updates as `PATCH`, actions as
    `POST /<resource>/:uuid/<verb>`, lookups by reference as list filters, and every `DELETE`
    answering `204` with no body. `/v1` is gone.
-   **The client.** `QBitFlow(api_key, *, base_url=None, timeout=None, max_retries=None,
    on_behalf_of=None, http_client=None)`: keyword-only options, `timeout` per attempt in seconds,
    `max_retries=0` disables retries, an injectable `httpx.Client`, context-manager support and
    `close()`. The key must be non-blank and start with `sk_` (a `ValidationError` otherwise,
    instead of `ValueError`; nothing is sent). `client.me()` describes the key.
    `client.on_behalf_of(user_uuid)` returns a client acting in a member's space (it replaces the
    per-service `on_behalf_of`); `""` (or `None`) means the organization level, and the
    `On-Behalf-Of` header is then omitted (never sent blank).
-   **Services and methods** follow the shared surface: `checkout_sessions`, `payments`,
    `transactions`, `failures`, `subscriptions`, `refunds`, `products`, `customers`, `members`,
    `invitations`, `wallets`, `accounting`, `webhooks` (+ `.endpoints`, `.events`), `currencies`.
    Every method takes **keyword-only arguments** (path ids positional) and
    `options=RequestOptions(...)` last (`on_behalf_of`, `idempotency_key`, `request_id`). The
    `Create…Dto` / `Update…Dto` request classes are gone.
-   **Ids are UUID strings.** Products are named by `uuid` (was the numeric `id`), and
    `product_id` is `product_uuid` everywhere; people are named by their user UUID (`user_id` →
    `user_uuid`). `organization_id` is gone from every model. Currencies keep numeric ids.
    Transaction ids are prefixed (`pay@`, `sub@`, `sub-hist@`, `refund@`, `transfer@`,
    `release@`) and every route also takes the bare UUID.
-   **Money is a decimal string, never a float**, in requests and in responses: USD amounts
    (`price_usd`, `amount_usd`, `paid_usd`, `total_usd`, `attempted_usd`), token amounts
    (`amount`, `paid`, `owed`, next to their `…_min_units`) and fee rates in percent
    (`fee_percent`, `organization_fee_percent`, `refund_percent`: `"1.5"` is 1.5 %). The money
    inputs (`products.create(price_usd=…)` / `update`, the sessions' inline `price_usd`,
    `FeeItem.amount_usd`, `invitations.create(organization_fee_percent=…)`,
    `members.update(organization_fee_percent=…)`)
    take a `str` or a `decimal.Decimal` (sent as `str(value)`, which must then match the grammar);
    a `float` or an `int` is refused with a `ValidationError` (a float cannot carry `0.1`
    exactly, and the API answers 400 to a JSON number). No float is left in a model.
-   **Amounts are token amounts.** `Payment.amount`, `Bill.amount`, `Transaction.amount` and
    `HeldFundsReleased.amount` are now in the currency's units (`"10"` for 10 USDC), next to
    `amount_min_units` and the new `amount_usd` (what `amount` used to be).
-   **Users and claims become invitations, members and held funds**: `users.*` →
    `invitations.*` and `members.*` (a person exists once they accept an invitation); `claim.*` →
    `members.trust` and the held-funds reads. `api_keys.*` is removed (keys are managed in the
    dashboard; `client.me()` describes the current key).
-   **Checkout sessions have their own service.** `one_time_payments.create_session` and
    `subscriptions.create_session` → `checkout_sessions.create_payment` / `create_subscription`
    (`POST /checkout-sessions/payment` / `subscription`), returning a `CreatedCheckoutSession`
    (`uuid`, `link`, `expires_at`, always set). `transaction_status.get` →
    `checkout_sessions.get(uuid)` (`GET /checkout-sessions/:uuid`), a `CheckoutSessionStatus` with
    four statuses (`created`, `waitingConfirmation`, `completed`, `expired`) and `expires_at` while
    open: a failed attempt is `created` with `last_attempt` set, never final.
    `checkout_sessions.expire` is new. The session getters (`get_session`) are removed.
-   **Subscriptions.** `status` (was `subscription_status`) takes `trial`, `trialExpired`,
    `active`, `pastDue`, `paused`, `stopped`, `cancelled`; `low_on_funds` and `pending` became
    `action_required` values (`topUpAllowance`, `raiseMaximum`, `confirmTrial`), and the `stopped`
    bool the `stopped` status. `frequency` is a `Duration` (was seconds); `last_billing_date` →
    `last_billed_at`, `next_billing_date` → `next_billing_at`, `minimum_cancellation_date` →
    `cancellable_at` (all `Optional[datetime]`); `allowance` is an `Allowance` object (`amount`,
    `amount_min_units`, `amount_usd`, `remaining_periods`, `max_per_period`,
    `max_per_period_min_units`) that absorbs `max_amount_per_period`; `from_`, `product_uuid` and
    `subscription_hash` are `None` when unknown; `currency` is always set; `management_page_link`
    is on the subscription itself. `force_cancel` → `cancel(uuid, immediate=…)`
    (`POST /subscriptions/:uuid/cancel`; `immediate=False` cancels at the end of the paid period;
    returns a `SubscriptionCancellation` with `pending` for an HTTP 202);
    `execute_test_billing_cycle` → `test_bill` (`POST /subscriptions/:uuid/test-bill`, returns a
    `TestBill`: `bill_uuid` `sub-hist@…`, `stage`, `outcome`, `attempts`, `next_attempt_at`);
    `get_payment_history` → `list_bills` / `iterate_bills`; `get` returns cancelled subscriptions
    too.
-   **The settlement.** `Payment.metadata` (the fee split) → `Payment.settlement`, a `Settlement`
    (`fee_percent`, `organization_fee`, `referral_fee`, `split`, `transaction`) on payments, bills,
    transactions and held-funds lines; a `TransferSettlement` on refunds and held-funds releases.
    `PaymentMetadata`, `TxMetadata`, `BlockData`, `NetworkFees`, `TxAmounts`, `TxAmountsMinUnits`
    and `TxAmountsUsd` are replaced by `Settlement`, `Split` (each part a `TokenAmount`;
    `split.platform` no longer includes the referrer's share), `SettlementTransaction`
    (`block_number`, `block_time`, `gas_used`, `fee`, `l1_fee`, `native_price_usd`) and
    `TransferSettlement`. `OrganizationFee.organization` and `ReferralFee.referrer` → `address`.
-   **`metadata` is now your own data**: a `dict[str, str]` on `Product`, `Customer`, `Payment`
    (copied from its checkout, read-only), `Subscription`, `Transaction` and the
    `checkout.expired` session (`{}` without any).
-   **Models renamed and retyped**: `LinkResponse` → `CreatedCheckoutSession`,
    `TransactionStatus` → `CheckoutSessionStatus`, `SubscriptionHistory` → `Bill`, `RefundEntry` →
    `Refund` (`tx_id` → `tx_uuid`), `CombinedPaymentItem` → `Transaction`, `User` → `Member`,
    `UserRole` → `Role`, `CursorData` → `Page`; `transaction_hash` → `tx_hash`; the wire's `from`
    is `from_`. `name` → `first_name` on `Customer`, `CustomerSummary`, `Member` and `MeMember`
    (and the customer methods' arguments); a payment's and a bill's `name` / `description` →
    `product_name` / `product_description`; `Product.price` → `price_usd`; `Me.on_behalf_of` →
    `on_behalf_of_user_uuid`; `Member.accepted_currency_ids` → `accepted_currencies`
    (`list[Currency]`); `Wallet.public_key` → `address`; `TokenWallet.token_id` / `token` →
    `currency`; `Balance` is a `TokenAmount` plus its `currency` (was a code, `balance` and
    `balance_usd`); `HeldFunds.total_amount` and `MemberHeldFunds.total_amount` → `total_usd`;
    `LedgerEntry.amount` → `amount_usd`, `LedgerEntry.metadata` → `settlement`, plus `owed`;
    `Invitation.trust_layer` → `hold_funds` (and the `invitations.create` argument);
    `CreatedInvitation` is flat (the invitation's fields and `link`); the `currency_id` fields are
    gone (each model carries its `currency` object). Optional fields are `Optional[...]` (`None`
    when absent); a field the API always sends has a zero default.
-   **The currency object** gains `code` (`BASE:USDC`) and `chain`; `address` is `None` on a
    native coin; the nested `main_currency` is gone (`main_currency_id` stays).
-   **Enum values** follow the API's lowerCamelCase (`pastDue`, `trialExpired`);
    `TransactionType.ONE_TIME_PAYMENT` → `PAYMENT`, `EXECUTE_SUBSCRIPTION_PAYMENT` →
    `EXECUTE_SUBSCRIPTION`, the PAYG values are `createPaygSubscription` /
    `cancelPaygSubscription`. `LedgerEntryType` and `AccountingEventType` `subscriptionHistory` →
    `bill` (`LedgerEntryType.BILL`, `AccountingEventType.BILL`). `RefundStatus` adds `FAILED`
    (declared, never set). `WebhookPayloadVersion` has `V2` only: v2 is the only payload.
-   **Pagination**: `get_all(limit, cursor)` → `list(limit=…, cursor=…, filters…)` returning a
    `Page[T]` (`items`, `has_more`, `next_cursor`): `has_more` is a field (it was a property),
    `next_cursor` an opaque string (`None` on the last page). Iterators stop when `has_more` is
    false. Bounded lists (`currencies.list`, `wallets.list`, `wallets.list_for_member`,
    `wallets.list_accepted_currencies`, `members.list_held_funds`, `accounting.export_json`)
    return a `list` (and follow a `next_cursor` should one ever claim more, so an export is never
    cut short silently). Iterators also stop on an empty page that claims more, a page claiming
    more without a cursor, or a cursor that did not move (a server fault).
-   **Lookups by reference are list filters.** `products`, `customers`, `payments` and
    `subscriptions` `get_by_reference(reference)` run the list's `?reference=` filter and return
    the item whose `reference` equals the one asked for (exactly), or raise a `NotFoundError`
    (status 404, code `not_found`, the list answer's request id) when none does — never another
    resource. The reference is validated (1 to 100 of `A-Z a-z 0-9 . _ : @ -`).
    `customers.get_by_email` is removed: an email may match several customers
    (`customers.list(email=…)`).
-   **Deletes and revokes return `None`**: every `DELETE` answers `204`; `invitations.revoke` no
    longer returns the invitation.
-   **Decoding policy**: an absent or `null` value of a non-optional field decodes to its zero
    value (`ZERO_TIME` for a timestamp); a value of the wrong JSON type is a `ServerError` (a JSON
    number where a decimal string is expected included); unknown enum values are kept as raw
    strings; timestamps are aware `datetime`s with any offset. Every answer is a JSON object: a
    `null` body is a `ServerError`.
-   **Errors.** One class per condition, all deriving from `QBitFlowError` and `ApiError`
    (`status`, `code`, `message`, `details`, `request_id`, `field_errors`, `raw_body`):
    `ValidationError` (400 `validation_failed` and client-side checks), `BadRequestError` (other
    400s, which 2.x reported as validation errors), `AuthenticationError`,
    `PermissionDeniedError` (was `ForbiddenException` in 2.5.0), `NotFoundError` (was
    `NotFoundException`), `ConflictError`, `GoneError`, `IdempotencyError` (422, which 2.x
    reported as a validation error), `RateLimitError` (`retry_after`, `limit`, `period_seconds`),
    `ServerError`, `NetworkError`, `WebhookSignatureError`. `APIError` → `ApiError`;
    `InvalidRequestError` is removed. The `qbitflow.exceptions` package is gone: import the
    errors from `qbitflow`.
-   **Webhooks** use API v2's scheme: the `QBitFlow-Signature: t=…,v1=…` header, an
    HMAC-SHA256 of `t + "." + raw_body` over the raw body (no canonical JSON), and the event
    envelope (`id`, `type`, `version`, `created_at`, `test`, `user_uuid`, `data`); a version other
    than `v2` is refused (`ValidationError`). `verify_webhook_signature`,
    `compute_webhook_signature`, `canonical_json`, `extract_webhook_headers`, the `X-Webhook-*`
    header constants, `TEST_WEBHOOK_ID` and `client.webhooks.verify(payload, signature,
    timestamp)` are replaced by `qbitflow.webhooks.verify` / `construct_event` / `parse_event`
    (raising `WebhookSignatureError` with a `reason`) and `client.webhooks.verify_remote`.
-   **Webhook events renamed and reshaped**: `refund.completed` → `refund.approved`
    (`EventType.REFUND_APPROVED`, `RefundApprovedEvent`), `refund.denied` → `refund.rejected`
    (`EventType.REFUND_REJECTED`, `RefundRejectedEvent`). `subscription.billed`'s data is nested:
    `SubscriptionBilled(bill=…, subscription=…)` (the flattened `subscription_reference` /
    `subscription_status` are `data.subscription.reference` / `.status`).
    `subscription.created`'s data is a plain `Subscription` (the `SubscriptionCreated` class is
    gone). `subscription.upcomingBill`'s `billing_date` → `billing_at`, and its `amount_usd` is a
    string. `heldFunds.released`'s `tx_metadata` → `settlement` (a `TransferSettlement`), its
    `amount` the token amount next to `amount_usd`. The `checkout.expired` session has
    `price_usd`, `amount_usd` (were `price` / `amount` numbers), `available_currencies` (was
    `available_currency_ids`), `metadata`, and `upgrading_from_trial` as a bool.
-   **Renamed methods** (inside 3.0.0's preparation, before the API v2 final contract):
    `checkout_sessions.get_status` → `get`; `payments.list_combined` / `iterate_combined` →
    `transactions.list` / `iterate` (`CombinedPayment` → `Transaction`, `CombinedPaymentSource` →
    `TransactionKind` with `payment` / `bill`, the `source` filter → `type`);
    `subscriptions.execute_test_billing` → `test_bill` (`BillingState` → `TestBill`);
    `refunds.initiate` is removed (refunds are read only, below); `refunds.list` (active) and
    `list_inactive` /
    `iterate_inactive` → one `refunds.list` / `iterate` with a `status` filter;
    `wallets.list_supported_currencies` → `list_accepted_currencies`; `currencies.list_available`
    / `list_main` → `currencies.list(test=…, main=…)`; `webhooks.endpoints.list` takes
    `limit` / `cursor` and returns a page; `CheckoutSession` → `CreatedCheckoutSession`,
    `InvitationCreated` → `CreatedInvitation`, `MemberHeldFundsSummary` → `MemberHeldFunds`.
    `subscriptions.get_public_history` is removed (the customer's public bill history is set
    aside; `list_bills` has every bill).

### Added

-   `client.me()`: what the key is (role, space, mode, the member acted for), the recommended
    start-up check; `client.on_behalf_of(user_uuid)`; `RequestOptions`. `MeSpace` has `role`,
    `trusted_at`, `created_at` and `organization_fee_percent`.
-   `checkout_sessions`: `create_payment`, `create_subscription` (with `expires_in_minutes`,
    `metadata` and the `{{UUID}}` / `{{TRANSACTION_TYPE}}` redirect placeholders), `get`,
    `expire`.
-   **Checkout fees**: the customer pays a tax, shipping or QBitFlow's processing fee on top of
    the price.
    -   `checkout_sessions.create_payment(..., fees=CheckoutFees(items=[FeeItem(label,
        amount_usd, description=None)], processing_fee=None))`: up to 10 lines of your own and
        the processing fee (grossed up so you keep the price and your lines; `None` follows the
        dashboard's `checkout.customerPaysProcessingFee` setting). `amount_usd` is a decimal
        string or a `Decimal`, sent as a JSON string. Omitted when not given.
    -   `checkout_sessions.create_subscription(..., fees=…)`: the same `CheckoutFees` and rules
        (errors on `fees.items[i].<field>` after the terms'), locked with the price: every bill
        charges the price plus every line.
    -   Validated before sending: at most 10 lines (`fees.items`), `label` the name rule in 1 to
        40 characters, `description` the text rule up to 200, `amount_usd` above 0, at most
        1,000,000, at most 2 decimals, no sign or exponent (`fees.items[i].amountUsd`…). The
        test-mode `"5"` cap, fees included, is the API's (a 400 on `fees`).
    -   Models: `FeeLine` (`type`, `label`, `description`, `amount_usd` as a decimal string) and
        the open enum `FeeLineType` (`CUSTOM`, `PROCESSING_FEE`); `Payment.price_usd` and
        `fees` (so `payment.completed` has them: `amount_usd` = `price_usd` + the fees);
        `Subscription.fees` (next to `price_usd`, which stays the price); `Transaction.price_usd`
        and `fees`; `PaymentSessionData.fees` and `amount_usd` (`checkout.expired`: what the
        customer pays before the network fee).
-   **Merchant metadata** (`metadata=`, a mapping of strings) on `products.create` / `update`,
    `customers.create` / `update`, both session creates, and `subscriptions.update`
    (`PATCH /subscriptions/:uuid`): merged on the updates, a key set to `""` deleting it.
-   `transactions.list` / `iterate` (`GET /transactions`): the feed of payments and bills, each a
    `Transaction` with its `type` (`TransactionKind`: `payment`, `bill`), filtered by `type`,
    `subscription_uuid`, `refunded` and the shared filters.
-   `payments.list` / `iterate` with filters (customer, product, dates, `reference`, `refunded`,
    `include_members` / `user_uuid`); `payments.get(uuid, include_members=…)`. `failures.list` /
    `iterate`: the failed payment attempts (`attempted`, `attempted_usd`, `currency`).
-   `products.list` / `iterate` (paginated: `limit`, `cursor`, `include_hidden`, `subscription`,
    `reference`) and subscription products (`SubscriptionTermsParams`); `customers.list` /
    `iterate` (`email`, `reference`, `verified`).
-   `subscriptions.list` / `iterate` (`status`, `reference` and the shared filters), `update`,
    `list_bills` / `iterate_bills`, `get_bill` (`GET /bills/:uuid`);
    `Subscription.current_period_end` (grant access while now is before it), `action_required`,
    `price_usd`, `cancellation_reason`, `dunning`, `metadata`, `management_page_link`;
    `Allowance`.
-   `refunds.list` / `iterate` (`status` (a list, sent as repeated `?status=`), `tx_uuid`, `held`,
    `include_members`, `user_uuid`) and `refunds.get` (`GET /refunds/:uuid`), read only: a
    customer's request is answered, and a merchant's own refund sent, from the dashboard (the
    merchant's is recorded only once its transfer confirmed, `approved`: `refund.approved` is its
    only event). A `Refund` carries `paid`, `amount`, its `currency` and, once approved, its
    `settlement`.
-   `members` (`list`, `iterate`, `get`, `update`, `remove`, `trust`, `list_held_funds`,
    `get_held_funds`, `get_own_held_funds`) and `invitations` (`create`, `list`, `iterate`,
    `revoke`) for marketplaces.
-   `wallets` (`list(with_balances=…)`, `list_for_member`, `list_accepted_currencies`),
    `accounting.export_csv`, `currencies.list(test=…, main=…)`, `currencies.get(id)`.
-   `TokenAmount` (`amount`, `amount_min_units`, `amount_usd`), the shape of every token amount.
-   `webhooks.endpoints` (`list` / `iterate` paginated, `create` with the secret shown once,
    `get`, `update`, `delete`) and `webhooks.events` (the event log: `list`, `iterate`, `get` with
    its deliveries, `EventDetail`).
-   **Typed webhook events**: one class per event type (`PaymentCompletedEvent`, …,
    `RefundApprovedEvent`, `RefundRejectedEvent`, …, `WebhookTestEvent`: 15 types) in the `Event`
    discriminated union, `UnknownEvent` (raw `data`) for new types; `EventType` constants. Every
    `v1=` signature is checked, so a secret rotation needs nothing on the receiver's side.
-   **Iterators** for every paginated list (`iterate`, `iterate_bills`): lazy, one request per
    page, filters and page size kept.
-   **Retries**: reads and the 6 creates are retried on network errors, timeouts, 5xx, 429
    (honouring `Retry-After`, up to 60 s) and 409 `idempotency_key_in_use`, 3 times by default
    with a 1 s · 2ⁿ back-off; `max_retries=0` disables them; `is_retryable`.
-   An `Idempotency-Key` on each create, generated per call and reused on every retry
    (`RequestOptions(idempotency_key=…)` to set your own).
-   **Client-side validation** of every input, mirroring the API v2 validators and raising
    `ValidationError` with wire field names before anything is sent: names, texts, references
    (also on the `reference` filters and `get_by_reference`), emails (also the customers'
    `email` filter), phones, URLs, USD amounts as strings (at most 2 decimals, above 0, at most
    1,000,000), percents as strings (at most 2 decimals and 16 characters;
    `organization_fee_percent` 0 to 50, required on `members.update`), metadata (at
    most 50 keys of 1 to 40 of `A-Z a-z 0-9 _ - . :`, values of at most 500 characters without
    control or bidirectional characters), durations, ids (the `release@` prefix included),
    dates, cursors (at most 200 characters), the refunds' `status` filter (at most 5 known
    statuses), the transactions' `type`, exclusive filters, argument types, and a clearable
    `customers.update(last_name="")`.
-   `X-Request-Id` (`RequestOptions(request_id=…)`), echoed as `request_id` on errors.
-   `NOT_GIVEN`: the default of the clearable update fields (`""` or `None` clears them).
-   `qbitflow.__version__` single-sourced in `qbitflow/_version.py`; `User-Agent:
    qbitflow-python/3.0.0`.
-   **Integration helpers** (the same in the four SDKs):
    -   `webhooks.WebhookRouter(secret, *, tolerance=300, on_error=None)` (also
        `client.webhooks.router(secret)`): `@router.on("payment.completed")` (or an `EventType`)
        handlers called with `(data, event)`, `@router.on_unknown`, `@router.on_any`,
        `router.add(type, fn)`; `router.handle(raw_body, signature_header)` returns a
        `WebhookResult(status, event, error)`: 400 for a bad signature or body (no handler
        runs), 200 once handled or for a type without a handler, 500 when a handler raises (the
        rest are skipped); `on_error(event, exc)` hears every 400 and 500. Adapters, each
        importing its framework only when used (no new dependency; optional extras `flask`,
        `django`, `fastapi`, `starlette`): `router.flask_view()`, `router.django_view()`
        (CSRF-exempt), `router.fastapi_endpoint()` and `await router.handle_asgi(request)` for
        Starlette/FastAPI. They accept `POST` only (405), read at most 1 MiB (413), match
        `QBitFlow-Signature` case-insensitively and answer `{"received":true}` or
        `{"error":"…"}` (`invalid signature`, `invalid event`, `cannot read the body`,
        `internal error`, `method not allowed`, `body too large`).
    -   `webhooks.sign(raw_body, secret, timestamp=None)`: a `QBitFlow-Signature` header as
        QBitFlow sends it, to test your endpoint.
    -   `checkout_sessions.wait_for_completion(uuid, *, timeout=600, interval=3)`: polls
        `checkout_sessions.get` until `completed` or `expired`; on timeout, the last status seen
        (`timeout <= 0` means 600 s, `interval` at least 1 s, the last wait shortened to the time
        left).
    -   `Subscription.has_access(at=None)`: `current_period_end` set and `at` before it.
    -   `qbitflow.format_amount(min_units, decimals)` / `parse_amount(amount, decimals)` and
        `Currency.format_amount(min_units)`: exact conversions between minimal units and
        decimal strings (string arithmetic, never a float).
    -   `accounting.export_json_range` / `export_csv_range`: any range, split into windows of at
        most 92 days, both ends included (`[from, from + 91d]`), requested in order and joined
        (the CSV header once).
    -   `QBitFlow.from_env(**overrides)`: `QBITFLOW_API_KEY` (required), `QBITFLOW_BASE_URL`,
        `QBITFLOW_ON_BEHALF_OF`; keyword arguments win.
    -   `qbitflow.PLACEHOLDER_UUID` (`{{UUID}}`) and `PLACEHOLDER_TRANSACTION_TYPE`
        (`{{TRANSACTION_TYPE}}`) for `success_url` / `cancel_url`.

### Changed

-   Requires `pydantic>=2.5` (callable discriminators for the event union).
-   `AccountingEvent` follows the API's export: amounts in the currency's units as decimal
    strings, each with its `…_min_units` twin (`gross_amount_min_units`,
    `platform_fee_min_units`, `referral_fee_min_units`, `organization_fee_min_units`,
    `net_amount_min_units`, `network_fees_min_units`); USD amounts and rates as decimal strings;
    `currency` (was `token_symbol`), `currency_price_usd`, and the network fees apart from the
    net (`network_fees_paid_by`, the open enum `NetworkFeesPayer`: `PAYER`, `MERCHANT`,
    `ORGANIZATION`; `network_fees`, `network_fees_currency`, `network_fees_currency_decimals`,
    `network_fees_currency_price_usd`, `network_fees_usd`). `payment_reference` /
    `related_payment_reference` → `reference` / `related_reference`, `payment_uuid` /
    `related_payment_uuid` → `tx_uuid` / `related_tx_uuid`; a fee that doesn't apply is `None`
    (was `"0"`). Its fields are in the CSV's column order; the always-empty `user_name`,
    `user_last_name`, `customer_name` and `customer_last_name` are gone. The export window is at
    most 92 days, both ends included (the API's check).
-   Redirects are never followed (a 3xx is a `ServerError`).
-   A 2xx with an empty or non-JSON body where a result is expected is a `ServerError`.
-   Error bodies are parsed on every route (the CSV export included).
-   Request bodies that JSON cannot represent (NaN, infinities, unpaired surrogates) are refused
    with a `ValidationError` naming the field, and nothing is sent.
-   Update methods send an explicit `""` for the clearable fields (`customers.update`'s
    `last_name` / `phone_number` / `address`, `products.update`'s `description`,
    `webhooks.endpoints.update`'s `description`): `""` (or `None`) clears them, `NOT_GIVEN` (the
    default) leaves them.
-   The event log's cursor is opaque (was an event id); the subscriptions' `status` and the event
    log's `type` filters are sent as given (the API checks them).
-   `CustomerSummary.deleted` and `DeliveryAttempt.skipped` are `bool`s (false when absent).
-   `TestBill` sets `__test__ = False`, so pytest never collects it from a test module that
    imports it.
-   Error messages read `<message> (status <status>, code <code>, request <requestId>)`,
    followed by each field error; the SDK's own validation messages never echo the rejected
    values.

### Removed

-   `users`, `api_keys`, `claim`, `transaction_status` (and its WebSocket URL helper),
    `one_time_payments` (and its `get_session` / `get_customer_for_transaction`: read
    `payment.customer_uuid`, then `customers.get`), `subscriptions.get_session`,
    `refunds.get_by_transaction` (read `payment.refund` / `bill.refund`, or
    `refunds.list(tx_uuid=…)`), `customers.get_by_email` (`customers.list(email=…)`),
    `subscriptions.get_payment_history` and the public bill history (the customer's page;
    `list_bills` has every bill), pay-as-you-go (the API has no pay-as-you-go routes).
-   Canonical-JSON webhook verification and the v1 webhook payload models
    (`SessionWebhookResponse`, `SubscriptionStatusTransitionWebhook`…), `qbitflow.config`,
    `qbitflow.dto`, `qbitflow.requests`, `qbitflow.utils`, `qbitflow.exceptions`.
-   `PaymentMetadata`, `TxMetadata`, `BlockData`, `NetworkFees`, `TxAmounts`,
    `TxAmountsMinUnits`, `TxAmountsUsd` (→ `Settlement` & co.), `SubscriptionCreated` (→
    `Subscription`), `ApiKey`, `Organization`, `ClaimFund`, `CreateClaimRequestResponse`,
    `StatusResponse`, `SuccessResponse`, `TransactionShortType`; `legacyId` is not modelled.
-   Not implemented (set aside, dashboard concerns that may come back in a minor release): the
    settings routes, webhook delivery tooling (endpoint test, deliveries list, event types,
    resend), `GET /account`, `GET /api-keys` and the public bill history.

### Fixed

-   **Field validation errors were read from the wrong key** (a top-level `errors` list instead
    of the API's `details.errors`), so every field of a 400 came back empty. `field_errors` now
    names each failing input by its wire name, dotted when nested (`frequency.unit`).
-   User-supplied path segments and query values are escaped: an id containing `/`, `?`, `#`,
    `%` or `&` no longer changes the request; a `.` or `..` segment is escaped (an event id of
    `.` or `..` is refused).
-   Lengths are counted in characters (code points), as the API does.

The website snippet ids are unchanged (none renamed or retired); `transactions-list`,
`subscriptions-update` and `refunds-get` are new; `refunds-create` is listed as unsupported
(refunds are read only in the SDK).

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
