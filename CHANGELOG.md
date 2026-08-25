# Changelog

All notable changes to the QBitFlow Python SDK will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


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
