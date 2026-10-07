# QBitFlow Python SDK

[![PyPI version](https://badge.fury.io/py/qbitflow.svg)](https://badge.fury.io/py/qbitflow)
[![Python Support](https://img.shields.io/pypi/pyversions/qbitflow.svg)](https://pypi.org/project/qbitflow/)
[![License: MPL-2.0](https://img.shields.io/pypi/l/qtwebview2)](https://opensource.org/licenses/MPL-2.0)

Official Python SDK for [QBitFlow](https://qbitflow.app) - a comprehensive cryptocurrency payment processing platform that enables seamless integration of crypto payments and recurring subscriptions into your applications.

## Features

-   🔐 **Type-Safe**: Full type hints; response fields are typed exactly as the API sends them
-   🚀 **Easy to Use**: Simple, intuitive API design
-   🔄 **Automatic Retries**: Idempotent (GET) requests are retried on network errors and 5xx
-   🧪 **Well Tested**: Comprehensive test coverage
-   📚 **Great Documentation**: Detailed docs with examples
-   🔌 **Webhook Support**: Handle payment notifications easily
-   💳 **One-Time Payments**: Accept cryptocurrency payments with ease
-   🔄 **Recurring Subscriptions**: Automated recurring billing in cryptocurrency
-   👥 **Customer Management**: Create and manage customer profiles
-   🛍️ **Product Management**: Organize your products and pricing
-   📈 **Transaction Tracking**: Webhooks (recommended) or polling `transaction_status.get()`
-   💸 **Refund Tracking**: Monitor refund status
-   📊 **Accounting Export**: Export transaction data as JSON or CSV
-   🔑 **Account Claims**: Invite unclaimed users to set up their wallets

## Table of Contents

- [QBitFlow Python SDK](#qbitflow-python-sdk)
	- [Features](#features)
	- [Table of Contents](#table-of-contents)
	- [Installation](#installation)
	- [Quick Start](#quick-start)
		- [1. Get Your API Key](#1-get-your-api-key)
		- [2. Initialize the Client](#2-initialize-the-client)
		- [3. Create a One-Time Payment](#3-create-a-one-time-payment)
		- [4. Create a Recurring Subscription](#4-create-a-recurring-subscription)
		- [5. Check Transaction Status](#5-check-transaction-status)
	- [Configuration](#configuration)
		- [Configuration Options](#configuration-options)
		- [Retry Policy](#retry-policy)
	- [Acting on Behalf of a User](#acting-on-behalf-of-a-user)
	- [Response Typing](#response-typing)
	- [One-Time Payments](#one-time-payments)
		- [Create a Payment Session](#create-a-payment-session)
			- [Using your own references](#using-your-own-references)
		- [With Redirect URLs](#with-redirect-urls)
		- [Get Payment Session](#get-payment-session)
		- [Get Completed Payment](#get-completed-payment)
		- [Get Payment by Reference](#get-payment-by-reference)
		- [List All Payments](#list-all-payments)
		- [List Combined Payments](#list-combined-payments)
		- [Get Customer for Transaction](#get-customer-for-transaction)
	- [Subscriptions](#subscriptions)
		- [Create a Subscription](#create-a-subscription)
		- [Frequency Units](#frequency-units)
		- [Get Subscription](#get-subscription)
		- [Get Subscription by Reference](#get-subscription-by-reference)
		- [Get Payment History](#get-payment-history)
		- [Force Cancel](#force-cancel)
		- [Execute Test Billing Cycle](#execute-test-billing-cycle)
	- [Refunds](#refunds)
		- [List Active Refunds](#list-active-refunds)
		- [List Inactive Refunds](#list-inactive-refunds)
		- [Get Refund by Transaction](#get-refund-by-transaction)
	- [Accounting Export](#accounting-export)
	- [Account Claims](#account-claims)
		- [Get a Claim Request](#get-a-claim-request)
		- [Create a Claim Request](#create-a-claim-request)
		- [Get Claim Funds](#get-claim-funds)
		- [Trigger Test Claim Funds](#trigger-test-claim-funds)
	- [Transaction Status](#transaction-status)
		- [Check Status](#check-status)
		- [Transaction Types](#transaction-types)
		- [Status Values](#status-values)
	- [Customer Management](#customer-management)
	- [Product Management](#product-management)
	- [User Management](#user-management)
	- [API Key Management](#api-key-management)
	- [Currencies](#currencies)
		- [Typed payment metadata](#typed-payment-metadata)
	- [Webhook Handling](#webhook-handling)
		- [Verifying a webhook signature](#verifying-a-webhook-signature)
		- [Configuring Webhooks](#configuring-webhooks)
			- [Test Webhook Reachability](#test-webhook-reachability)
		- [Transaction Webhook](#transaction-webhook)
		- [Subscription Status Webhook](#subscription-status-webhook)
	- [Error Handling](#error-handling)
	- [API Reference](#api-reference)
		- [QBitFlow](#qbitflow)
			- [Constructor](#constructor)
			- [Properties](#properties)
	- [Testing](#testing)
	- [License](#license)
	- [Support](#support)
	- [Changelog](#changelog)
	- [Security](#security)

## Installation

Install the SDK using pip:

```bash
pip install qbitflow
```

Or install from source:

```bash
git clone https://github.com/qbitflow/qbitflow-python-sdk.git
cd qbitflow-python-sdk
pip install -e .
```

## Quick Start

### 1. Get Your API Key

Sign up at [QBitFlow](https://qbitflow.app) and obtain your API key from the dashboard.

### 2. Initialize the Client

```python
from qbitflow import QBitFlow

client = QBitFlow(api_key="your_api_key_here")
```

All handlers share one HTTP connection pool. Close it when you are done (or use the client
as a context manager):

```python
with QBitFlow(api_key="your_api_key_here") as client:
    ...
```

### 3. Create a One-Time Payment

```python
response = client.one_time_payments.create_session(
    product_id=1,
    success_url="https://your-domain.com/success",
    cancel_url="https://your-domain.com/cancel"
)

print(f"Payment link: {response.link}")
# Send this link to your customer
```

To pre-fill the checkout with a known customer, pass `customer_uuid=customer.uuid` (a bare
UUID, as returned by `client.customers`) or `customer_reference="your-own-id"`.

### 4. Create a Recurring Subscription

```python
from qbitflow import Duration

response = client.subscriptions.create_session(
    product_id=1,
    frequency=Duration(value=1, unit="months"),
    trial_period=Duration(value=7, unit="days"),  # Optional 7-day trial
)

print(f"Subscription link: {response.link}")
```

### 5. Check Transaction Status

```python
from qbitflow.dto.transaction.status import TransactionType, TransactionStatusValue

status = client.transaction_status.get(
    transaction_uuid=response.uuid,  # e.g. "pay@..." from create_session
    transaction_type=TransactionType.ONE_TIME_PAYMENT
)

if status.status == TransactionStatusValue.COMPLETED:
    print(f"Payment completed! Transaction hash: {status.tx_hash}")
elif status.status == TransactionStatusValue.FAILED:
    print(f"Payment failed: {status.message}")
```

## Configuration

### Configuration Options

| Option        | Type   | Default                       | Description                                                              |
| ------------- | ------ | ----------------------------- | ------------------------------------------------------------------------ |
| `api_key`     | string | (required)                    | Your QBitFlow API key                                                    |
| `base_url`    | string | `https://api.qbitflow.app/v1` | API base URL (trailing slash stripped). Also `QBITFLOW_BASE_URL` env var |
| `timeout`     | float  | `30`                          | Request timeout in seconds; `0` disables it                              |
| `max_retries` | int    | `3`                           | Retry attempts for idempotent (GET) requests; `0` disables retries       |

A blank API key raises `ValueError`; a negative or non-numeric `timeout` / `max_retries`, or a
blank `base_url`, raises `ValidationError` — before any connection is opened.

```python
client = QBitFlow(
    api_key="your_api_key_here",
    base_url="https://staging.example.com/v1",  # e.g. a staging API
    timeout=60,
    max_retries=5,
)
```

Base URL precedence, highest first:

1. `QBitFlow(api_key, base_url=...)` — per client.
2. `qbitflow.config.set_base_url(url)` — process-wide; clients created without `base_url`
   follow it, even if they were created before the call.
3. The `QBITFLOW_BASE_URL` environment variable, **read once when `qbitflow` is imported**.
4. The default, `https://api.qbitflow.app/v1`.

### Retry Policy

The policy is identical across every QBitFlow SDK:

-   Only **idempotent requests are retried: HTTP `GET`**. `POST`, `PUT` and `DELETE` are
    never retried, so a timed-out session creation is never silently sent twice.
-   Three `GET` routes perform an action and are explicitly non-retriable:
    `subscriptions.force_cancel()`, `subscriptions.execute_test_billing_cycle()` and
    `claims.trigger_test_claim_funds()`.
-   A retry is triggered by any transport failure — connection, read/write, timeout, or a
    protocol error such as "server disconnected without sending a response" — or by any `5xx`
    response. `4xx`, `429`, `3xx` and configuration errors (a `base_url` without `http://` /
    `https://`) are never retried.
-   Backoff is exponential: 1s, 2s, 4s. `max_retries=0` disables retries.
-   Redirects are never followed: a `3xx` reaching the SDK is reported as a `ServerError` —
    it almost always means a misconfigured `base_url`.

## Acting on Behalf of a User

If you hold an **organization (admin) API key**, you can perform any request as one of the users in your organization, without needing that user's own API key. This is useful for admin-level tooling, dashboards, and back-office automation where your server acts for a specific user (e.g. listing _their_ products, creating a payment session _for them_, or reading _their_ subscriptions).

`client.on_behalf_of(user_id)` returns a scoped client: **every** service on it adds an
`On-Behalf-Of` header to each request. Every service also exposes its own
`on_behalf_of(user_id)`, returning a scoped copy of just that service. Either way the original
client is left untouched, so you can freely mix org-level and per-user calls.
`on_behalf_of(0)` acts at the organization level (no header); anything other than a
non-negative integer (a negative id, `True`, `1.5`, `"5"`) raises `ValidationError`.

```python
user_id = 123

# Every service, scoped to user 123
as_user = client.on_behalf_of(user_id)
products = as_user.products.get_all()
user_payments = as_user.one_time_payments.get_all()

# Or scope a single service
products = client.products.on_behalf_of(user_id).get_all()

# The base client is unaffected — this call still runs at the organization level
all_org_products = client.products.get_all()
```

A scoped client shares the root client's connection pool and settings. **Close only the root
client** (closing a scoped copy is a no-op); once the root is closed, its scoped copies can no
longer be used.

> **Note:** `on_behalf_of` requires an organization-level admin/owner API key. Acting for a
> user outside your organization answers `404`; acting for a regular user on an admin-only
> route answers `403` (`ForbiddenException`).

## Response Typing

Response models are typed exactly as the Go API serializes them, so you never have to
null-check a field the API always sends:

-   A field the API always sends — or omits only when it is empty — is **non-nullable** and
    decodes to its zero value when absent or `null`: `0`, `""`, `False`, `[]`, an empty nested
    object, or `qbitflow.GO_ZERO_TIME` (`0001-01-01T00:00:00Z`, Go's zero time) for a
    timestamp. For example `payment.product_id` is `0` for an inline product,
    `customer.phone_number` is `""` when none was given, and `subscription.last_billing_date`
    is `GO_ZERO_TIME` before the first billing.
-   Only fields that are pointers in the API are `Optional`, e.g. `payment.customer_uuid`,
    `payment.reference`, `refund.responded_at`, `user.claimed_at`, `api_key.expires_at`,
    `currency.main_currency`, `payment.metadata.organization_fee`.
-   `payment.currency`, `subscription.currency` and each billing record's / combined
    payment's `currency` are full `Currency` objects.
-   A field that arrives with the **wrong JSON type** (a string where a number is expected, an
    object where a string is expected, …) raises `ServerError` with the HTTP status; unknown
    keys are ignored and unknown enum values are kept as plain strings.

`GO_ZERO_TIME` compares equal to the decoded zero time; converting it to a local time zone west
of UTC (`.astimezone()`) raises `OverflowError`, so compare against it before converting.

## One-Time Payments

### Create a Payment Session

Provide either a `product_id` for an existing product, or `product_name` + `description` + `price` for an ad-hoc charge:

```python
# From an existing product
response = client.one_time_payments.create_session(product_id=1)

# Ad-hoc payment
response = client.one_time_payments.create_session(
    product_name="Custom Product",
    description="Product description",
    price=99.99,  # USD, must be greater than 0
)

print(response.uuid)  # Session UUID ("pay@...")
print(response.link)  # Payment link for customer
```

The SDK checks the API's rules before sending and raises `ValidationError` otherwise: an inline
`price` must be a finite number greater than 0; `customer_uuid`, when given, must be a bare UUID
(not `pay@…`-prefixed); redirect URLs must be absolute `http(s)` URLs. An empty string for an
optional argument means "not provided" and is left out of the request.

#### Using your own references

Instead of storing QBitFlow's internal UUIDs, pass your own identifiers. Set `reference` to your
order/invoice ID, and use `product_reference` / `customer_reference` to select an existing product
or customer by your own reference:

```python
response = client.one_time_payments.create_session(
    reference="order-1234",            # your own transaction reference
    product_reference="PROD-PREMIUM",  # use a product by your reference (instead of product_id)
    customer_reference="user-42",      # use a customer by your reference (instead of customer_uuid)
)
```

The `reference` is echoed back on the resulting `Payment` and in webhook payloads, and you can look
the payment up later with [`get_by_reference()`](#get-payment-by-reference). If no customer matches
`customer_reference`, one is created during checkout.

### With Redirect URLs

```python
response = client.one_time_payments.create_session(
    product_id=1,
    success_url="https://your-domain.com/success?uuid={{UUID}}&transaction_type={{TRANSACTION_TYPE}}",
    cancel_url="https://your-domain.com/cancel",
)
```

**Available Placeholders:**

-   `{{UUID}}`: The session UUID
-   `{{TRANSACTION_TYPE}}`: The transaction type of the session

### Get Payment Session

Returns a `OneTimePaymentSession`. Asking `one_time_payments.get_session()` for a
subscription session raises `ValidationError` (use `subscriptions.get_session()`), and vice
versa.

```python
session = client.one_time_payments.get_session(response.uuid)
print(session.product_name, session.price, session.organization_name)
```

### Get Completed Payment

```python
payment = client.one_time_payments.get("pay@...")
print(payment.transaction_hash, payment.amount, payment.currency.symbol)
```

### Get Payment by Reference

Look a payment up by the `reference` you assigned when creating the session — no need to store
QBitFlow's UUID:

```python
payment = client.one_time_payments.get_by_reference("order-1234")
print(payment.uuid, payment.amount)
```

### List All Payments

```python
page = client.one_time_payments.get_all(limit=10)

print(page.items)      # List of Payment objects
print(page.has_more()) # Whether there are more pages
print(page.next_cursor)

if page.has_more():
    next_page = client.one_time_payments.get_all(limit=10, cursor=page.next_cursor)
```

### List Combined Payments

Get all payments from both one-time and subscription sources in a single paginated list:

```python
page = client.one_time_payments.get_all_combined(limit=20)
for item in page.items:
    print(item.source)  # "payment" or "subscription_history"
    print(item.amount)
    if item.subscription_uuid:
        print(f"Subscription: {item.subscription_uuid}")
```

### Get Customer for Transaction

```python
customer = client.one_time_payments.get_customer_for_transaction("pay@...")  # or "sub@..."
print(f"{customer.name} {customer.last_name} — {customer.email}")
```

## Subscriptions

A subscription session takes the same product forms as a one-time payment: an existing
product (`product_id` or `product_reference`) **or** an inline ghost product
(`product_name` + `description` + `price`).

### Create a Subscription

```python
from qbitflow import Duration

response = client.subscriptions.create_session(
    product_id=1,
    frequency=Duration(value=1, unit="months"),
    trial_period=Duration(value=7, unit="days"),  # Optional
    min_periods=3,                                 # Optional: minimum billing periods
)

print(response.link)  # Send to customer
```

`frequency` is required and its value must be an integer from 1 to 4294967295.
`trial_period` may have a value of 0, and `min_periods` is an integer from 0 to 4294967295
(0 means no minimum and is not sent).

Like one-time payments, subscription sessions accept your own `reference`, `product_reference`,
and `customer_reference` instead of QBitFlow's internal IDs, or an inline product:

```python
response = client.subscriptions.create_session(
    reference="sub-1234",            # your own subscription reference
    product_reference="PLAN-PRO",    # select a product by your reference
    customer_reference="user-42",    # select a customer by your reference
    frequency=Duration(value=1, unit="months"),
)

# Inline ghost product — no stored product needed
response = client.subscriptions.create_session(
    product_name="Pro plan",
    description="Monthly Pro subscription",
    price=29.0,
    frequency=Duration(value=1, unit="months"),
)
```

### Frequency Units

Available units for `frequency` and `trial_period`:

-   `seconds`
-   `minutes`
-   `hours`
-   `days`
-   `weeks`
-   `months`
-   `years`

### Get Subscription

```python
subscription = client.subscriptions.get("sub@...")
print(subscription.subscription_status, subscription.next_billing_date)
print(subscription.allowance, subscription.currency.symbol)
```

### Get Subscription by Reference

Look a subscription up by the `reference` you assigned when creating the session:

```python
subscription = client.subscriptions.get_by_reference("sub-1234")
print(subscription.uuid, subscription.subscription_status)
```

> **Tracking status changes:** You no longer need to poll `get()` on a schedule
> (e.g. a cron job) to detect subscription lifecycle changes. Enable the
> **Subscription status webhook** in your QBitFlow dashboard settings and you will
> receive a notification on every status transition. See
> [Subscription Status Webhook](#subscription-status-webhook).

### Get Payment History

```python
history = client.subscriptions.get_payment_history("sub@...")
for record in history:
    print(record.uuid, record.amount, record.created_at)
```

### Force Cancel

Force cancel a subscription immediately, bypassing the normal user-signed cancellation flow:

```python
response = client.subscriptions.force_cancel("sub@...")
print(response.message)
```

### Execute Test Billing Cycle

**Test Mode Only**: Manually trigger a billing cycle to test webhook behaviour. Returns the
API's `{message}` envelope; a subscription that is not yet due raises `ConflictError` (409).

```python
from qbitflow.exceptions import ConflictError

try:
    result = client.subscriptions.execute_test_billing_cycle("sub@...")
    print(result.message)
except ConflictError as e:
    print("Not due yet:", e.message)
```

## Refunds

### List Active Refunds

```python
refunds = client.refunds.get_all()
for refund in refunds:
    # `status` is a RefundStatus (a str enum) or, for a value this SDK does not know, a str
    print(f"{refund.uuid}: {refund.status} — {refund.reason}")
```

### List Inactive Refunds

Returns processed (approved/refused/failed) refunds with pagination:

```python
page = client.refunds.get_all_inactive(limit=10)
for refund in page.items:
    print(f"{refund.uuid}: {refund.status} (responded {refund.responded_at})")

if page.has_more():
    next_page = client.refunds.get_all_inactive(limit=10, cursor=page.next_cursor)
```

### Get Refund by Transaction

The route is public, but the API honours your API key, so the refund comes back complete:

```python
refund = client.refunds.get_by_transaction("pay@...")
print(refund.status, refund.tx_hash or "not processed yet")
```

## Accounting Export

Export transaction data for a date range. Dates must be real `YYYY-MM-DD` calendar dates and
`from` must not be after `to` — the SDK checks this before sending, raising `ValidationError`.
The length of the window is decided by the API (a window it refuses answers `400`, also a
`ValidationError`).

```python
# JSON export — returns List[AccountingEvent]
events = client.accounting.export("2025-01-01", "2025-01-31", "json")
for event in events:
    print(f"{event.payment_id} | {event.type} | ${event.gross_amount_usd}")

# CSV export — returns raw CSV string
csv_data = client.accounting.export("2025-01-01", "2025-01-31", "csv")
with open("accounting_2025_01.csv", "w") as f:
    f.write(csv_data)
```

`event.type` is a plain string: `payment`, `refund`, `organizationFee`, `referralFee`, or the
subscription-billing value (spelled `subscriptionHistory` or `subHistory` in the API
reference; `qbitflow.dto.accounting.ACCOUNTING_EVENT_TYPES` lists both).

`AccountingEvent` fields include: `payment_id`, `type`, `tx_time_utc`, `receipt_url`, `product_id`, `customer_uuid`, `chain`, `tx_hash`, `token_symbol`, `gross_amount_usd`, `platform_fee_usd`, `organization_fee_usd`, `net_amount_usd`, and more.

## Account Claims

QBitFlow lets organizations create users whose payments are held by the organization. When the organization is ready, they create a **claim request** — a one-time link that the user follows to set up their wallet and receive their accumulated funds. These operations live on `client.claims` (`client.claim` and `claims.get_request()` remain as deprecated aliases that emit a `DeprecationWarning`).

### Get a Claim Request

Retrieve the existing claim link for a user without creating a new one:

```python
result = client.claims.get_request_by_user(user_id=42)
print(f"Claim link: {result.link}")
```

### Create a Claim Request

Create a claim request for a user. A user may have only one active request: a second
`create_request()` raises `ValidationError` (400) — use `get_request_by_user()` to fetch the
existing link.

```python
result = client.claims.create_request(user_id=42)
print(f"Claim link: {result.link}")
# Send result.link to the user by email
```

### Get Claim Funds

List the amounts your organization owes its provisioned users:

```python
funds = client.claims.get_funds()
for fund in funds:
    if not fund.funded:
        print(f"Pending: ${fund.total_amount_owed} → user {fund.user_id}")
```

### Trigger Test Claim Funds

**Test Mode Only**: Manually compute ledger totals for a user without waiting for the hourly
job. It is an action, so it is never retried automatically:

```python
client.claims.trigger_test_claim_funds(user_id=42)
```

## Transaction Status

To learn that a payment or subscription settled, use [webhooks](#webhook-handling)
(recommended — QBitFlow notifies your endpoint), or poll `transaction_status.get()`.

### Check Status

```python
from qbitflow.dto.transaction.status import TransactionType

status = client.transaction_status.get(
    "pay@...",
    TransactionType.ONE_TIME_PAYMENT
)

print(status.status)   # TransactionStatusValue enum (or a str for an unknown value)
print(status.tx_hash)  # Blockchain transaction hash ("" until broadcast)
```

### Transaction Types

```python
class TransactionType:
    ONE_TIME_PAYMENT = 'payment'
    TRANSFER = 'transfer'
    TOKEN_TRANSFER = 'tokenTransfer'
    CREATE_SUBSCRIPTION = 'createSubscription'
    CANCEL_SUBSCRIPTION = 'cancelSubscription'
    EXECUTE_SUBSCRIPTION_PAYMENT = 'executeSubscription'
    CREATE_PAYG_SUBSCRIPTION = 'createPAYGSubscription'  # records only; no PAYG routes
    CANCEL_PAYG_SUBSCRIPTION = 'cancelPAYGSubscription'
    INCREASE_ALLOWANCE = 'increaseAllowance'
    UPDATE_MAX_AMOUNT = 'updateMaxAmount'
    REFUND = 'refund'
    FAUCET = 'faucet'
    CLAIM_FUNDS = 'claimFunds'
```

### Status Values

```python
class TransactionStatusValue:
    CREATED = 'created'
    WAITING_CONFIRMATION = 'waitingConfirmation'
    PENDING = 'pending'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'
    EXPIRED = 'expired'
```

> **Unknown enum values.** Enum-typed fields on *responses* (`status`, `subscription_status`,
> `role`, `tx_type`, refund `status`, webhook `type`) never fail to parse: a value this SDK
> version does not know yet is kept as a plain `str`. Known values hydrate to the enum
> member, and because the enums subclass `str`, `status == "completed"` and
> `status == TransactionStatusValue.COMPLETED` both keep working. Request DTOs stay strict.

## Customer Management

```python
from qbitflow.dto.customer import CreateCustomerDto, UpdateCustomerDto

# Create
customer = client.customers.create(CreateCustomerDto(
    name="John", last_name="Doe",
    email="john@example.com",
    phone_number="+1234567890",
    reference="CRM-12345"
))

# Get
customer = client.customers.get(customer.uuid)  # a bare UUID
customer = client.customers.get_by_email("john@example.com")
customer = client.customers.get_by_reference("CRM-12345")

# List (paginated)
page = client.customers.get_all(limit=10)

# Update - partial: send only what changes, everything else is left untouched
updated = client.customers.update(customer.uuid, UpdateCustomerDto(name="John"))

updated = client.customers.update(customer.uuid, UpdateCustomerDto(
    name="John", last_name="Doe", email="john.doe@example.com"
))

# Note: `reference` is immutable and cannot be updated.

# Delete
client.customers.delete(customer.uuid)
```

`name` / `last_name` follow the API's `alphanumspace` rule (Unicode letters, decimal digits,
spaces and `- _ ' .`, 2–100 characters — `²` or `Ⅻ` are rejected, as the API rejects them) and
`email` must be a structurally valid address, which is sent exactly as given (case preserved).
Violations raise `qbitflow.exceptions.ValidationError` when the DTO is built, before any
request. On `UpdateCustomerDto`, an empty string means "not provided" and is left out of the
request. Every identifier argument (`uuid`, `reference`, `email`) is checked for emptiness and
every numeric id for positivity.

References are escaped correctly in the URL, but the API currently cannot route a reference
containing `/` (it answers 404).

## Product Management

```python
from qbitflow.dto.product import CreateProductDto, UpdateProductDto

# Create
product = client.products.create(CreateProductDto(
    name="Premium Subscription",
    description="Access to all premium features",
    price=29.99,
    reference="PROD-PREMIUM"
))

# Get
product = client.products.get(1)
product = client.products.get_by_reference("PROD-PREMIUM")

# List all
products = client.products.get_all()

# Update - partial: omitted fields keep their current value
updated = client.products.update(1, UpdateProductDto(price=39.99))

updated = client.products.update(1, UpdateProductDto(
    name="Premium Plus",
    description="Enhanced premium features",
    price=39.99
))

# Delete
client.products.delete(1)
```

`name` (2–100) and `description` (2–500) follow the API's `producttext` rule: no markup
characters (`< > { } [ ] \` \\ | ; " ~ ^`), no control characters and not blank; `price` must
be a finite number greater than 0. Length is counted in characters, as the server counts runes.
An empty `reference` on create means "generate one"; an empty `name` or `description` on update
is rejected. Violations raise `ValidationError`.

## User Management

```python
from qbitflow.dto.user import CreateUserDto, UpdateUserDto

# Create (admin only)
user = client.users.create(CreateUserDto(
    name="Alice",
    last_name="Smith",
    email="alice@example.com",
    role="user",              # "user" or "admin"
    organization_fee_bps=100  # optional integer 0-5000, 1% fee
))

# Get current user (identified by API key)
me = client.users.get()

# Get by ID or list all (admin only)
user = client.users.get_by_id(42)
users = client.users.get_all()

# Get by email (admin only for other users in the organization)
user = client.users.get_by_email("alice@example.com")

# Update - partial: omitted fields keep their current value
updated = client.users.update(user.id, UpdateUserDto(name="Alicia"))

# organization_fee_bps requires admin authority (an admin/owner key, or an
# organization-level key via on_behalf_of). A non-admin caller sending it gets a 403.
updated = client.users.update(user.id, UpdateUserDto(organization_fee_bps=250))  # 2.5%

# Note: passwords cannot be changed through this SDK. It is a JWT-only, self-service
# operation on the API, so the field is intentionally absent from UpdateUserDto.

# Delete (admin only)
client.users.delete(user.id)
```

## API Key Management

API-key **creation and deletion are JWT-only** API operations and cannot be performed
with an API key, so the SDK exposes **read-only** access. Create and revoke keys from the
QBitFlow dashboard.

```python
# List API keys for the current user
keys = client.api_keys.get_all()

# List API keys for a specific user (admin only)
keys = client.api_keys.get_for_user(user_id)
```

## Currencies

Sessions reference the accepted currencies by **ID** (`session.available_currencies` is a
`list[int]`); payments, combined payments, subscriptions and billing records carry the full
`currency` object (with `main_currency` for a token). Use the public currency lookups to resolve
IDs to `Currency` details.

```python
# All supported currencies (native currencies and tokens)
currencies = client.currencies.get_all_available()

# Only the main (native / blockchain) currencies, excluding tokens
main_currencies = client.currencies.get_all_main()

by_id = {c.id: c for c in currencies}
session = client.one_time_payments.get_session("pay@...")
for currency_id in session.available_currencies:
    currency = by_id[currency_id]
    print(f"{currency.name} ({currency.symbol})")
```

### Typed payment metadata

Payment metadata is fully typed. `Payment.metadata` and `SubscriptionHistory.metadata` are
`PaymentMetadata` (always present); `CombinedPaymentItem.metadata` is
`Optional[PaymentMetadata]` and `RefundEntry.metadata` is `Optional[TxMetadata]`.
`PaymentMetadata` exposes the fee breakdown (`fee_bps`, and the optional `organization_fee` /
`referral_fee`), on-chain details (`tx_metadata`), and the computed per-party amounts
(`tx_amounts`, in both USD and smallest currency units).

## Webhook Handling

### Verifying a webhook signature

Every webhook QBitFlow sends carries three headers:

| Header | Meaning |
|---|---|
| `X-Webhook-Signature-256` | HMAC signature, formatted `sha256=<hex>` |
| `X-Webhook-Timestamp` | Send time, in unix seconds |
| `X-Webhook-Id` | Transaction id, e.g. `pay@<uuid>` |

There are two ways to check a webhook is genuine, and you can use either:

| | Needs the secret | Network call | Use when |
|---|---|---|---|
| **Local** | yes | none | Default. Faster, and keeps working if the API is unreachable. |
| **Remote** | no | one per webhook | You would rather not hold the secret at all. |

Local verification performs the same three checks the server does: the timestamp is within
a replay window (5 minutes by default), the HMAC matches, and the comparison is
constant-time so a timing side channel cannot be used to guess the signature.

**Why the signature covers a canonical rendering, not the raw bytes.** JSON object key
order is not significant, and proxies, frameworks and logging layers routinely re-serialize
a body and reorder keys. Signing raw bytes would reject a payload that is in fact
untouched. So both sides sign `<timestamp>.<canonical-json>`, where canonical means keys
sorted at every level and no insignificant whitespace. You do not have to do anything for
this — pass the body you received and the SDK handles it.

Get your webhook secret from the QBitFlow dashboard. Treat it like a password: keep it in
your environment or secret manager, never in source control.

```python
import os

from flask import Flask, request
from qbitflow import extract_webhook_headers, parse_session_webhook, verify_webhook_signature
from qbitflow.exceptions import ValidationError

app = Flask(__name__)


@app.post("/webhooks")
def handle_webhook():
    headers = extract_webhook_headers(request.headers)

    try:
        verify_webhook_signature(
            os.environ["QBITFLOW_WEBHOOK_SECRET"],
            headers["timestamp"],
            headers["signature"],
            request.get_data(),  # raw bytes
        )
    except ValidationError:
        return "invalid webhook", 400

    if headers["is_test"]:
        return "", 200  # verified connectivity check, nothing to process

    event = parse_session_webhook(request.get_data())
    return "", 200
```

`extract_webhook_headers` takes any mapping, so it works with Flask, Django,
FastAPI/Starlette or a plain dict. Lookup is case-insensitive and a repeated header yields
its first value.

Pass the **raw body**: it is canonicalised exactly as the Go server does (a payload you have
already decoded also works, but a stdlib-decoded `-0` loses its sign). The timestamp must be an
ASCII integer (an optional sign, no whitespace), as Go's `strconv.ParseInt` requires. To widen
or narrow the replay window (it must match the server's setting; `0` or less means the default
of 300 seconds):

```python
verify_webhook_signature(secret, timestamp, signature, body, max_timestamp_age_seconds=600)
```

To verify through the API instead, with no secret in your process — the payload may be the raw
body or an already-decoded value; only a `400` from the API returns `False`, every other
failure raises:

```python
ok = client.webhooks.verify(payload, signature, timestamp)
```

After verification, parse the body with `parse_session_webhook(body)` (transaction webhook) or
`parse_subscription_webhook(body)` (subscription webhook). They decode with the same policy as
API responses and raise `ValidationError` for a body that is not JSON or has a field of the
wrong type.

### Configuring Webhooks

Webhook URLs are **no longer set per session**. Instead, configure them once in your
QBitFlow dashboard settings, and they apply consistently to every transaction:

-   **Transaction webhook** — receives notifications when a payment or subscription
    session changes status (e.g. completed, failed). Payload: `SessionWebhookResponse`.
-   **Subscription status webhook** — receives notifications on every subscription
    lifecycle transition (e.g. `trial → active`, `active → past_due`,
    `active → cancelled`), and on each successful renewal. Payload: `SubscriptionWebhook`.

> **Migration note:** Previous versions accepted a `webhook_url` argument on
> `one_time_payments.create_session()` and `subscriptions.create_session()`. That
> parameter has been removed — set the **Transaction webhook** in the dashboard instead.
> Likewise, the **Subscription status webhook** replaces the old pattern of running a
> cron job that periodically calls `subscriptions.get()` to detect status changes.

A complete, runnable FastAPI example lives in [`examples/server.py`](examples/server.py).

#### Test Webhook Reachability

The dashboard's **Test webhook** action lets you confirm your endpoint is reachable
before going live. It sends a request with a **fake payload** that will not parse like a
real webhook — so your handler must short-circuit it. The request carries the webhook ID
in the `X-Webhook-Id` header; when that value equals `TEST_WEBHOOK_ID`, return HTTP `200`
immediately and skip normal payload processing:

```python
from qbitflow import TEST_WEBHOOK_ID

# ...inside your handler, after verifying the signature:
if x_webhook_id == TEST_WEBHOOK_ID:
    return {"status": "received", "message": "Test webhook acknowledged"}
```

Perform this check **after** signature verification but **before** parsing the payload.

Verifying first is deliberate: running the probe through your verification path is what
makes the dashboard button a genuine end-to-end test of your setup — secret, headers and
replay window included. Short-circuiting before the signature check would make the button
report success even with a broken or missing secret. Checking before *parsing* still
matters, because the fake payload will not validate as a real event. Both examples below
follow this order.

> **Note:** this assumes the dashboard's probe is signed like a normal delivery. If your
> probe is rejected with a signature mismatch, confirm that with QBitFlow before relaxing
> the check.

### Transaction Webhook

Handles payment and subscription session status changes. Always verify the signature
before trusting the payload:

```python
from typing import Annotated
from fastapi import FastAPI, Request, Header, HTTPException
from qbitflow import QBitFlow, TEST_WEBHOOK_ID, parse_session_webhook
from qbitflow.dto.transaction.status import TransactionStatusValue

app = FastAPI()
client = QBitFlow(api_key="your_api_key")

@app.post("/webhook")
async def handle_webhook(
    request: Request,
    x_webhook_id: Annotated[str, Header()],
    x_webhook_signature_256: Annotated[str, Header()],
    x_webhook_timestamp: Annotated[str, Header()]
):
    body = await request.body()

    if not client.webhooks.verify(
        payload=body,
        signature=x_webhook_signature_256,
        timestamp=x_webhook_timestamp
    ):
        # Returning a >= 400 status causes QBitFlow to retry the webhook
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    # Reachability test from the dashboard — acknowledge and skip processing
    if x_webhook_id == TEST_WEBHOOK_ID:
        return {"status": "received", "message": "Test webhook acknowledged"}

    event = parse_session_webhook(body)

    # event.session is automatically resolved to the correct session type:
    # OneTimePaymentSession or SubscriptionSession. event.status may be None.
    if event.status and event.status.status == TransactionStatusValue.COMPLETED:
        print(f"Payment completed: {event.session.product_name}")
        print(f"Customer: {event.session.customer_uuid}")
        print(f"Amount: ${event.session.price}")
        # `reference` echoes back the value you set when creating the session, so you can
        # match the transaction to your own order/invoice without storing our UUID.
        print(f"Your reference: {event.session.reference}")

        from qbitflow.dto.transaction.session import SubscriptionSession
        if isinstance(event.session, SubscriptionSession):
            print(f"Frequency: {event.session.frequency}s")
    elif event.status and event.status.status == TransactionStatusValue.FAILED:
        print(f"Payment failed: {event.status.message}")

    return {"received": True}
```

### Subscription Status Webhook

Once the **Subscription status webhook** is enabled in the dashboard, QBitFlow POSTs a
`SubscriptionWebhook` payload whenever a subscription changes status — no polling
required. The same endpoint also receives a delivery on each successful renewal, so the
envelope carries `subscription_uuid`, `subscription_reference` (your own reference, if
set), a `type` discriminator, and the event-specific payload in `data`:

- `type == SubscriptionWebhookType.STATUS_TRANSITION` → `data` is a
  `SubscriptionStatusTransition` (`previous_status`, `current_status`, `updated_at`)
- `type == SubscriptionWebhookType.BILLING` → `data` is a `SubscriptionHistory`

```python
from typing import Annotated
from fastapi import FastAPI, Request, Header, HTTPException
from qbitflow import QBitFlow, TEST_WEBHOOK_ID, parse_subscription_webhook
from qbitflow.dto.transaction.subscription import SubscriptionStatus, SubscriptionWebhookType

app = FastAPI()
client = QBitFlow(api_key="your_api_key")

@app.post("/subscription-webhook")
async def handle_subscription_webhook(
    request: Request,
    x_webhook_id: Annotated[str, Header()],
    x_webhook_signature_256: Annotated[str, Header()],
    x_webhook_timestamp: Annotated[str, Header()]
):
    body = await request.body()

    if not client.webhooks.verify(
        payload=body,
        signature=x_webhook_signature_256,
        timestamp=x_webhook_timestamp
    ):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    # Reachability test from the dashboard — acknowledge and skip processing
    if x_webhook_id == TEST_WEBHOOK_ID:
        return {"status": "received", "message": "Test webhook acknowledged"}

    event = parse_subscription_webhook(body)

    if event.type == SubscriptionWebhookType.BILLING:
        # A period was renewed — record event.data against event.subscription_uuid
        print(f"Subscription {event.subscription_uuid} billed {event.data.amount}")
        return {"received": True}

    if event.type != SubscriptionWebhookType.STATUS_TRANSITION:
        # A webhook type this SDK version does not know: event.data is the raw dict.
        return {"received": True}

    print(f"Subscription {event.subscription_uuid} "
          f"(ref: {event.subscription_reference or '-'}): "
          f"{event.data.previous_status} -> {event.data.current_status}")

    # React to the lifecycle transition — e.g. revoke access on cancellation
    if event.data.current_status == SubscriptionStatus.CANCELLED:
        print(f"Revoking access for {event.subscription_uuid}")
    elif event.data.current_status == SubscriptionStatus.PAST_DUE:
        print(f"Payment failed — notifying customer for {event.subscription_uuid}")

    return {"received": True}
```

`SubscriptionStatus` values: `active`, `cancelled`, `past_due`, `low_on_funds`,
`pending`, `trial`, `trial_expired`. A status added by the API later arrives as a plain
string rather than failing the delivery.

## Error Handling

Every exception derives from `QBitFlowError` and carries `message`, `status_code` (whenever an
HTTP response was involved, including response-shape failures) and `fields` — the per-field
failures, one `FieldError(field, message)` each. Client-side validation, including building a
request DTO, raises the same `ValidationError` with `status_code=None`.

| HTTP status                                   | Exception                                           |
| --------------------------------------------- | --------------------------------------------------- |
| 400, 422                                      | `ValidationError` (same type as client-side checks) |
| 401                                           | `AuthenticationError`                               |
| 403                                           | `ForbiddenException`                                |
| 404                                           | `NotFoundException`                                 |
| 409                                           | `ConflictError`                                     |
| 429                                           | `RateLimitError` (`retry_after` seconds or `None`)  |
| other 4xx                                     | `InvalidRequestError`                               |
| 5xx, 3xx, empty / non-JSON 2xx, wrong types   | `ServerError` (a subclass of `APIError`)            |
| network / timeout after retries               | `NetworkError`                                      |

```python
from qbitflow.exceptions import (
    QBitFlowError,
    AuthenticationError,
    ConflictError,
    ForbiddenException,
    NotFoundException,
    RateLimitError,
    ServerError,
    ValidationError,
    NetworkError,
)

try:
    # "P" is too short: rejected locally, before any request, with the same type as a 400.
    product = client.products.create(CreateProductDto(name="P", description="Desc", price=9.99))
except ValidationError as e:
    # A field rejected locally *or* by the API (400): same type, same handling.
    print(f"Validation failed ({e.status_code}): {e.message}")
    for failure in e.fields:
        print(f"  {failure.field}: {failure.message}")
except AuthenticationError:
    print("Invalid or expired API key")
except ForbiddenException:
    print("This API key is not permitted to do that")
except NotFoundException as e:
    print(f"Not found: {e.message}")
except ConflictError as e:
    print(f"Conflict: {e.message}")
except RateLimitError as e:
    print(f"Rate limited; retry after {e.retry_after} seconds")
except ServerError as e:
    print(f"QBitFlow is unavailable or answered unexpectedly ({e.status_code}): {e.message}")
except NetworkError as e:
    print(f"Network error: {e.message}")
except QBitFlowError as e:
    print(f"SDK error: {e.message}")
```

Request DTOs (`CreateCustomerDto`, `CreateProductDto`, …) validate their fields when they
are constructed — and again when handed to a request method — and raise the SDK's
`ValidationError` with `fields`, never `pydantic.ValidationError`. Request methods also accept a
plain mapping of the DTO's fields.

## API Reference

### QBitFlow

#### Constructor

```python
QBitFlow(
    api_key: str,
    timeout: Optional[float] = None,
    max_retries: Optional[int] = None,
    base_url: Optional[str] = None,
)
```

`client.close()` releases the shared HTTP connection pool; the client is also a context
manager. `client.on_behalf_of(user_id)` returns a scoped client sharing that pool (close only
the root client).

#### Properties

| Property             | Type                          | Description                              |
|----------------------|-------------------------------|------------------------------------------|
| `customers`          | `CustomerRequests`            | Customer CRUD operations                 |
| `products`           | `ProductRequests`             | Product CRUD operations                  |
| `users`              | `UserRequests`                | User management operations               |
| `api_keys`           | `ApiKeyRequests`              | Read-only API key access                 |
| `currencies`         | `CurrencyRequests`            | Supported-currency lookups               |
| `one_time_payments`  | `PaymentRequests`             | One-time payment sessions and history    |
| `subscriptions`      | `SubscriptionRequests`        | Recurring subscription management        |
| `refunds`            | `RefundRequests`              | Refund retrieval                         |
| `accounting`         | `AccountingRequests`          | Accounting data export (JSON/CSV)        |
| `claims`             | `ClaimRequests`               | Account claim and fund transfer (`claim` is a deprecated alias) |
| `transaction_status` | `TransactionStatusRequests`   | Transaction status polling               |
| `webhooks`           | `WebhookRequests`             | Webhook signature verification           |

## Testing

```bash
# Offline suite (no server needed): transport, DTOs, validation, webhooks
pytest tests/ -v

# Live integration tests run against the server named by QBITFLOW_BASE_URL, with
# QBITFLOW_API_KEY. They never default to localhost or production:
#   neither variable set           -> the live tests are skipped
#   key set, QBITFLOW_BASE_URL not -> the live tests fail with a clear message
set -a; . ../.local.env; set +a   # or export both variables yourself
pytest tests/test_integration.py -v
```

## License

This project is licensed under the MPL-2.0 License - see the [LICENSE](LICENSE) file for details.

## Support

-   📖 [Documentation](https://qbitflow.app/docs)
-   📧 [Email Support](mailto:support@qbitflow.app)
-   🐛 [Issue Tracker](https://github.com/qbitflow/qbitflow-python-sdk/issues)

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for a list of changes in each version.

## Security

For security issues, please email security@qbitflow.app instead of using the issue tracker.

